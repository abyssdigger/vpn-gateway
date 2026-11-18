"""Strict host-namespace nft owner for NG3 stateful return steering."""

from __future__ import annotations

from dataclasses import dataclass
import json

from .linux_host_boundary_policy import (
    HOST_RETURN_CLASSIFY_CHAIN_COMMENT,
    HOST_RETURN_INGRESS_RULE_COMMENT,
    HOST_RETURN_OUTPUT_CHAIN_COMMENT,
    HOST_RETURN_OUTPUT_RESTORE_COMMENT,
    HOST_RETURN_PREROUTE_RESTORE_COMMENT,
    HOST_RETURN_PREROUTING_CHAIN_COMMENT,
    HOST_RETURN_TABLE,
    HOST_RETURN_TABLE_COMMENT,
    HostReturnNftSpec,
    classifier_rule_comment,
    render_host_return_nft,
)
from .linux_nft_scaffold import NftScriptRunner


@dataclass(frozen=True, slots=True)
class HostReturnNftObservation:
    table_present: bool
    exact: bool
    conflicts: tuple[str, ...]


@dataclass(slots=True)
class LinuxHostReturnNftBackend:
    runner: NftScriptRunner
    network_namespace: str | None = None

    def __post_init__(self) -> None:
        if self.network_namespace is not None and (
            not isinstance(self.network_namespace, str)
            or not self.network_namespace
        ):
            raise ValueError("network_namespace must be non-empty text or None")

    def observe(self, desired: HostReturnNftSpec | None) -> HostReturnNftObservation:
        if desired is not None and not isinstance(desired, HostReturnNftSpec):
            raise ValueError("desired must be HostReturnNftSpec or None")
        raw = self.runner.run(self._cmd("nft", "-j", "-y", "list", "ruleset"))
        return parse_host_return_nft_observation(raw, desired)

    def replace(self, desired: HostReturnNftSpec | None) -> None:
        current = self.observe(desired)
        if current.conflicts:
            raise RuntimeError("host return nft owner conflict: " + "; ".join(current.conflicts))
        lines = []
        if current.table_present:
            lines.append(f"delete table inet {HOST_RETURN_TABLE}")
        if desired is not None:
            lines.append(render_host_return_nft(desired))
        if not lines:
            return
        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            "\n".join(lines).rstrip() + "\n",
        )

    def _cmd(self, *args: str) -> tuple[str, ...]:
        if self.network_namespace is None:
            return tuple(args)
        return ("ip", "netns", "exec", self.network_namespace, *args)


def converge_host_return_nft_once(
    backend: LinuxHostReturnNftBackend,
    desired: HostReturnNftSpec | None,
) -> HostReturnNftObservation:
    if not isinstance(backend, LinuxHostReturnNftBackend):
        raise ValueError("backend must be LinuxHostReturnNftBackend")
    initial = backend.observe(desired)
    if initial.conflicts:
        raise RuntimeError("host return nft owner conflict: " + "; ".join(initial.conflicts))
    if initial.exact:
        return initial
    backend.replace(desired)
    final = backend.observe(desired)
    if final.conflicts:
        raise RuntimeError("host return nft postcondition conflict: " + "; ".join(final.conflicts))
    if not final.exact:
        raise RuntimeError("host return nft fresh postcondition does not match desired state")
    return final


