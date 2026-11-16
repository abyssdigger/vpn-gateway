"""VPN-GATE NG3 Python reference slice."""

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
    "build_payload_profile_requests",
    "classify_inbound_profile",
    "classify_outbound_profile",
    "parse_ip_link_inventory",
    "plan_route_priority_moves",
    "parse_structural_config",
    "project_device_bindings",
]
