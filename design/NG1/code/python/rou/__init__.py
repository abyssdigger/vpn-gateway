"""VPN-GATE NG1 ROU production-model reference package."""

from .config import ConfigError, load_active_config, parse_active_config
from .device_engine import (
    BoundInterface,
    DeviceBindingSnapshot,
    DeviceBindingState,
    DeviceReconcileResult,
    EnvironmentInterface,
    ExpectedBindingState,
    InterfaceIdentity,
    reconcile_devices,
)
from .domain import (
    ActiveConfig,
    Availability,
    Device,
    Direction,
    ExpectedInterface,
    InterfaceMatch,
    MatchKind,
    Profile,
)
from .traffic_state import (
    MetricAssignment,
    TrafficProjection,
    TrafficRuntimeState,
    committed_state_from_verified,
    project_normal_metrics,
)

__all__ = [
    "ActiveConfig",
    "Availability",
    "BoundInterface",
    "ConfigError",
    "Device",
    "DeviceBindingSnapshot",
    "DeviceBindingState",
    "DeviceReconcileResult",
    "Direction",
    "EnvironmentInterface",
    "ExpectedBindingState",
    "ExpectedInterface",
    "InterfaceIdentity",
    "InterfaceMatch",
    "MatchKind",
    "MetricAssignment",
    "Profile",
    "TrafficProjection",
    "TrafficRuntimeState",
    "committed_state_from_verified",
    "load_active_config",
    "parse_active_config",
    "project_normal_metrics",
    "reconcile_devices",
]
