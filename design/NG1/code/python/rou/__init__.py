"""VPN-GATE NG1 ROU production-model reference package."""

from .config import ConfigError, load_active_config, parse_active_config
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

__all__ = [
    "ActiveConfig",
    "Availability",
    "ConfigError",
    "Device",
    "Direction",
    "ExpectedInterface",
    "InterfaceMatch",
    "MatchKind",
    "Profile",
    "load_active_config",
    "parse_active_config",
]
