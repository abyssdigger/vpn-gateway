"""Operational logging boundary for the NG3 reference runtime.

Architecture: A.010 OperationalLogAdapter.
Requirement traceability: VPNG-M001-R2.R3.*
"""

from __future__ import annotations

from enum import Enum
from typing import Callable


LOG_TAG = "LOG"


class OperationalLogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_LEVEL_ORDER = {
    OperationalLogLevel.DEBUG: 10,
    OperationalLogLevel.INFO: 20,
    OperationalLogLevel.WARNING: 30,
    OperationalLogLevel.ERROR: 40,
}


class OperationalLogAdapter:
    """Direct Adapter from semantic operational records to one deployment log stream."""

    def __init__(
        self,
        minimum_level: OperationalLogLevel = OperationalLogLevel.INFO,
        *,
        sink: Callable[[str], None] | None = None,
    ) -> None:
        if not isinstance(minimum_level, OperationalLogLevel):
            raise ValueError("minimum_level must be OperationalLogLevel")
        self._minimum_level = minimum_level
        self._sink = sink if sink is not None else self._default_sink

    @property
    def minimum_level(self) -> OperationalLogLevel:
        return self._minimum_level

    def emit(
        self,
        level: OperationalLogLevel,
        component_tag: str,
        event: str,
        **safe_context: str | int | float | bool | None,
    ) -> bool:
        if not isinstance(level, OperationalLogLevel):
            raise ValueError("level must be OperationalLogLevel")
        if not isinstance(component_tag, str) or not component_tag:
            raise ValueError("component_tag must be a non-empty string")
        if len(component_tag) > 6:
            raise ValueError("component_tag must not exceed 6 characters")
        if not isinstance(event, str) or not event:
            raise ValueError("event must be a non-empty string")
        for key, value in safe_context.items():
            if not isinstance(key, str) or not key:
                raise ValueError("log context keys must be non-empty strings")
            if value is not None and type(value) not in {str, int, float, bool}:
                raise ValueError(
                    "operational log context must be pre-normalized safe scalar data"
                )

        if _LEVEL_ORDER[level] < _LEVEL_ORDER[self._minimum_level]:
            return False

        fields = " ".join(
            f"{key}={_render_value(value)}"
            for key, value in sorted(safe_context.items())
        )
        line = f"{level.value.upper()} {component_tag} {event}"
        if fields:
            line += " " + fields
        self._sink(line)
        return True

    @staticmethod
    def _default_sink(line: str) -> None:
        print(line, flush=True)


def _render_value(value: str | int | float | bool | None) -> str:
    if value is None:
        return "none"
    if type(value) is bool:
        return "true" if value else "false"
    text = str(value)
    if text and all(ch.isalnum() or ch in "._:/-," for ch in text):
        return text
    return repr(text)
