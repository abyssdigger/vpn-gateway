"""VPN-GATE NG3 Python reference slice."""

from .config import ConfigError, parse_structural_config
from .domain import (
    DeviceBindingIntent,
    DeviceConfigIntent,
    Direction,
    ExpectedInterfaceSelector,
    ProfileConfigIntent,
    SelectorKind,
    StructuralConfig,
)

__all__ = [
    "ConfigError",
    "DeviceBindingIntent",
    "DeviceConfigIntent",
    "Direction",
    "ExpectedInterfaceSelector",
    "ProfileConfigIntent",
    "SelectorKind",
    "StructuralConfig",
    "parse_structural_config",
]
