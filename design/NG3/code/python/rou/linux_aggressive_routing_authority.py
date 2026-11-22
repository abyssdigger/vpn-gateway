"""Fresh Linux authority verification for aggressive host routing.

Architecture: E.004 AggressiveHostRoutingEnforcer.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from .linux_host_managed_routing import HostManagedRoutingLinuxDesired
from .linux_host_managed_routing_backend import LinuxHostManagedRoutingDriver


@dataclass(frozen=True, slots=True)
class AggressiveRoutingAuthorityObservation:
    owner_exact: bool
    authority_confirmed: bool
    conflicts: tuple[str, ...]

    @property
    def confirmed(self) -> bool:
        return self.owner_exact and self.authority_confirmed and not self.conflicts


def observe_aggressive_routing_authority(
    driver: LinuxHostManagedRoutingDriver,
    desired: HostManagedRoutingLinuxDesired,
) -> AggressiveRoutingAuthorityObservation:
    if not isinstance(driver, LinuxHostManagedRoutingDriver):
        raise ValueError("driver must be LinuxHostManagedRoutingDriver")
    if not isinstance(desired, HostManagedRoutingLinuxDesired):
        raise ValueError("desired must be HostManagedRoutingLinuxDesired")
    owner = driver.observe(desired)
    conflicts = list(owner.conflicts)
    if not owner.exact:
        conflicts.append("VPN-GATE-owned aggressive routing state is not exact")

    dispatch = desired.dispatch
    bypass = desired.bypass
    if dispatch is None or bypass is None:
        conflicts.append("active aggressive desired state has no dispatch/bypass")
        return AggressiveRoutingAuthorityObservation(
            owner_exact=owner.exact,
            authority_confirmed=False,
            conflicts=tuple(conflicts),
        )

    rows = _json_array(
        driver.runner.run(driver._cmd("ip", "-j", "-4", "rule", "show")),
    )
    for row in rows:
        priority = _decimal(row.get("priority"))
        if priority is None:
            conflicts.append("RPDB rule has no representable priority")
            continue
        if priority >= dispatch.priority:
            continue
        if _is_standard_local_rule(row):
            continue
        if priority == bypass.priority and _is_owned_bypass(
            row,
            bypass.interface,
            driver.allocation.rule_protocol,
        ):
            continue
        conflicts.append(
            f"RPDB rule priority {priority} can precede aggressive dispatch"
        )

    return AggressiveRoutingAuthorityObservation(
        owner_exact=owner.exact,
        authority_confirmed=not conflicts,
        conflicts=tuple(conflicts),
    )


def _is_standard_local_rule(row: dict) -> bool:
    if _decimal(row.get("priority")) != 0:
        return False
    table = row.get("table", row.get("lookup"))
    if table not in ("local", 255, "255"):
        return False
    selectors = {
        "src", "src_len", "dst", "dst_len", "fwmark", "fwmask",
        "uidrange", "sport", "dport", "ipproto", "iif", "oif",
        "goto", "nop", "suppress_prefixlen", "suppress_prefixlength",
    }
    return not any(key in row for key in selectors)


def _is_owned_bypass(
    row: dict,
    interface: str,
    protocol: int,
) -> bool:
    if _decimal(row.get("protocol")) != protocol:
        return False
    if row.get("iif") != interface or "not" in row:
        return False
    table = row.get("table", row.get("lookup"))
    if table not in ("main", 254, "254"):
        return False
    forbidden = {
        "src", "src_len", "dst", "dst_len", "fwmark", "fwmask",
        "uidrange", "sport", "dport", "ipproto", "oif",
        "goto", "nop", "suppress_prefixlen", "suppress_prefixlength",
    }
    return not any(key in row for key in forbidden)


def _decimal(value: object) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _json_array(raw: str) -> list[dict]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise RuntimeError("invalid RPDB JSON") from None
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise RuntimeError("RPDB JSON must be an array of objects")
    return value
