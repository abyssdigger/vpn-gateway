"""VPN-GATE NG3 Python reference slice."""

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

__all__ = [
    "ConfigError",
    "DeviceBindingIntent",
    "DeviceStructuralIntent",
    "Direction",
    "ExpectedInterfaceSelector",
    "ProfileStructuralIntent",
    "SelectorKind",
    "StructuralConfig",
    "parse_structural_config",
]
