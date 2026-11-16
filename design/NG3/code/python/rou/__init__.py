"""VPN-GATE NG3 Python reference slice."""

from .availability_priority import (
    AvailabilityPriorityError,
    calculate_effective_path_order,
)
from .availability_confirmation import (
    AvailabilityConfirmationState,
    AvailabilityOutcome,
    apply_availability_evidence,
)
from .binding import (
    BindingProjectionError,
    DeviceBindingProjection,
    DeviceBindingState,
    LogicalPathId,
    PathBinding,
    SelectorBindingState,
    WaitingCandidate,
    project_device_bindings,
)
from .config import ConfigError, parse_structural_config
from .domain import (
    DeviceBindingIntent,
    DeviceStructuralIntent,
    Direction,
    ExpectedInterfaceSelector,
    ProfileStructuralIntent,
    SelectorKind,
    StructuralConfig,
)
from .interface_identity import InterfaceIdentity
from .interface_inventory import (
    InterfaceInventoryError,
    parse_ip_link_inventory,
)
from .payload_profile import (
    PayloadProfileProjectionError,
    PayloadProfileRequest,
    build_payload_profile_requests,
)
from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyLayoutError,
    NetworkPolicyPlatformSpace,
    NumericResourcePool,
    PayloadDispatchRule,
    PayloadPolicyAllocation,
    ProbePolicyAllocation,
    ProbePolicyOwner,
    ProbeRoutingDemand,
    RouteMetricPlatformSpace,
    allocate_network_policy_layout,
)
from .profile_classification import (
    ProfileClassificationError,
    classify_inbound_profile,
    classify_outbound_profile,
)
from .route_priority import (
    RoutePriorityMove,
    RoutePriorityPlanError,
    plan_route_priority_moves,
)
from .route_priority_convergence import (
    RoutePriorityConvergenceError,
    RoutePriorityDeleteDuplicate,
    plan_route_priority_convergence,
)
from .route_priority_executor import (
    RoutePriorityExecutionResult,
    RoutePriorityExecutionStatus,
    RoutePrioritySnapshot,
    converge_route_priority_once,
)
from .route_priority_inventory import (
    RoutePriorityInventoryError,
    RoutePriorityPathRoute,
    parse_ip_route_priority_snapshot,
)
from .iproute_priority_backend import (
    IproutePriorityBackend,
    IproutePriorityBackendError,
    SubprocessCommandRunner,
)
from .route_priority_profile import (
    RoutePriorityDomainId,
    RoutePriorityDomainOutcome,
    RoutePriorityDomainRequest,
    RoutePriorityProfileResult,
    RoutePriorityProfileStatus,
    converge_route_priority_profile_once,
)
from .route_priority_realization import (
    RoutePriorityDomainRealization,
    RoutePriorityMetricSpace,
    RoutePriorityRealizationError,
)

__all__ = [
    "AvailabilityConfirmationState",
    "AvailabilityOutcome",
    "AvailabilityPriorityError",
    "BindingProjectionError",
    "ConfigError",
    "DeviceBindingIntent",
    "DeviceBindingProjection",
    "DeviceBindingState",
    "DeviceStructuralIntent",
    "Direction",
    "ExpectedInterfaceSelector",
    "InterfaceIdentity",
    "InterfaceInventoryError",
    "IproutePriorityBackend",
    "IproutePriorityBackendError",
    "LogicalPathId",
    "NetworkPolicyLayout",
    "NetworkPolicyLayoutError",
    "NetworkPolicyPlatformSpace",
    "NumericResourcePool",
    "PathBinding",
    "PayloadDispatchRule",
    "PayloadPolicyAllocation",
    "PayloadProfileProjectionError",
    "PayloadProfileRequest",
    "ProbePolicyAllocation",
    "ProbePolicyOwner",
    "ProbeRoutingDemand",
    "ProfileClassificationError",
    "ProfileStructuralIntent",
    "RouteMetricPlatformSpace",
    "RoutePriorityConvergenceError",
    "RoutePriorityDeleteDuplicate",
    "RoutePriorityDomainId",
    "RoutePriorityDomainOutcome",
    "RoutePriorityDomainRequest",
    "RoutePriorityDomainRealization",
    "RoutePriorityExecutionResult",
    "RoutePriorityExecutionStatus",
    "RoutePriorityInventoryError",
    "RoutePriorityMetricSpace",
    "RoutePriorityPathRoute",
    "RoutePrioritySnapshot",
    "RoutePriorityMove",
    "RoutePriorityPlanError",
    "RoutePriorityProfileResult",
    "RoutePriorityProfileStatus",
    "RoutePriorityRealizationError",
    "SelectorBindingState",
    "SelectorKind",
    "StructuralConfig",
    "SubprocessCommandRunner",
    "WaitingCandidate",
    "allocate_network_policy_layout",
    "apply_availability_evidence",
    "calculate_effective_path_order",
    "build_payload_profile_requests",
    "classify_inbound_profile",
    "classify_outbound_profile",
    "converge_route_priority_once",
    "converge_route_priority_profile_once",
    "parse_ip_link_inventory",
    "parse_ip_route_priority_snapshot",
    "plan_route_priority_convergence",
    "plan_route_priority_moves",
    "parse_structural_config",
    "project_device_bindings",
]
