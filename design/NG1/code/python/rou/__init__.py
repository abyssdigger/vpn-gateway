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
from .dispatch import DispatchEntry, classify_device_to_host_profile, compile_profile_dispatch
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
from .environment import EnvironmentParseError, EnvironmentSnapshot, parse_ip_link_json
from .firewall_intent import FlowDirection, NewFlowRuleIntent, Verdict, compile_new_flow_intents
from .route_intent import (
    DirectRouteIntent,
    FallbackRouteIntent,
    ProfileRouteIntent,
    compile_profile_route_intents,
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
    "DirectRouteIntent",
    "FallbackRouteIntent",
    "Direction",
    "DispatchEntry",
    "EnvironmentInterface",
    "EnvironmentParseError",
    "EnvironmentSnapshot",
    "FlowDirection",
    "ExpectedBindingState",
    "ExpectedInterface",
    "InterfaceIdentity",
    "InterfaceMatch",
    "MatchKind",
    "MetricAssignment",
    "NewFlowRuleIntent",
    "Profile",
    "ProfileRouteIntent",
    "TrafficProjection",
    "TrafficRuntimeState",
    "Verdict",
    "classify_device_to_host_profile",
    "committed_state_from_verified",
    "compile_new_flow_intents",
    "compile_profile_dispatch",
    "compile_profile_route_intents",
    "load_active_config",
    "parse_active_config",
    "parse_ip_link_json",
    "project_normal_metrics",
    "reconcile_devices",
]
