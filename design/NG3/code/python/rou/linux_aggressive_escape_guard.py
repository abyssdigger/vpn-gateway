"""Linux escape-protection state owned inside E.004.

Architecture: E.004 AggressiveHostRoutingEnforcer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network
import json

from .linux_nft_scaffold import NftScriptRunner


AGGRESSIVE_GUARD_FAMILY = "inet"
AGGRESSIVE_GUARD_TABLE = "vpn_gate_aggressive_guard"
AGGRESSIVE_GUARD_OWNER_COMMENT = "vpn-gate:ng3:aggressive-guard-v1"
_OUTPUT_LOCAL_COMMENT = "vpn-gate:ng3:aggressive-output-local-v1"
_FORWARD_RETURN_COMMENT = "vpn-gate:ng3:aggressive-forward-return-v1"
_OUTPUT_PREFIX = "vpn-gate:ng3:aggressive-output:"
_FORWARD_PREFIX = "vpn-gate:ng3:aggressive-forward:"


class AggressiveEscapeGuardState(str, Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"


@dataclass(frozen=True, slots=True)
class AggressiveEscapeGuardDesired:
    state: AggressiveEscapeGuardState
    boundary_interface: str | None = None
    managed_destinations: tuple[IPv4Network, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, AggressiveEscapeGuardState):
            raise ValueError("state must be AggressiveEscapeGuardState")
        if self.state is AggressiveEscapeGuardState.DISABLED:
            if self.boundary_interface is not None or self.managed_destinations:
                raise ValueError("disabled guard carries no boundary or destinations")
            return
        if not isinstance(self.boundary_interface, str) or not self.boundary_interface:
            raise ValueError("enabled guard requires boundary_interface")
        if (
            not isinstance(self.managed_destinations, tuple)
            or not self.managed_destinations
            or any(
                not isinstance(item, IPv4Network)
                for item in self.managed_destinations
            )
        ):
            raise ValueError("enabled guard requires IPv4 managed_destinations")
        normalized = _normalize_networks(self.managed_destinations)
        object.__setattr__(self, "managed_destinations", normalized)


class AggressiveEscapeGuardObservationStatus(str, Enum):
    ABSENT = "absent"
    EXACT = "exact"
    OWNED_DRIFT = "owned_drift"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class AggressiveEscapeGuardObservation:
    status: AggressiveEscapeGuardObservationStatus
    conflict_reason: str | None = None

    @property
    def owned(self) -> bool:
        return self.status in {
            AggressiveEscapeGuardObservationStatus.EXACT,
            AggressiveEscapeGuardObservationStatus.OWNED_DRIFT,
        }

    def matches(self, desired: AggressiveEscapeGuardDesired) -> bool:
        if desired.state is AggressiveEscapeGuardState.DISABLED:
            return self.status is AggressiveEscapeGuardObservationStatus.ABSENT
        return self.status is AggressiveEscapeGuardObservationStatus.EXACT


@dataclass(slots=True)
class LinuxAggressiveEscapeGuardDriver:
    runner: NftScriptRunner
    network_namespace: str | None = None

    def __post_init__(self) -> None:
        if self.network_namespace is not None and (
            not isinstance(self.network_namespace, str)
            or not self.network_namespace
        ):
            raise ValueError("network_namespace must be non-empty text or None")

    def observe(
        self,
        desired: AggressiveEscapeGuardDesired,
    ) -> AggressiveEscapeGuardObservation:
        raw = self.runner.run(self._cmd("nft", "-j", "list", "ruleset"))
        return parse_aggressive_escape_guard_ruleset(raw, desired)

    def apply(
        self,
        desired: AggressiveEscapeGuardDesired,
        initial: AggressiveEscapeGuardObservation,
    ) -> None:
        if not isinstance(desired, AggressiveEscapeGuardDesired):
            raise ValueError("desired must be AggressiveEscapeGuardDesired")
        if not isinstance(initial, AggressiveEscapeGuardObservation):
            raise ValueError("initial must be AggressiveEscapeGuardObservation")
        if initial.status is AggressiveEscapeGuardObservationStatus.CONFLICT:
            raise RuntimeError("refusing to mutate conflicting aggressive guard table")

        if desired.state is AggressiveEscapeGuardState.DISABLED:
            if not initial.owned:
                raise RuntimeError("guard disable requires proven-owned table")
            script = (
                f"delete table {AGGRESSIVE_GUARD_FAMILY} "
                f"{AGGRESSIVE_GUARD_TABLE}\n"
            )
        else:
            prefix = ""
            if initial.owned:
                prefix = (
                    f"delete table {AGGRESSIVE_GUARD_FAMILY} "
                    f"{AGGRESSIVE_GUARD_TABLE}\n"
                )
            elif initial.status is not AggressiveEscapeGuardObservationStatus.ABSENT:
                raise RuntimeError("guard enable requires absent or owned state")
            script = prefix + _enabled_script(desired)

        self.runner.run_script(self._cmd("nft", "-f", "-"), script)

    def _cmd(self, *args: str) -> tuple[str, ...]:
        if self.network_namespace is None:
            return tuple(args)
        return ("ip", "netns", "exec", self.network_namespace, *args)


def converge_aggressive_escape_guard_once(
    driver: LinuxAggressiveEscapeGuardDriver,
    desired: AggressiveEscapeGuardDesired,
) -> AggressiveEscapeGuardObservation:
    initial = driver.observe(desired)
    if initial.status is AggressiveEscapeGuardObservationStatus.CONFLICT:
        raise RuntimeError(initial.conflict_reason or "aggressive guard ownership conflict")
    if initial.matches(desired):
        final = driver.observe(desired)
        if not final.matches(desired):
            raise RuntimeError("aggressive guard drifted during no-op confirmation")
        return final

    driver.apply(desired, initial)
    final = driver.observe(desired)
    if final.status is AggressiveEscapeGuardObservationStatus.CONFLICT:
        raise RuntimeError(final.conflict_reason or "aggressive guard ownership conflict")
    if not final.matches(desired):
        raise RuntimeError("fresh aggressive guard postcondition is not exact")
    return final


def parse_aggressive_escape_guard_ruleset(
    text: str,
    desired: AggressiveEscapeGuardDesired,
) -> AggressiveEscapeGuardObservation:
    if not isinstance(desired, AggressiveEscapeGuardDesired):
        raise ValueError("desired must be AggressiveEscapeGuardDesired")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid nft ruleset JSON: {exc}") from None
    rows = document.get("nftables") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        raise ValueError("nft ruleset JSON must contain nftables array")

    tables: list[dict] = []
    objects: list[tuple[str, dict]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or len(row) != 1:
            raise ValueError(f"nftables row {index} must be a single-key object")
        kind, payload = next(iter(row.items()))
        if kind == "metainfo":
            continue
        if not isinstance(payload, dict):
            raise ValueError(f"nft {kind!r} payload must be an object")
        if (
            kind == "table"
            and payload.get("family") == AGGRESSIVE_GUARD_FAMILY
            and payload.get("name") == AGGRESSIVE_GUARD_TABLE
        ):
            tables.append(payload)
        elif (
            payload.get("family") == AGGRESSIVE_GUARD_FAMILY
            and payload.get("table") == AGGRESSIVE_GUARD_TABLE
        ):
            objects.append((kind, payload))

    if len(tables) > 1:
        return _conflict("duplicate aggressive guard table declarations")
    if not tables:
        if objects:
            return _conflict("aggressive guard objects exist without table")
        return AggressiveEscapeGuardObservation(
            AggressiveEscapeGuardObservationStatus.ABSENT
        )

    table = _without_handle(tables[0])
    if table.get("comment") != AGGRESSIVE_GUARD_OWNER_COMMENT:
        return _conflict("aggressive guard owner marker is absent or different")
    expected_table = {
        "family": AGGRESSIVE_GUARD_FAMILY,
        "name": AGGRESSIVE_GUARD_TABLE,
        "comment": AGGRESSIVE_GUARD_OWNER_COMMENT,
    }
    if table != expected_table:
        return AggressiveEscapeGuardObservation(
            AggressiveEscapeGuardObservationStatus.OWNED_DRIFT
        )
    if desired.state is AggressiveEscapeGuardState.DISABLED:
        return AggressiveEscapeGuardObservation(
            AggressiveEscapeGuardObservationStatus.OWNED_DRIFT
        )

    chains: dict[str, dict] = {}
    rules: dict[str, dict] = {}
    for kind, payload in objects:
        normalized = _without_handle(payload)
        if kind == "chain":
            name = normalized.get("name")
            if not isinstance(name, str) or name in chains:
                return _owned_drift()
            chains[name] = normalized
        elif kind == "rule":
            comment = normalized.get("comment")
            if not isinstance(comment, str) or comment in rules:
                return _owned_drift()
            rules[comment] = normalized
        else:
            return _owned_drift()

    expected_chains = {
        "protect_output": _chain("protect_output", "output"),
        "protect_forward": _chain("protect_forward", "forward"),
    }
    if chains != expected_chains:
        return _owned_drift()

    boundary = desired.boundary_interface
    assert boundary is not None
    expected_comments = {_OUTPUT_LOCAL_COMMENT, _FORWARD_RETURN_COMMENT}
    for network in desired.managed_destinations:
        expected_comments.add(_OUTPUT_PREFIX + network.with_prefixlen)
        expected_comments.add(_FORWARD_PREFIX + network.with_prefixlen)
    if set(rules) != expected_comments:
        return _owned_drift()

    if not _is_output_local_rule(rules[_OUTPUT_LOCAL_COMMENT]):
        return _owned_drift()
    if not _is_forward_return_rule(rules[_FORWARD_RETURN_COMMENT], boundary):
        return _owned_drift()
    for network in desired.managed_destinations:
        if not _is_escape_drop_rule(
            rules[_OUTPUT_PREFIX + network.with_prefixlen],
            "protect_output",
            boundary,
            network,
        ):
            return _owned_drift()
        if not _is_escape_drop_rule(
            rules[_FORWARD_PREFIX + network.with_prefixlen],
            "protect_forward",
            boundary,
            network,
        ):
            return _owned_drift()

    return AggressiveEscapeGuardObservation(
        AggressiveEscapeGuardObservationStatus.EXACT
    )


def _chain(name: str, hook: str) -> dict:
    return {
        "family": AGGRESSIVE_GUARD_FAMILY,
        "table": AGGRESSIVE_GUARD_TABLE,
        "name": name,
        "type": "filter",
        "hook": hook,
        "prio": 100,
        "policy": "accept",
    }


def _is_output_local_rule(payload: dict) -> bool:
    if payload.get("chain") != "protect_output":
        return False
    expr = payload.get("expr")
    return (
        isinstance(expr, list)
        and len(expr) == 2
        and _is_fib_local_match(expr[0])
        and expr[1] == {"accept": None}
    )


def _is_forward_return_rule(payload: dict, boundary: str) -> bool:
    if payload.get("chain") != "protect_forward":
        return False
    expr = payload.get("expr")
    return (
        isinstance(expr, list)
        and len(expr) == 2
        and _is_meta_match(expr[0], "iifname", "==", boundary)
        and expr[1] == {"accept": None}
    )


def _is_escape_drop_rule(
    payload: dict,
    chain: str,
    boundary: str,
    network: IPv4Network,
) -> bool:
    if payload.get("chain") != chain:
        return False
    expr = payload.get("expr")
    if not isinstance(expr, list):
        return False
    expected_len = 2 if network.prefixlen == 0 else 3
    if len(expr) != expected_len or expr[-1] != {"drop": None}:
        return False
    offset = 0
    if network.prefixlen != 0:
        if not _is_destination_match(expr[0], network):
            return False
        offset = 1
    return _is_meta_match(expr[offset], "oifname", "!=", boundary)


def _is_fib_local_match(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    match = item.get("match")
    if not isinstance(match, dict) or match.get("op") != "==":
        return False
    left = match.get("left")
    if not isinstance(left, dict):
        return False
    fib = left.get("fib")
    return (
        isinstance(fib, dict)
        and fib.get("result") == "type"
        and fib.get("flags") == ["daddr"]
        and match.get("right") == "local"
    )


def _is_meta_match(
    item: object,
    key: str,
    op: str,
    value: str,
) -> bool:
    if not isinstance(item, dict):
        return False
    match = item.get("match")
    if not isinstance(match, dict) or match.get("op") != op:
        return False
    left = match.get("left")
    return (
        isinstance(left, dict)
        and left.get("meta") == {"key": key}
        and match.get("right") == value
    )


def _is_destination_match(item: object, network: IPv4Network) -> bool:
    if not isinstance(item, dict):
        return False
    match = item.get("match")
    if not isinstance(match, dict) or match.get("op") != "==":
        return False
    left = match.get("left")
    if not (
        isinstance(left, dict)
        and left.get("payload") == {"protocol": "ip", "field": "daddr"}
    ):
        return False
    right = match.get("right")
    if network.prefixlen == 32:
        return right == str(network.network_address) or right == {
            "prefix": {"addr": str(network.network_address), "len": 32}
        }
    return right == {
        "prefix": {
            "addr": str(network.network_address),
            "len": network.prefixlen,
        }
    }


def _without_handle(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "handle"}


def _normalize_networks(
    networks: tuple[IPv4Network, ...],
) -> tuple[IPv4Network, ...]:
    unique = set(networks)
    default = IPv4Network("0.0.0.0/0")
    if default in unique:
        return (default,)
    return tuple(
        sorted(
            unique,
            key=lambda item: (-item.prefixlen, int(item.network_address)),
        )
    )


def _owned_drift() -> AggressiveEscapeGuardObservation:
    return AggressiveEscapeGuardObservation(
        AggressiveEscapeGuardObservationStatus.OWNED_DRIFT
    )


def _conflict(reason: str) -> AggressiveEscapeGuardObservation:
    return AggressiveEscapeGuardObservation(
        AggressiveEscapeGuardObservationStatus.CONFLICT,
        reason,
    )


def _enabled_script(desired: AggressiveEscapeGuardDesired) -> str:
    boundary = desired.boundary_interface
    assert boundary is not None
    quoted = json.dumps(boundary)
    lines = [
        f"table inet {AGGRESSIVE_GUARD_TABLE} {{",
        f'    comment "{AGGRESSIVE_GUARD_OWNER_COMMENT}"',
        "    chain protect_output {",
        "        type filter hook output priority 100; policy accept;",
        (
            "        fib daddr type local accept "
            f'comment "{_OUTPUT_LOCAL_COMMENT}"'
        ),
    ]
    for network in desired.managed_destinations:
        selector = (
            ""
            if network.prefixlen == 0
            else f"ip daddr {network.with_prefixlen} "
        )
        lines.append(
            "        "
            + selector
            + f"oifname != {quoted} drop "
            + f'comment "{_OUTPUT_PREFIX}{network.with_prefixlen}"'
        )
    lines.extend(
        (
            "    }",
            "    chain protect_forward {",
            "        type filter hook forward priority 100; policy accept;",
            (
                f"        iifname {quoted} accept "
                f'comment "{_FORWARD_RETURN_COMMENT}"'
            ),
        )
    )
    for network in desired.managed_destinations:
        selector = (
            ""
            if network.prefixlen == 0
            else f"ip daddr {network.with_prefixlen} "
        )
        lines.append(
            "        "
            + selector
            + f"oifname != {quoted} drop "
            + f'comment "{_FORWARD_PREFIX}{network.with_prefixlen}"'
        )
    lines.extend(("    }", "}"))
    return "\n".join(lines) + "\n"
