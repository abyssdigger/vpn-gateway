from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from ipaddress import IPv4Address, IPv4Network
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

from .interfaces import (
    InterfaceBinding,
    InterfaceRecord,
    InterfaceSelector,
    ProfileInterfaceState,
)

if TYPE_CHECKING:
    from .policy import FirewallNatPolicy


class DaemonState(Enum):
    STARTING = auto()
    ACTIVE = auto()
    DEGRADED = auto()
    ISOLATED = auto()
    STOPPING = auto()


class FirewallSafety(Enum):
    SAFE = auto()
    UNSAFE = auto()
    UNKNOWN = auto()


class FirewallDriftScope(Enum):
    INPUT_ONLY = auto()
    TRANSIT = auto()


class RouteType(Enum):
    UNICAST = auto()
    BLACKHOLE = auto()
    UNREACHABLE = auto()
    PROHIBIT = auto()
    THROW = auto()


class ApplyStateResult(Enum):
    SUCCESS = auto()
    FAIL = auto()


class ConfigIssueLevel(Enum):
    ERROR = auto()
    WARNING = auto()
    NOTE = auto()


class RuntimeReasonCode(Enum):
    INTERFACE_INVENTORY_FAILED = auto()
    SNAPSHOT_PROJECTION_FAILED = auto()
    IPV6_PREREQUISITE_FAILED = auto()
    FIREWALL_INVENTORY_FAILED = auto()
    FIREWALL_INSPECTION_FAILED = auto()
    FIREWALL_DRIFT = auto()
    FIREWALL_REPAIR_FAILED = auto()
    ROUTE_PASS_INCOMPLETE = auto()
    PROFILE_ROUTE_MISMATCH = auto()
    PROFILE_NO_UNICAST_PATH = auto()
    FORWARDING_DISABLE_FAILED = auto()
    FORWARDING_ENABLE_FAILED = auto()
    FORWARDING_QUERY_FAILED = auto()
    FORWARDING_RESTORED = auto()


RUNTIME_REASON_TEXT: Mapping[RuntimeReasonCode, str] = MappingProxyType(
    {
        RuntimeReasonCode.INTERFACE_INVENTORY_FAILED:
            "failed to inventory interfaces for reconciliation",
        RuntimeReasonCode.SNAPSHOT_PROJECTION_FAILED:
            "failed to build complete reconciliation snapshot",
        RuntimeReasonCode.IPV6_PREREQUISITE_FAILED:
            "IPv6 host prerequisites are not satisfied",
        RuntimeReasonCode.FIREWALL_INVENTORY_FAILED:
            "failed to inventory fixed firewall/NAT state",
        RuntimeReasonCode.FIREWALL_INSPECTION_FAILED:
            "failed to parse/normalize/compare fixed firewall/NAT state",
        RuntimeReasonCode.FIREWALL_DRIFT:
            "fixed firewall/NAT state differs from configured policy",
        RuntimeReasonCode.FIREWALL_REPAIR_FAILED:
            "failed to repair fixed firewall/NAT state",
        RuntimeReasonCode.ROUTE_PASS_INCOMPLETE:
            "route reconciliation pass did not complete",
        RuntimeReasonCode.PROFILE_ROUTE_MISMATCH:
            "verified profile route state differs from desired state",
        RuntimeReasonCode.PROFILE_NO_UNICAST_PATH:
            "profile has no verified desired UNICAST path",
        RuntimeReasonCode.FORWARDING_DISABLE_FAILED:
            "failed to confirm ip_forward disabled",
        RuntimeReasonCode.FORWARDING_ENABLE_FAILED:
            "failed to confirm ip_forward enabled",
        RuntimeReasonCode.FORWARDING_QUERY_FAILED:
            "failed to query ip_forward state",
        RuntimeReasonCode.FORWARDING_RESTORED:
            "ip_forward was unexpectedly disabled and was restored",
    }
)


@dataclass(slots=True, frozen=True)
class RouteSpec:
    destination: IPv4Network
    route_type: RouteType
    via: IPv4Address | None
    interface: str | None
    metric: int | None
    proto: int | None
    onlink: bool


@dataclass(slots=True, frozen=True)
class ReconciliationPlan:
    route_adds: frozenset[RouteSpec]
    route_deletes: frozenset[RouteSpec]
    route_replaces: frozenset[RouteSpec]


