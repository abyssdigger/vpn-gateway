"""Test-only parser for the isolated structural Device/Profile slice."""

from __future__ import annotations

import tomllib

from rou.config import (
    ConfigError,
    _DEVICE_STRUCTURAL_KEYS,
    _PROFILE_STRUCTURAL_KEYS,
    _TOP_LEVEL_KEYS,
    _parse_structural_root,
)


def parse_structural_config(text: str):
    """Parse only the lower structural slice used by isolated unit tests."""
    try:
        raw = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, TypeError) as exc:
        raise ConfigError(f"invalid TOML: {exc}") from None
    return _parse_structural_root(
        raw,
        top_level_keys=_TOP_LEVEL_KEYS,
        device_keys=_DEVICE_STRUCTURAL_KEYS,
        profile_keys=_PROFILE_STRUCTURAL_KEYS,
    )
