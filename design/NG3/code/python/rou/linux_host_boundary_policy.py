"""Linux desired-state compiler for NG3 ordinary-host boundary routing.

The compiler is intentionally side-effect free. It turns the semantic host-boundary plan into
exact route/RPDB/nft desired objects. Mutation/observation remains a separate lower Driver.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from .host_boundary_policy import HostBoundaryPolicyPlan, HostReturnClassifierRule
from .host_underlay_route import HostUnderlayPin


class UnderlayPinningIncomplete(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HostBoundaryLinuxAllocation:
    mark: int
    return_table: int
    return_rule_priority: int
    route_protocol: int

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("mark", self.mark, 0xFFFFFFFF),
            ("return_table", self.return_table, 0xFFFFFFFF),
            ("return_rule_priority", self.return_rule_priority, 0xFFFFFFFF),
            ("route_protocol", self.route_protocol, 0xFF),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{label} must be an integer in [1, {maximum}]")


@dataclass(frozen=True, slots=True)
class HostBoundaryRouteSpec:
    destination: IPv4Network
    via: IPv4Address
    interface: str
    protocol: int


@dataclass(frozen=True, slots=True)
class HostBoundaryReturnRouteSpec:
    via: IPv4Address
    interface: str
    table: int
    protocol: int


@dataclass(frozen=True, slots=True)
class HostBoundaryRuleSpec:
    mark: int
    table: int
    priority: int


@dataclass(frozen=True, slots=True)
class HostReturnNftSpec:
    interface: str
    mark: int
    classifier: tuple[HostReturnClassifierRule, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.interface, str) or not self.interface:
            raise ValueError("interface must be non-empty text")
        if type(self.mark) is not int or not 1 <= self.mark <= 0xFFFFFFFF:
            raise ValueError("mark must be an integer in [1, 2^32-1]")
        if not self.classifier:
            raise ValueError("classifier must be non-empty")
        if any(not isinstance(item, HostReturnClassifierRule) for item in self.classifier):
            raise ValueError("classifier must contain HostReturnClassifierRule values")


@dataclass(frozen=True, slots=True)
class HostBoundaryLinuxDesired:
    underlay_pins: tuple[HostUnderlayPin, ...]
    bootstrap_routes: tuple[HostBoundaryRouteSpec, ...]
    return_route: HostBoundaryReturnRouteSpec | None
    return_rule: HostBoundaryRuleSpec | None
    return_nft: HostReturnNftSpec | None

    @property
    def nft_script(self) -> str | None:
        if self.return_nft is None:
            return None
        return render_host_return_nft(self.return_nft)


def build_linux_host_boundary_desired(
    plan: HostBoundaryPolicyPlan,
    *,
    host_interface: str,
    inner_gateway: IPv4Address,
    allocation: HostBoundaryLinuxAllocation,
    required_underlay_endpoints: tuple[IPv4Address, ...] = (),
    underlay_pins: tuple[HostUnderlayPin, ...] = (),
) -> HostBoundaryLinuxDesired:
    if not isinstance(plan, HostBoundaryPolicyPlan):
        raise ValueError("plan must be HostBoundaryPolicyPlan")
    if not isinstance(host_interface, str) or not host_interface:
        raise ValueError("host_interface must be non-empty text")
    if not isinstance(inner_gateway, IPv4Address):
        raise ValueError("inner_gateway must be IPv4Address")
    if not isinstance(allocation, HostBoundaryLinuxAllocation):
        raise ValueError("allocation must be HostBoundaryLinuxAllocation")

    if any(not isinstance(item, IPv4Address) for item in required_underlay_endpoints):
        raise ValueError("required_underlay_endpoints must contain IPv4Address values")
    if any(not isinstance(item, HostUnderlayPin) for item in underlay_pins):
        raise ValueError("underlay_pins must contain HostUnderlayPin values")

    required = tuple(sorted(set(required_underlay_endpoints), key=int))
    observed_by_endpoint = {pin.endpoint: pin for pin in underlay_pins}
    if len(observed_by_endpoint) != len(underlay_pins):
        raise UnderlayPinningIncomplete("duplicate underlay endpoint pin")
    if tuple(sorted(observed_by_endpoint, key=int)) != required:
        raise UnderlayPinningIncomplete(
            "underlay pins must exactly cover every captured external VPN endpoint"
        )
    canonical_pins = tuple(observed_by_endpoint[item] for item in required)

    physical_destinations: set[IPv4Network] = set()
    for item in plan.bootstrap_routes:
        if item.destination.prefixlen == 0:
            physical_destinations.update(
                (
                    IPv4Network("0.0.0.0/1"),
                    IPv4Network("128.0.0.0/1"),
                )
            )
        else:
            physical_destinations.add(item.destination)

    bootstrap = tuple(
        HostBoundaryRouteSpec(
            destination=destination,
            via=inner_gateway,
            interface=host_interface,
            protocol=allocation.route_protocol,
        )
        for destination in sorted(
            physical_destinations,
            key=lambda value: (int(value.network_address), value.prefixlen),
        )
    )

    has_stateful = any(item.stateful_return for item in plan.return_classifier)
    if not has_stateful:
        return HostBoundaryLinuxDesired(
            underlay_pins=canonical_pins,
            bootstrap_routes=bootstrap,
            return_route=None,
            return_rule=None,
            return_nft=None,
        )

    return HostBoundaryLinuxDesired(
        underlay_pins=canonical_pins,
        bootstrap_routes=bootstrap,
        return_route=HostBoundaryReturnRouteSpec(
            via=inner_gateway,
            interface=host_interface,
            table=allocation.return_table,
            protocol=allocation.route_protocol,
        ),
        return_rule=HostBoundaryRuleSpec(
            mark=allocation.mark,
            table=allocation.return_table,
            priority=allocation.return_rule_priority,
        ),
        return_nft=HostReturnNftSpec(
            interface=host_interface,
            mark=allocation.mark,
            classifier=plan.return_classifier,
        ),
    )


HOST_RETURN_TABLE = "vpn_gate_host_return"
HOST_RETURN_TABLE_COMMENT = "vpn-gate:ng3:host-return-owner-v1"
HOST_RETURN_CLASSIFY_CHAIN_COMMENT = "vpn-gate:ng3:host-return-classify-v1"
HOST_RETURN_PREROUTING_CHAIN_COMMENT = "vpn-gate:ng3:host-return-prerouting-v1"
HOST_RETURN_OUTPUT_CHAIN_COMMENT = "vpn-gate:ng3:host-return-output-v1"
HOST_RETURN_INGRESS_RULE_COMMENT = "vpn-gate:ng3:host-return-ingress-v1"
HOST_RETURN_PREROUTE_RESTORE_COMMENT = "vpn-gate:ng3:host-return-preroute-restore-v1"
HOST_RETURN_OUTPUT_RESTORE_COMMENT = "vpn-gate:ng3:host-return-output-restore-v1"


def classifier_rule_comment(index: int, rule: HostReturnClassifierRule) -> str:
    mode = "stateful" if rule.stateful_return else "route"
    return (
        f"vpn-gate:ng3:host-return-classifier-v1:{index}:"
        f"{mode}:{rule.remote_prefix.with_prefixlen}"
    )


def render_host_return_nft(spec: HostReturnNftSpec) -> str:
    if not isinstance(spec, HostReturnNftSpec):
        raise ValueError("spec must be HostReturnNftSpec")
    safe_if = spec.interface.replace("\\", "\\\\").replace('"', '\\"')
    mark_hex = hex(spec.mark)
    lines = [
        f'add table inet {HOST_RETURN_TABLE} {{ comment "{HOST_RETURN_TABLE_COMMENT}"; }}',
        (
            f'add chain inet {HOST_RETURN_TABLE} classify_remote '
            f'{{ comment "{HOST_RETURN_CLASSIFY_CHAIN_COMMENT}"; }}'
        ),
        (
            f'add chain inet {HOST_RETURN_TABLE} prerouting '
            '{ type filter hook prerouting priority mangle; policy accept; '
            f'comment "{HOST_RETURN_PREROUTING_CHAIN_COMMENT}"; }}'
        ),
        (
            f'add chain inet {HOST_RETURN_TABLE} output '
            '{ type route hook output priority mangle; policy accept; '
            f'comment "{HOST_RETURN_OUTPUT_CHAIN_COMMENT}"; }}'
        ),
    ]
    for index, item in enumerate(spec.classifier):
        prefix = item.remote_prefix.with_prefixlen
        comment = classifier_rule_comment(index, item)
        if item.stateful_return:
            expr = f'ip saddr {prefix} ct state new ct mark set {mark_hex} return'
        else:
            expr = f'ip saddr {prefix} return'
        lines.append(
            f'add rule inet {HOST_RETURN_TABLE} classify_remote '
            f'{expr} comment "{comment}"'
        )
    lines.extend(
        (
            (
                f'add rule inet {HOST_RETURN_TABLE} prerouting '
                f'iifname "{safe_if}" jump classify_remote '
                f'comment "{HOST_RETURN_INGRESS_RULE_COMMENT}"'
            ),
            (
                f'add rule inet {HOST_RETURN_TABLE} prerouting '
                f'iifname != "{safe_if}" ct mark {mark_hex} meta mark set ct mark '
                f'comment "{HOST_RETURN_PREROUTE_RESTORE_COMMENT}"'
            ),
            (
                f'add rule inet {HOST_RETURN_TABLE} output '
                f'ct mark {mark_hex} meta mark set ct mark '
                f'comment "{HOST_RETURN_OUTPUT_RESTORE_COMMENT}"'
            ),
            '',
        )
    )
    return "\n".join(lines)