@dataclass(slots=True, frozen=True)
class ReconciliationSnapshot:
    interfaces: tuple[InterfaceRecord, ...]
    interface_state_by_profile: Mapping[str, ProfileInterfaceState]
    prefix_metric_allocations_by_profile: Mapping[
        str, Mapping[InterfaceBinding, int]
    ]
    prefix_metric_cursor_by_profile: Mapping[str, int]
    desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]]
    desired_full_policy: FirewallNatPolicy

    def __post_init__(self) -> None:
        object.__setattr__(self, "interfaces", tuple(self.interfaces))
        object.__setattr__(
            self,
            "interface_state_by_profile",
            MappingProxyType(dict(self.interface_state_by_profile)),
        )
        object.__setattr__(
            self,
            "prefix_metric_allocations_by_profile",
            MappingProxyType(
                {
                    profile_id: MappingProxyType(dict(metrics))
                    for profile_id, metrics
                    in self.prefix_metric_allocations_by_profile.items()
                }
            ),
        )
        object.__setattr__(
            self,
            "prefix_metric_cursor_by_profile",
            MappingProxyType(dict(self.prefix_metric_cursor_by_profile)),
        )
        object.__setattr__(
            self,
            "desired_routes_by_profile",
            MappingProxyType(
                {
                    profile_id: frozenset(routes)
                    for profile_id, routes in self.desired_routes_by_profile.items()
                }
            ),
        )


@dataclass(slots=True, frozen=True)
class VpnProfileConfig:
    profile_id: str
    interface: InterfaceSelector
    network: IPv4Network
    routes: tuple[IPv4Network, ...]
    allowed_sources: tuple[IPv4Network, ...]

    @property
    def chain_input(self) -> str:
        return f"VPNG-{self.profile_id.upper()}-INPUT"

    @property
    def chain_forward(self) -> str:
        return f"VPNG-{self.profile_id.upper()}-FORWARD"

    @property
    def chain_nat(self) -> str:
        return f"VPNG-{self.profile_id.upper()}-NAT"


@dataclass(slots=True, frozen=True)
class GatewayConfig:
    reconcile_interval: float
    common_allowed_sources: tuple[IPv4Network, ...]
    vpns: Mapping[str, VpnProfileConfig]


@dataclass(slots=True, frozen=True)
class ConfigIssue:
    level: ConfigIssueLevel
    location: str
    message: str


@dataclass(slots=True, frozen=True)
class ConfigCheckResult:
    issues: tuple[ConfigIssue, ...]

    @property
    def has_errors(self) -> bool:
        return any(issue.level is ConfigIssueLevel.ERROR for issue in self.issues)


@dataclass(slots=True, frozen=True)
class DiagnosticFact:
    code: RuntimeReasonCode
    detail: str | None = None


@dataclass(slots=True, frozen=True)
class FirewallCheck:
    safety: FirewallSafety
    reason: DiagnosticFact | None
    scope: FirewallDriftScope | None = None

    def __post_init__(self) -> None:
        if self.safety is FirewallSafety.SAFE:
            if self.reason is not None or self.scope is not None:
                raise ValueError("SAFE FirewallCheck must not carry reason/scope")
            return
        if self.reason is None:
            raise ValueError("UNSAFE/UNKNOWN FirewallCheck requires a DiagnosticFact")
        if self.safety is FirewallSafety.UNKNOWN:
            if self.scope is not None:
                raise ValueError("UNKNOWN FirewallCheck must not carry scope")
            return
        if self.scope is None:
            raise ValueError("UNSAFE FirewallCheck requires drift scope")


@dataclass(slots=True, frozen=True)
class ProfileResult:
    result: ApplyStateResult
    reason: DiagnosticFact | None = None

    def __post_init__(self) -> None:
        if self.result is ApplyStateResult.SUCCESS:
            if self.reason is not None:
                raise ValueError("SUCCESS ProfileResult must not carry a reason")
            return
        if self.reason is None:
            raise ValueError("FAIL ProfileResult requires a DiagnosticFact")


@dataclass(slots=True, frozen=True)
class RouteVerifyResult:
    profile_results: Mapping[str, ProfileResult]
    owned_routes_by_profile: Mapping[str, frozenset[RouteSpec]]
    verified_profiles: frozenset[str]
