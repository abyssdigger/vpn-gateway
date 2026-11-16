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
    "LogicalPathId",
    "PathBinding",
    "PayloadProfileProjectionError",
    "PayloadProfileRequest",
    "ProfileClassificationError",
    "ProfileStructuralIntent",
    "RoutePriorityConvergenceError",
    "RoutePriorityDeleteDuplicate",
    "RoutePriorityExecutionResult",
    "RoutePriorityExecutionStatus",
    "RoutePriorityInventoryError",
    "RoutePriorityPathRoute",
    "RoutePrioritySnapshot",
    "RoutePriorityMove",
    "RoutePriorityPlanError",
    "SelectorBindingState",
    "SelectorKind",
    "StructuralConfig",
    "WaitingCandidate",
    "apply_availability_evidence",
    "calculate_effective_path_order",
    "build_payload_profile_requests",
    "classify_inbound_profile",
    "classify_outbound_profile",
    "converge_route_priority_once",
    "parse_ip_link_inventory",
    "parse_ip_route_priority_snapshot",
    "plan_route_priority_convergence",
    "plan_route_priority_moves",
    "parse_structural_config",
    "project_device_bindings",
]
