"""Linux owner for managed-stack established-flow return affinity."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
from typing import Any

from .linux_nft_scaffold import NftScriptRunner
from .stack_return_affinity import (
    StackReturnAffinityDesired,
    StackReturnAffinityPlatformSpace,
    StackReturnRuleSpec,
)
from .stack_return_affinity_convergence import (
    StackReturnAffinityObservation,
    StackReturnAffinityOwnerStatus,
)


STACK_RETURN_TABLE = "vpn_gate_return_affinity"
STACK_RETURN_CHAIN = "prerouting"
STACK_RETURN_TABLE_COMMENT = "vpn-gate:ng3:stack-return-affinity-owner-v1"
STACK_RETURN_CHAIN_COMMENT = "vpn-gate:ng3:stack-return-affinity-prerouting-v1"
STACK_RETURN_CLASSIFIER_COMMENT = "vpn-gate:ng3:stack-return-affinity-classifier-v1"
STACK_RETURN_RESTORE_COMMENT = "vpn-gate:ng3:stack-return-affinity-restore-v1"


@dataclass(frozen=True, slots=True)
class _RuleKey:
    priority: int
    mark: int
    table: int


@dataclass(frozen=True, slots=True)
class _NftInventory:
    present: bool
    owned: bool
    classifiers: tuple[tuple[int, str, int], ...] = ()
    restores: tuple[tuple[int, int], ...] = ()
    diagnostic: str | None = None


@dataclass(slots=True)
class LinuxStackReturnAffinityBackend:
    runner: NftScriptRunner
    namespace: str
    platform: StackReturnAffinityPlatformSpace | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be non-empty text")

    def create_nft(self, desired: StackReturnAffinityDesired) -> None:
        if not isinstance(desired, StackReturnAffinityDesired):
            raise ValueError("desired must be StackReturnAffinityDesired")
        if not desired.classifiers:
            return
        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            render_stack_return_affinity_nft(desired),
        )

    def delete_nft(self) -> None:
        self.runner.run(
            self._cmd("nft", "delete", "table", "ip", STACK_RETURN_TABLE)
        )

    def add_rule(self, rule: StackReturnRuleSpec) -> None:
        if not isinstance(rule, StackReturnRuleSpec):
            raise ValueError("rule must be StackReturnRuleSpec")
        self.runner.run(
            self._cmd(
                "ip", "-4", "rule", "add",
                "priority", str(rule.priority),
                "fwmark", hex(rule.mark),
                "lookup", str(rule.table),
            )
        )

    def delete_rule(self, rule: StackReturnRuleSpec) -> None:
        if not isinstance(rule, StackReturnRuleSpec):
            raise ValueError("rule must be StackReturnRuleSpec")
        self.runner.run(
            self._cmd(
                "ip", "-4", "rule", "del",
                "priority", str(rule.priority),
                "fwmark", hex(rule.mark),
                "lookup", str(rule.table),
            )
        )

    def observe(self, desired: StackReturnAffinityDesired) -> StackReturnAffinityObservation:
        if self.platform is None:
            raise ValueError("platform is required for authoritative affinity observation")
        nft = _parse_nft_inventory(
            self.runner.run(self._cmd("nft", "-j", "list", "ruleset"))
        )
        rules, rule_conflict = _parse_reserved_rules(
            self.runner.run(self._cmd("ip", "-j", "-4", "rule", "show")),
            self.platform,
        )
        if nft.diagnostic is not None or rule_conflict is not None:
            return StackReturnAffinityObservation(
                StackReturnAffinityOwnerStatus.CONFLICT,
                diagnostic=nft.diagnostic or rule_conflict,
            )

        expected_rules = tuple(
            sorted(
                (_RuleKey(item.priority, item.mark, item.table) for item in desired.rules),
                key=lambda item: (item.priority, item.mark, item.table),
            )
        )
        expected_classifiers = tuple(
            sorted(
                (
                    item.ingress.ifindex,
                    item.remote_prefix.with_prefixlen,
                    item.mark,
                )
                for item in desired.classifiers
            )
        )
        expected_restores = tuple(
            sorted((desired.host_boundary.ifindex, item.mark) for item in desired.rules)
        )

        wants_owner = bool(desired.classifiers)
        if not wants_owner:
            if nft.present or rules:
                return StackReturnAffinityObservation(
                    StackReturnAffinityOwnerStatus.STALE,
                    diagnostic="affinity owner exists but desired state is empty",
                )
            return StackReturnAffinityObservation(
                StackReturnAffinityOwnerStatus.EXACT,
                desired=desired,
            )

        if not nft.present and not rules:
            return StackReturnAffinityObservation(StackReturnAffinityOwnerStatus.ABSENT)
        if not nft.present or not nft.owned:
            return StackReturnAffinityObservation(
                StackReturnAffinityOwnerStatus.CONFLICT,
                diagnostic="reserved affinity nft owner is absent or not owned while reserved RPDB state exists",
            )

        exact = (
            nft.classifiers == expected_classifiers
            and nft.restores == expected_restores
            and rules == expected_rules
        )
        return StackReturnAffinityObservation(
            StackReturnAffinityOwnerStatus.EXACT if exact else StackReturnAffinityOwnerStatus.STALE,
            desired=desired if exact else None,
            diagnostic=None if exact else "owned affinity state differs from exact desired state",
        )

    def replace_owned(
        self,
        desired: StackReturnAffinityDesired,
        observed: StackReturnAffinityObservation,
    ) -> None:
        if observed.status not in {
            StackReturnAffinityOwnerStatus.ABSENT,
            StackReturnAffinityOwnerStatus.STALE,
        }:
            raise ValueError("replace_owned requires ABSENT or STALE classified state")
        current = self.observe(desired)
        if current.status is StackReturnAffinityOwnerStatus.CONFLICT:
            raise RuntimeError(current.diagnostic or "affinity owner conflict before mutation")
        if current.status is StackReturnAffinityOwnerStatus.EXACT:
            return
        self._clear_reserved_owned_state()
        if desired.classifiers:
            self.create_nft(desired)
            for rule in desired.rules:
                self.add_rule(rule)

    def cleanup_owned(self) -> None:
        if self.platform is None:
            raise ValueError("platform is required for authoritative affinity cleanup")
        nft = _parse_nft_inventory(
            self.runner.run(self._cmd("nft", "-j", "list", "ruleset"))
        )
        rules, rule_conflict = _parse_reserved_rules(
            self.runner.run(self._cmd("ip", "-j", "-4", "rule", "show")),
            self.platform,
        )
        if nft.diagnostic is not None or rule_conflict is not None:
            raise RuntimeError(nft.diagnostic or rule_conflict)
        if nft.present and not nft.owned:
            raise RuntimeError("reserved affinity nft table is not owned")
        for rule in reversed(rules):
            self.runner.run(
                self._cmd(
                    "ip", "-4", "rule", "del",
                    "priority", str(rule.priority),
                    "fwmark", hex(rule.mark),
                    "lookup", str(rule.table),
                )
            )
        if nft.present:
            self.delete_nft()

    def _clear_reserved_owned_state(self) -> None:
        assert self.platform is not None
        nft = _parse_nft_inventory(
            self.runner.run(self._cmd("nft", "-j", "list", "ruleset"))
        )
        rules, conflict = _parse_reserved_rules(
            self.runner.run(self._cmd("ip", "-j", "-4", "rule", "show")),
            self.platform,
        )
        if nft.diagnostic is not None or conflict is not None:
            raise RuntimeError(nft.diagnostic or conflict)
        if nft.present and not nft.owned:
            raise RuntimeError("reserved affinity nft table is not owned")
        for rule in reversed(rules):
            self.runner.run(
                self._cmd(
                    "ip", "-4", "rule", "del",
                    "priority", str(rule.priority),
                    "fwmark", hex(rule.mark),
                    "lookup", str(rule.table),
                )
            )
        if nft.present:
            self.delete_nft()

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)


def _parse_int(value: Any, label: str) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            pass
    raise ValueError(f"{label} must be an integer")


def _parse_reserved_rules(
    text: str,
    platform: StackReturnAffinityPlatformSpace,
) -> tuple[tuple[_RuleKey, ...], str | None]:
    document = json.loads(text)
    if not isinstance(document, list):
        raise ValueError("ip rule JSON root must be an array")
    found: list[_RuleKey] = []
    for row in document:
        if not isinstance(row, dict):
            raise ValueError("ip rule entry must be an object")
        priority = row.get("priority")
        if priority is None:
            continue
        priority = _parse_int(priority, "rule priority")
        in_priority_pool = platform.rule_priorities.first <= priority < platform.rule_priorities.stop
        fwmark_raw = row.get("fwmark")
        mark = None if fwmark_raw is None else _parse_int(fwmark_raw, "fwmark")
        in_mark_pool = (
            mark is not None
            and platform.marks.first <= mark < platform.marks.stop
        )
        if not in_priority_pool and not in_mark_pool:
            continue
        if not in_priority_pool or not in_mark_pool:
            return (), "reserved affinity RPDB priority/mark is used by a non-owner rule"
        table_raw = row.get("table")
        if table_raw is None:
            return (), "reserved affinity RPDB rule has no lookup table"
        try:
            table = _parse_int(table_raw, "lookup table")
        except ValueError:
            return (), "reserved affinity RPDB rule has non-numeric lookup table"
        unsupported = set(row) - {
            "priority", "fwmark", "fwmask", "table", "action", "protocol",
        }
        if unsupported:
            return (), f"reserved affinity RPDB rule has unsupported selectors {sorted(unsupported)!r}"
        action = row.get("action")
        if action not in {None, "to_tbl"}:
            return (), "reserved affinity RPDB rule has unsupported action"
        mask = row.get("fwmask")
        if mask is not None and _parse_int(mask, "fwmask") != 0xFFFFFFFF:
            return (), "reserved affinity RPDB rule uses a non-exact mark mask"
        found.append(_RuleKey(priority, mark, table))
    found.sort(key=lambda item: (item.priority, item.mark, item.table))
    if len({item.priority for item in found}) != len(found):
        return (), "duplicate reserved affinity RPDB priority"
    if len({item.mark for item in found}) != len(found):
        return (), "duplicate reserved affinity mark"
    return tuple(found), None


def _parse_nft_inventory(text: str) -> _NftInventory:
    document = json.loads(text)
    if not isinstance(document, dict) or not isinstance(document.get("nftables"), list):
        raise ValueError("nft ruleset JSON must contain nftables array")
    rows = document["nftables"]
    tables = []
    chains = []
    rules = []
    for row in rows:
        if not isinstance(row, dict) or len(row) != 1:
            raise ValueError("nft row must be a single-key object")
        kind, payload = next(iter(row.items()))
        if kind == "metainfo":
            continue
        if not isinstance(payload, dict):
            raise ValueError("nft object payload must be an object")
        if kind == "table" and payload.get("family") == "ip" and payload.get("name") == STACK_RETURN_TABLE:
            tables.append(payload)
        elif payload.get("family") == "ip" and payload.get("table") == STACK_RETURN_TABLE:
            if kind == "chain":
                chains.append(payload)
            elif kind == "rule":
                rules.append(payload)
            else:
                return _NftInventory(True, False, diagnostic=f"reserved affinity table contains unsupported {kind!r} object")

    if not tables:
        if chains or rules:
            return _NftInventory(True, False, diagnostic="reserved affinity objects exist without table declaration")
        return _NftInventory(False, False)
    if len(tables) != 1:
        return _NftInventory(True, False, diagnostic="duplicate reserved affinity table declaration")
    if tables[0].get("comment") != STACK_RETURN_TABLE_COMMENT:
        return _NftInventory(True, False, diagnostic="reserved affinity table owner marker differs")
    if len(chains) != 1:
        return _NftInventory(True, False, diagnostic="reserved affinity owner must contain exactly one chain")
    chain = chains[0]
    if (
        chain.get("name") != STACK_RETURN_CHAIN
        or chain.get("type") != "filter"
        or chain.get("hook") != "prerouting"
        or chain.get("policy") != "accept"
        or chain.get("comment") != STACK_RETURN_CHAIN_COMMENT
        or chain.get("prio") not in {-150, "mangle"}
    ):
        return _NftInventory(True, False, diagnostic="reserved affinity chain shape differs")

    classifiers: list[tuple[int, str, int]] = []
    restores: list[tuple[int, int]] = []
    for rule in rules:
        comment = rule.get("comment")
        expr = rule.get("expr")
        if not isinstance(expr, list):
            return _NftInventory(True, False, diagnostic="reserved affinity rule expression is malformed")
        try:
            if comment == STACK_RETURN_CLASSIFIER_COMMENT:
                classifiers.append(_parse_classifier_expr(expr))
            elif comment == STACK_RETURN_RESTORE_COMMENT:
                restores.append(_parse_restore_expr(expr))
            else:
                return _NftInventory(True, False, diagnostic="reserved affinity owner contains unclassified rule")
        except ValueError as exc:
            return _NftInventory(True, False, diagnostic=str(exc))
    return _NftInventory(
        True,
        True,
        tuple(sorted(classifiers)),
        tuple(sorted(restores)),
    )


def _match(expr: list[dict], left_kind: str, key: str) -> Any:
    for item in expr:
        if not isinstance(item, dict) or "match" not in item:
            continue
        match = item["match"]
        if not isinstance(match, dict) or match.get("op") != "==":
            continue
        left = match.get("left")
        if isinstance(left, dict):
            body = left.get(left_kind)
            if isinstance(body, dict) and body.get("key") == key:
                return match.get("right")
    raise ValueError(f"reserved affinity rule misses {left_kind}.{key} exact match")


def _parse_classifier_expr(expr: list[dict]) -> tuple[int, str, int]:
    ingress = _parse_int(_match(expr, "meta", "iif"), "classifier iif")
    source = None
    for item in expr:
        if not isinstance(item, dict) or "match" not in item:
            continue
        match = item["match"]
        left = match.get("left") if isinstance(match, dict) else None
        payload = left.get("payload") if isinstance(left, dict) else None
        if isinstance(payload, dict) and payload.get("protocol") == "ip" and payload.get("field") == "saddr":
            right = match.get("right")
            if isinstance(right, dict) and isinstance(right.get("prefix"), dict):
                prefix = right["prefix"]
                source = f"{prefix.get('addr')}/{prefix.get('len')}"
            elif isinstance(right, str):
                source = right
    if source is None:
        raise ValueError("classifier source prefix match is missing")
    source = ipaddress.IPv4Network(source, strict=True).with_prefixlen
    state = _match(expr, "ct", "state")
    if state not in {"new", ["new"]}:
        raise ValueError("classifier does not match ct state new")
    mark = None
    for item in expr:
        if not isinstance(item, dict):
            continue
        mangle = item.get("mangle")
        if not isinstance(mangle, dict):
            continue
        key = mangle.get("key")
        if isinstance(key, dict):
            ct = key.get("ct")
            if isinstance(ct, dict) and ct.get("key") == "mark":
                mark = _parse_int(mangle.get("value"), "classifier ct mark")
    if mark is None:
        raise ValueError("classifier ct mark assignment is missing")
    return ingress, source, mark


def _parse_restore_expr(expr: list[dict]) -> tuple[int, int]:
    ingress = _parse_int(_match(expr, "meta", "iif"), "restore iif")
    mark = _parse_int(_match(expr, "ct", "mark"), "restore ct mark")
    restored = False
    for item in expr:
        if not isinstance(item, dict):
            continue
        mangle = item.get("mangle")
        if not isinstance(mangle, dict):
            continue
        key = mangle.get("key")
        value = mangle.get("value")
        meta = key.get("meta") if isinstance(key, dict) else None
        ct = value.get("ct") if isinstance(value, dict) else None
        if (
            isinstance(meta, dict) and meta.get("key") == "mark"
            and isinstance(ct, dict) and ct.get("key") == "mark"
        ):
            restored = True
    if not restored:
        raise ValueError("restore rule does not copy ct mark to packet mark")
    return ingress, mark


def render_stack_return_affinity_nft(
    desired: StackReturnAffinityDesired,
) -> str:
    if not isinstance(desired, StackReturnAffinityDesired):
        raise ValueError("desired must be StackReturnAffinityDesired")
    if not desired.classifiers:
        raise ValueError("cannot render empty stack return-affinity owner")

    lines = [
        f"table ip {STACK_RETURN_TABLE} {{",
        f'  comment "{STACK_RETURN_TABLE_COMMENT}"',
        f"  chain {STACK_RETURN_CHAIN} {{",
        "    type filter hook prerouting priority mangle; policy accept;",
        f'    comment "{STACK_RETURN_CHAIN_COMMENT}"',
    ]

    for item in desired.classifiers:
        lines.append(
            "    "
            f"meta iif {item.ingress.ifindex} "
            f"ip saddr {item.remote_prefix.with_prefixlen} "
            "ct state new "
            f"ct mark set {hex(item.mark)} "
            f'comment "{STACK_RETURN_CLASSIFIER_COMMENT}"'
        )

    for rule in desired.rules:
        lines.append(
            "    "
            f"meta iif {desired.host_boundary.ifindex} "
            f"ct mark {hex(rule.mark)} "
            "meta mark set ct mark "
            f'comment "{STACK_RETURN_RESTORE_COMMENT}"'
        )

    lines.extend(("  }", "}", ""))
    return "\n".join(lines)
