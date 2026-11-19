"""Strict host-side nft owner for fixed Release-1 behavior lanes."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from .host_boundary_behavior import (
    HostBoundaryBehaviorIntent,
    HostBoundaryBehaviorLane,
)
from .linux_nft_scaffold import NftScriptRunner


HOST_BEHAVIOR_TABLE = "vpn_gate_host_behavior"
HOST_BEHAVIOR_TABLE_COMMENT = "vpn-gate:ng3:host-behavior-owner-v1"
HOST_BEHAVIOR_PREROUTING_COMMENT = "vpn-gate:ng3:host-behavior-prerouting-v1"
HOST_BEHAVIOR_OUTPUT_COMMENT = "vpn-gate:ng3:host-behavior-output-v1"
HOST_BEHAVIOR_POSTROUTING_COMMENT = "vpn-gate:ng3:host-behavior-postrouting-v1"


class HostBoundaryBehaviorLinuxError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HostBoundaryBehaviorLinuxAllocation:
    stateful_no_nat_mark: int
    stateful_nat_mark: int
    route_no_nat_mark: int
    route_nat_mark: int
    return_mark: int

    def __post_init__(self) -> None:
        values = (
            self.stateful_no_nat_mark,
            self.stateful_nat_mark,
            self.route_no_nat_mark,
            self.route_nat_mark,
            self.return_mark,
        )
        if any(type(value) is not int or not 1 <= value <= 0xFFFFFFFF for value in values):
            raise HostBoundaryBehaviorLinuxError(
                "behavior class/return marks must be integers in [1, 2^32-1]"
            )
        if len(set(values)) != len(values):
            raise HostBoundaryBehaviorLinuxError(
                "behavior class marks and return mark must be distinct"
            )

    def class_mark(self, lane: HostBoundaryBehaviorLane) -> int:
        if lane is HostBoundaryBehaviorLane.STATEFUL_NO_NAT:
            return self.stateful_no_nat_mark
        if lane is HostBoundaryBehaviorLane.STATEFUL_NAT:
            return self.stateful_nat_mark
        if lane is HostBoundaryBehaviorLane.ROUTE_NO_NAT:
            return self.route_no_nat_mark
        if lane is HostBoundaryBehaviorLane.ROUTE_NAT:
            return self.route_nat_mark
        raise HostBoundaryBehaviorLinuxError("unsupported host-boundary behavior lane")


@dataclass(frozen=True, slots=True)
class HostBoundaryBehaviorHostLane:
    lane: HostBoundaryBehaviorLane
    host_interface: str

    def __post_init__(self) -> None:
        if not isinstance(self.lane, HostBoundaryBehaviorLane):
            raise HostBoundaryBehaviorLinuxError(
                "lane must be HostBoundaryBehaviorLane"
            )
        if not isinstance(self.host_interface, str) or not self.host_interface:
            raise HostBoundaryBehaviorLinuxError(
                "host_interface must be non-empty text"
            )


@dataclass(frozen=True, slots=True)
class HostBoundaryBehaviorLaneNftSpec:
    lane: HostBoundaryBehaviorLane
    host_interface: str
    class_mark: int


@dataclass(frozen=True, slots=True)
class HostBoundaryBehaviorNftSpec:
    lanes: tuple[HostBoundaryBehaviorLaneNftSpec, ...]
    return_mark: int

    def __post_init__(self) -> None:
        if not self.lanes:
            raise HostBoundaryBehaviorLinuxError(
                "host behavior owner requires at least one active lane"
            )
        lane_ids = tuple(item.lane for item in self.lanes)
        interfaces = tuple(item.host_interface for item in self.lanes)
        marks = tuple(item.class_mark for item in self.lanes)
        if len(set(lane_ids)) != len(lane_ids):
            raise HostBoundaryBehaviorLinuxError("duplicate active behavior lane")
        if len(set(interfaces)) != len(interfaces):
            raise HostBoundaryBehaviorLinuxError(
                "active behavior lanes require distinct host interfaces"
            )
        if len(set(marks)) != len(marks):
            raise HostBoundaryBehaviorLinuxError(
                "active behavior lanes require distinct class marks"
            )
        if type(self.return_mark) is not int or not 1 <= self.return_mark <= 0xFFFFFFFF:
            raise HostBoundaryBehaviorLinuxError(
                "return_mark must be an integer in [1, 2^32-1]"
            )
        if self.return_mark in marks:
            raise HostBoundaryBehaviorLinuxError(
                "return mark must differ from behavior class marks"
            )


def build_host_boundary_behavior_nft_desired(
    intents: Iterable[HostBoundaryBehaviorIntent],
    host_lanes: Iterable[HostBoundaryBehaviorHostLane],
    allocation: HostBoundaryBehaviorLinuxAllocation,
) -> HostBoundaryBehaviorNftSpec | None:
    if not isinstance(allocation, HostBoundaryBehaviorLinuxAllocation):
        raise HostBoundaryBehaviorLinuxError(
            "allocation must be HostBoundaryBehaviorLinuxAllocation"
        )

    current_intents = tuple(intents)
    if any(not isinstance(item, HostBoundaryBehaviorIntent) for item in current_intents):
        raise HostBoundaryBehaviorLinuxError(
            "intents must contain HostBoundaryBehaviorIntent"
        )
    profile_ids = tuple(item.profile_id for item in current_intents)
    if len(set(profile_ids)) != len(profile_ids):
        raise HostBoundaryBehaviorLinuxError(
            "behavior intents contain duplicate Profile"
        )

    active_lanes = frozenset(item.lane for item in current_intents)
    if not active_lanes:
        return None

    by_lane: dict[HostBoundaryBehaviorLane, HostBoundaryBehaviorHostLane] = {}
    for item in host_lanes:
        if not isinstance(item, HostBoundaryBehaviorHostLane):
            raise HostBoundaryBehaviorLinuxError(
                "host_lanes must contain HostBoundaryBehaviorHostLane"
            )
        if item.lane in by_lane:
            raise HostBoundaryBehaviorLinuxError(
                f"duplicate host interface for behavior lane {item.lane.value!r}"
            )
        by_lane[item.lane] = item

    missing = active_lanes - set(by_lane)
    if missing:
        raise HostBoundaryBehaviorLinuxError(
            "missing host interface for active behavior lanes: "
            + ", ".join(sorted(item.value for item in missing))
        )

    lanes = tuple(
        HostBoundaryBehaviorLaneNftSpec(
            lane=lane,
            host_interface=by_lane[lane].host_interface,
            class_mark=allocation.class_mark(lane),
        )
        for lane in sorted(active_lanes, key=lambda item: item.value)
    )
    return HostBoundaryBehaviorNftSpec(
        lanes=lanes,
        return_mark=allocation.return_mark,
    )


def render_host_boundary_behavior_nft(spec: HostBoundaryBehaviorNftSpec) -> str:
    if not isinstance(spec, HostBoundaryBehaviorNftSpec):
        raise HostBoundaryBehaviorLinuxError(
            "spec must be HostBoundaryBehaviorNftSpec"
        )

    lines = [
        f'add table inet {HOST_BEHAVIOR_TABLE} {{ comment "{HOST_BEHAVIOR_TABLE_COMMENT}"; }}',
        (
            f'add chain inet {HOST_BEHAVIOR_TABLE} prerouting '
            '{ type filter hook prerouting priority mangle; policy accept; '
            f'comment "{HOST_BEHAVIOR_PREROUTING_COMMENT}"; }}'
        ),
        (
            f'add chain inet {HOST_BEHAVIOR_TABLE} output '
            '{ type route hook output priority mangle; policy accept; '
            f'comment "{HOST_BEHAVIOR_OUTPUT_COMMENT}"; }}'
        ),
        (
            f'add chain inet {HOST_BEHAVIOR_TABLE} postrouting '
            '{ type nat hook postrouting priority srcnat; policy accept; '
            f'comment "{HOST_BEHAVIOR_POSTROUTING_COMMENT}"; }}'
        ),
    ]

    for item in spec.lanes:
        safe_if = _quote(item.host_interface)
        mark_hex = hex(item.class_mark)
        lines.append(
            f'add rule inet {HOST_BEHAVIOR_TABLE} prerouting '
            f'iifname "{safe_if}" ct state new ct mark set {mark_hex} return '
            f'comment "{_classify_comment(item.lane)}"'
        )
        # All packets arriving from a behavior lane must leave this owner before
        # stateful return-mark restore rules. Otherwise subsequent packets in
        # the original VPN->ordinary direction would be steered back to stack.
        lines.append(
            f'add rule inet {HOST_BEHAVIOR_TABLE} prerouting '
            f'iifname "{safe_if}" return '
            f'comment "{_lane_return_comment(item.lane)}"'
        )

    for item in spec.lanes:
        if not _stateful(item.lane):
            continue
        lines.append(
            f'add rule inet {HOST_BEHAVIOR_TABLE} prerouting '
            f'ct mark {hex(item.class_mark)} '
            f'meta mark set {hex(spec.return_mark)} '
            f'comment "{_prerouting_restore_comment(item.lane)}"'
        )
        lines.append(
            f'add rule inet {HOST_BEHAVIOR_TABLE} output '
            f'ct mark {hex(item.class_mark)} '
            f'meta mark set {hex(spec.return_mark)} '
            f'comment "{_output_restore_comment(item.lane)}"'
        )

    for item in spec.lanes:
        if not _nat(item.lane):
            continue
        lines.append(
            f'add rule inet {HOST_BEHAVIOR_TABLE} postrouting '
            f'ct mark {hex(item.class_mark)} masquerade '
            f'comment "{_nat_comment(item.lane)}"'
        )

    lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class HostBoundaryBehaviorNftObservation:
    table_present: bool
    exact: bool
    conflicts: tuple[str, ...]


@dataclass(slots=True)
class LinuxHostBoundaryBehaviorNftBackend:
    runner: NftScriptRunner

    def observe(
        self,
        desired: HostBoundaryBehaviorNftSpec | None,
    ) -> HostBoundaryBehaviorNftObservation:
        if desired is not None and not isinstance(
            desired,
            HostBoundaryBehaviorNftSpec,
        ):
            raise HostBoundaryBehaviorLinuxError(
                "desired must be HostBoundaryBehaviorNftSpec or None"
            )
        raw = self.runner.run(("nft", "-j", "-y", "list", "ruleset"))
        return parse_host_boundary_behavior_nft_observation(raw, desired)

    def replace(self, desired: HostBoundaryBehaviorNftSpec | None) -> None:
        current = self.observe(desired)
        if current.conflicts:
            raise RuntimeError(
                "host behavior nft owner conflict: "
                + "; ".join(current.conflicts)
            )
        lines = []
        if current.table_present:
            lines.append(f"delete table inet {HOST_BEHAVIOR_TABLE}")
        if desired is not None:
            lines.append(render_host_boundary_behavior_nft(desired))
        if not lines:
            return
        self.runner.run_script(
            ("nft", "-f", "-"),
            "\n".join(lines).rstrip() + "\n",
        )


def converge_host_boundary_behavior_nft_once(
    backend: LinuxHostBoundaryBehaviorNftBackend,
    desired: HostBoundaryBehaviorNftSpec | None,
) -> HostBoundaryBehaviorNftObservation:
    if not isinstance(backend, LinuxHostBoundaryBehaviorNftBackend):
        raise ValueError(
            "backend must be LinuxHostBoundaryBehaviorNftBackend"
        )
    initial = backend.observe(desired)
    if initial.conflicts:
        raise RuntimeError(
            "host behavior nft owner conflict: "
            + "; ".join(initial.conflicts)
        )
    if initial.exact:
        return initial
    backend.replace(desired)
    final = backend.observe(desired)
    if final.conflicts:
        raise RuntimeError(
            "host behavior nft postcondition conflict: "
            + "; ".join(final.conflicts)
        )
    if not final.exact:
        raise RuntimeError(
            "host behavior nft fresh postcondition does not match desired state"
        )
    return final


def parse_host_boundary_behavior_nft_observation(
    raw: str,
    desired: HostBoundaryBehaviorNftSpec | None,
) -> HostBoundaryBehaviorNftObservation:
    try:
        root = json.loads(raw)
    except (TypeError, ValueError):
        raise HostBoundaryBehaviorLinuxError(
            "invalid host behavior nft JSON"
        ) from None
    rows = root.get("nftables") if isinstance(root, dict) else None
    if not isinstance(rows, list):
        raise HostBoundaryBehaviorLinuxError(
            "host behavior nft JSON must contain nftables array"
        )

    tables: list[dict] = []
    chains: list[dict] = []
    rules: list[dict] = []
    conflicts: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or len(row) != 1:
            continue
        kind, payload = next(iter(row.items()))
        if kind == "metainfo" or not isinstance(payload, dict):
            continue
        if payload.get("family") != "inet":
            continue
        belongs = (
            kind == "table" and payload.get("name") == HOST_BEHAVIOR_TABLE
        ) or payload.get("table") == HOST_BEHAVIOR_TABLE
        if not belongs:
            continue
        if kind == "table":
            tables.append(payload)
        elif kind == "chain":
            chains.append(payload)
        elif kind == "rule":
            rules.append(payload)
        else:
            conflicts.append(
                f"unsupported object {kind!r} in host behavior table"
            )

    if not tables and not chains and not rules and not conflicts:
        return HostBoundaryBehaviorNftObservation(
            table_present=False,
            exact=desired is None,
            conflicts=(),
        )

    if len(tables) != 1:
        conflicts.append("host behavior table is missing or duplicated")
    elif tables[0].get("comment") != HOST_BEHAVIOR_TABLE_COMMENT:
        conflicts.append("host behavior table owner comment mismatch")

    expected_chains = {
        "prerouting": ("filter", "prerouting", -150, HOST_BEHAVIOR_PREROUTING_COMMENT),
        "output": ("route", "output", -150, HOST_BEHAVIOR_OUTPUT_COMMENT),
        "postrouting": ("nat", "postrouting", 100, HOST_BEHAVIOR_POSTROUTING_COMMENT),
    }
    by_chain: dict[str, dict] = {}
    for row in chains:
        name = row.get("name")
        if not isinstance(name, str) or name in by_chain:
            conflicts.append("host behavior chain identity is invalid or duplicated")
            continue
        by_chain[name] = row
    if set(by_chain) != set(expected_chains):
        conflicts.append("host behavior chain set does not match owner contract")
    for name, (chain_type, hook, priority, comment) in expected_chains.items():
        row = by_chain.get(name)
        if row is None:
            continue
        if (
            row.get("type") != chain_type
            or row.get("hook") != hook
            or row.get("prio") != priority
            or row.get("policy") != "accept"
            or row.get("comment") != comment
        ):
            conflicts.append(f"host behavior chain {name!r} shape mismatch")

    expected_by_chain = (
        _expected_rule_comments_by_chain(desired)
        if desired is not None
        else {}
    )
    actual_by_chain: dict[str, list[str]] = {}
    all_comments: list[str] = []
    for row in rules:
        comment = row.get("comment")
        chain = row.get("chain")
        if not isinstance(comment, str):
            conflicts.append("host behavior rule has no owner comment")
            continue
        if not isinstance(chain, str):
            conflicts.append("host behavior rule has no chain identity")
            continue
        all_comments.append(comment)
        actual_by_chain.setdefault(chain, []).append(comment)
        if not comment.startswith("vpn-gate:ng3:host-behavior-"):
            conflicts.append("foreign rule exists in owned host behavior table")

    comments_match = (
        desired is not None
        and set(all_comments)
        == {
            comment
            for comments in expected_by_chain.values()
            for comment in comments
        }
        and all(
            actual_by_chain.get(chain, []) == list(expected)
            for chain, expected in expected_by_chain.items()
        )
        and set(actual_by_chain) == set(expected_by_chain)
    )
    if comments_match and not conflicts:
        _validate_rule_shapes(rules, desired, conflicts)

    return HostBoundaryBehaviorNftObservation(
        table_present=True,
        exact=(
            not conflicts
            and comments_match
            and len(tables) == 1
            and set(by_chain) == set(expected_chains)
        ),
        conflicts=tuple(conflicts),
    )


def _expected_rule_comments_by_chain(
    desired: HostBoundaryBehaviorNftSpec,
) -> dict[str, tuple[str, ...]]:
    prerouting: list[str] = []
    output: list[str] = []
    postrouting: list[str] = []
    for item in desired.lanes:
        prerouting.extend(
            (
                _classify_comment(item.lane),
                _lane_return_comment(item.lane),
            )
        )
    for item in desired.lanes:
        if _stateful(item.lane):
            prerouting.append(_prerouting_restore_comment(item.lane))
            output.append(_output_restore_comment(item.lane))
    for item in desired.lanes:
        if _nat(item.lane):
            postrouting.append(_nat_comment(item.lane))
    return {
        "prerouting": tuple(prerouting),
        "output": tuple(output),
        "postrouting": tuple(postrouting),
    }


def _validate_rule_shapes(
    rules: list[dict],
    desired: HostBoundaryBehaviorNftSpec,
    conflicts: list[str],
) -> None:
    expected_count = sum(
        len(items)
        for items in _expected_rule_comments_by_chain(desired).values()
    )
    if len(rules) != expected_count:
        conflicts.append("host behavior rule count mismatch")
        return

    by_comment = {row.get("comment"): row for row in rules}
    for item in desired.lanes:
        classify = by_comment.get(_classify_comment(item.lane), {})
        classify_blob = json.dumps(classify.get("expr"), sort_keys=True)
        if (
            classify.get("chain") != "prerouting"
            or item.host_interface not in classify_blob
            or "new" not in classify_blob
            or "ct" not in classify_blob
            or str(item.class_mark) not in classify_blob
            or "return" not in classify_blob
        ):
            conflicts.append(
                f"behavior lane {item.lane.value!r} classifier shape mismatch"
            )

        lane_return = by_comment.get(_lane_return_comment(item.lane), {})
        lane_return_blob = json.dumps(lane_return.get("expr"), sort_keys=True)
        if (
            lane_return.get("chain") != "prerouting"
            or item.host_interface not in lane_return_blob
            or "return" not in lane_return_blob
        ):
            conflicts.append(
                f"behavior lane {item.lane.value!r} ingress-return shape mismatch"
            )

        if _stateful(item.lane):
            for comment, chain in (
                (_prerouting_restore_comment(item.lane), "prerouting"),
                (_output_restore_comment(item.lane), "output"),
            ):
                row = by_comment.get(comment, {})
                blob = json.dumps(row.get("expr"), sort_keys=True)
                if (
                    row.get("chain") != chain
                    or "ct" not in blob
                    or "meta" not in blob
                    or str(item.class_mark) not in blob
                    or str(desired.return_mark) not in blob
                ):
                    conflicts.append(
                        f"behavior lane {item.lane.value!r} {chain} return shape mismatch"
                    )

        if _nat(item.lane):
            row = by_comment.get(_nat_comment(item.lane), {})
            blob = json.dumps(row.get("expr"), sort_keys=True)
            if (
                row.get("chain") != "postrouting"
                or "ct" not in blob
                or str(item.class_mark) not in blob
                or "masquerade" not in blob
            ):
                conflicts.append(
                    f"behavior lane {item.lane.value!r} NAT shape mismatch"
                )


def _stateful(lane: HostBoundaryBehaviorLane) -> bool:
    return lane in {
        HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
        HostBoundaryBehaviorLane.STATEFUL_NAT,
    }


def _nat(lane: HostBoundaryBehaviorLane) -> bool:
    return lane in {
        HostBoundaryBehaviorLane.STATEFUL_NAT,
        HostBoundaryBehaviorLane.ROUTE_NAT,
    }


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _lane_suffix(lane: HostBoundaryBehaviorLane) -> str:
    return lane.value.replace("_", "-")


def _classify_comment(lane: HostBoundaryBehaviorLane) -> str:
    return f"vpn-gate:ng3:host-behavior-classify-v1:{_lane_suffix(lane)}"


def _lane_return_comment(lane: HostBoundaryBehaviorLane) -> str:
    return f"vpn-gate:ng3:host-behavior-lane-return-v1:{_lane_suffix(lane)}"


def _prerouting_restore_comment(lane: HostBoundaryBehaviorLane) -> str:
    return f"vpn-gate:ng3:host-behavior-preroute-return-v1:{_lane_suffix(lane)}"


def _output_restore_comment(lane: HostBoundaryBehaviorLane) -> str:
    return f"vpn-gate:ng3:host-behavior-output-return-v1:{_lane_suffix(lane)}"


def _nat_comment(lane: HostBoundaryBehaviorLane) -> str:
    return f"vpn-gate:ng3:host-behavior-nat-v1:{_lane_suffix(lane)}"
