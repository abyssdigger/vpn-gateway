"""Linux desired-state compiler for NG3 ordinary-host boundary routing.

The compiler is intentionally side-effect free. It turns the semantic host-boundary plan into
exact route/RPDB/nft desired objects. Mutation/observation remains a separate lower Driver.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from .host_boundary_policy import HostBoundaryPolicyPlan


class FullTunnelUnderlayPinningRequired(ValueError):
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
class HostBoundaryLinuxDesired:
    bootstrap_routes: tuple[HostBoundaryRouteSpec, ...]
    return_route: HostBoundaryReturnRouteSpec | None
    return_rule: HostBoundaryRuleSpec | None
    nft_script: str | None


def build_linux_host_boundary_desired(
    plan: HostBoundaryPolicyPlan,
    *,
    host_interface: str,
    inner_gateway: IPv4Address,
    allocation: HostBoundaryLinuxAllocation,
) -> HostBoundaryLinuxDesired:
    if not isinstance(plan, HostBoundaryPolicyPlan):
        raise ValueError("plan must be HostBoundaryPolicyPlan")
    if not isinstance(host_interface, str) or not host_interface:
        raise ValueError("host_interface must be non-empty text")
    if not isinstance(inner_gateway, IPv4Address):
        raise ValueError("inner_gateway must be IPv4Address")
    if not isinstance(allocation, HostBoundaryLinuxAllocation):
        raise ValueError("allocation must be HostBoundaryLinuxAllocation")

    if plan.full_tunnel:
        raise FullTunnelUnderlayPinningRequired(
            "0.0.0.0/0 host bootstrap requires observed underlay endpoint pinning "
            "before catch-all routes may be materialized"
        )

    bootstrap = tuple(
        HostBoundaryRouteSpec(
            destination=item.destination,
            via=inner_gateway,
            interface=host_interface,
            protocol=allocation.route_protocol,
        )
        for item in plan.bootstrap_routes
    )

    has_stateful = any(item.stateful_return for item in plan.return_classifier)
    if not has_stateful:
        return HostBoundaryLinuxDesired(
            bootstrap_routes=bootstrap,
            return_route=None,
            return_rule=None,
            nft_script=None,
        )

    return HostBoundaryLinuxDesired(
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
        nft_script=_render_nft(plan, host_interface, allocation.mark),
    )


def _render_nft(
    plan: HostBoundaryPolicyPlan,
    host_interface: str,
    mark: int,
) -> str:
    safe_if = host_interface.replace("\\", "\\\\").replace('"', '\\"')
    mark_hex = hex(mark)
    lines = [
        'table inet vpn_gate_host_return {',
        '  chain classify_remote {',
    ]
    for item in plan.return_classifier:
        prefix = item.remote_prefix.with_prefixlen
        if item.stateful_return:
            lines.append(
                f'    ip saddr {prefix} ct state new ct mark set {mark_hex} return'
            )
        else:
            # Explicit negative verdict is required to stop a more-specific
            # route-return Profile from falling through to a broader stateful prefix.
            lines.append(f'    ip saddr {prefix} return')
    lines.extend(
        (
            '    return',
            '  }',
            '  chain prerouting {',
            '    type filter hook prerouting priority mangle; policy accept;',
            f'    iifname "{safe_if}" jump classify_remote',
            f'    iifname != "{safe_if}" ct mark {mark_hex} meta mark set ct mark',
            '  }',
            '  chain output {',
            '    type route hook output priority mangle; policy accept;',
            f'    ct mark {mark_hex} meta mark set ct mark',
            '  }',
            '}',
            '',
        )
    )
    return "\n".join(lines)
