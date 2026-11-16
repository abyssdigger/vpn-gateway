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
    "parse_ip_link_inventory",
    "plan_route_priority_moves",
    "parse_structural_config",
    "project_device_bindings",
]