def parse_host_return_nft_observation(
    raw: str,
    desired: HostReturnNftSpec | None,
) -> HostReturnNftObservation:
    try:
        root = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("invalid host return nft JSON") from None
    rows = root.get("nftables") if isinstance(root, dict) else None
    if not isinstance(rows, list):
        raise ValueError("host return nft JSON must contain nftables array")

    table_rows = []
    chain_rows = []
    rule_rows = []
    conflicts = []
    for row in rows:
        if not isinstance(row, dict) or len(row) != 1:
            continue
        kind, payload = next(iter(row.items()))
        if kind == "metainfo" or not isinstance(payload, dict):
            continue
        if payload.get("family") != "inet":
            continue
        table = payload.get("table")
        name = payload.get("name")
        belongs = (
            kind == "table" and name == HOST_RETURN_TABLE
        ) or table == HOST_RETURN_TABLE
        if not belongs:
            continue
        if kind == "table":
            table_rows.append(payload)
        elif kind == "chain":
            chain_rows.append(payload)
        elif kind == "rule":
            rule_rows.append(payload)
        else:
            conflicts.append(f"unsupported object {kind!r} in host return table")

    if not table_rows and not chain_rows and not rule_rows and not conflicts:
        return HostReturnNftObservation(
            table_present=False,
            exact=desired is None,
            conflicts=(),
        )

    if len(table_rows) != 1:
        conflicts.append("host return table object is missing or duplicated")
    elif table_rows[0].get("comment") != HOST_RETURN_TABLE_COMMENT:
        conflicts.append("host return table owner comment mismatch")

    expected_chains = {
        "classify_remote": (None, None, None, HOST_RETURN_CLASSIFY_CHAIN_COMMENT),
        "prerouting": ("filter", "prerouting", -150, HOST_RETURN_PREROUTING_CHAIN_COMMENT),
        "output": ("route", "output", -150, HOST_RETURN_OUTPUT_CHAIN_COMMENT),
    }
    by_chain = {}
    for row in chain_rows:
        name = row.get("name")
        if not isinstance(name, str) or name in by_chain:
            conflicts.append("host return chain identity is invalid or duplicated")
            continue
        by_chain[name] = row
    if set(by_chain) != set(expected_chains):
        conflicts.append("host return chain set does not match owner contract")
    for name, expected in expected_chains.items():
        row = by_chain.get(name)
        if row is None:
            continue
        chain_type, hook, prio, comment = expected
        if row.get("comment") != comment:
            conflicts.append(f"host return chain {name!r} owner comment mismatch")
        if chain_type is None:
            if any(key in row for key in ("type", "hook", "prio", "policy")):
                conflicts.append("host return classifier chain unexpectedly is a base chain")
        else:
            if row.get("type") != chain_type or row.get("hook") != hook:
                conflicts.append(f"host return chain {name!r} type/hook mismatch")
            if row.get("prio") != prio:
                conflicts.append(f"host return chain {name!r} priority mismatch")
            if row.get("policy") != "accept":
                conflicts.append(f"host return chain {name!r} policy mismatch")

    comments = []
    for rule in rule_rows:
        comment = rule.get("comment")
        if not isinstance(comment, str):
            conflicts.append("host return rule has no owner comment")
            continue
        comments.append(comment)
        if not _is_owned_rule_comment(comment):
            conflicts.append("foreign rule exists in owned host return table")

    expected_comments = []
    if desired is not None:
        expected_comments.extend(
            classifier_rule_comment(index, rule)
            for index, rule in enumerate(desired.classifier)
        )
        expected_comments.extend(
            (
                HOST_RETURN_INGRESS_RULE_COMMENT,
                HOST_RETURN_PREROUTE_RESTORE_COMMENT,
                HOST_RETURN_OUTPUT_RESTORE_COMMENT,
            )
        )

    comments_match = desired is not None and comments == expected_comments
    shape_conflicts: list[str] = []
    if comments_match and not conflicts:
        _validate_rule_shapes(rule_rows, desired, shape_conflicts)
        conflicts.extend(shape_conflicts)

    exact = (
        not conflicts
        and comments_match
        and len(table_rows) == 1
        and set(by_chain) == set(expected_chains)
    )
    return HostReturnNftObservation(
        table_present=True,
        exact=exact,
        conflicts=tuple(conflicts),
    )


def _is_owned_rule_comment(comment: str) -> bool:
    if comment in {
        HOST_RETURN_INGRESS_RULE_COMMENT,
        HOST_RETURN_PREROUTE_RESTORE_COMMENT,
        HOST_RETURN_OUTPUT_RESTORE_COMMENT,
    }:
        return True
    return comment.startswith("vpn-gate:ng3:host-return-classifier-v1:")


def _validate_rule_shapes(
    rules: list[dict],
    desired: HostReturnNftSpec,
    conflicts: list[str],
) -> None:
    expected_count = len(desired.classifier) + 3
    if len(rules) != expected_count:
        conflicts.append("host return rule count mismatch")
        return
    for index, semantic in enumerate(desired.classifier):
        row = rules[index]
        if row.get("chain") != "classify_remote":
            conflicts.append("host return classifier rule is on unexpected chain")
            continue
        blob = json.dumps(row.get("expr"), sort_keys=True)
        if (
            str(semantic.remote_prefix.network_address) not in blob
            or str(semantic.remote_prefix.prefixlen) not in blob
        ):
            conflicts.append(f"classifier rule {index} remote prefix mismatch")
        if '"return"' not in blob:
            conflicts.append(f"classifier rule {index} lacks return verdict")
        if semantic.stateful_return:
            if "ct" not in blob or str(desired.mark) not in blob:
                conflicts.append(f"classifier rule {index} lacks expected ct mark write")
        elif "ct" in blob and "mark" in blob:
            conflicts.append(f"classifier rule {index} unexpectedly writes ct mark")

    ingress, restore, output = rules[-3:]
    if ingress.get("chain") != "prerouting":
        conflicts.append("host return ingress rule is on unexpected chain")
    ingress_blob = json.dumps(ingress.get("expr"), sort_keys=True)
    if desired.interface not in ingress_blob or "classify_remote" not in ingress_blob:
        conflicts.append("host return ingress rule does not match managed interface/jump")

    if restore.get("chain") != "prerouting":
        conflicts.append("host return prerouting restore rule is on unexpected chain")
    restore_blob = json.dumps(restore.get("expr"), sort_keys=True)
    if desired.interface not in restore_blob or "ct" not in restore_blob or "meta" not in restore_blob:
        conflicts.append("host return prerouting restore rule shape mismatch")
    if str(desired.mark) not in restore_blob:
        conflicts.append("host return prerouting restore mark mismatch")

    if output.get("chain") != "output":
        conflicts.append("host return output restore rule is on unexpected chain")
    output_blob = json.dumps(output.get("expr"), sort_keys=True)
    if "ct" not in output_blob or "meta" not in output_blob or str(desired.mark) not in output_blob:
        conflicts.append("host return output restore rule shape mismatch")
