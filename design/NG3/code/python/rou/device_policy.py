from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NatIntent(str, Enum):
    """Normalized Device payload source-NAT semantics, not external config spelling."""

    NONE = "none"
    MASQUERADE = "masquerade"


@dataclass(frozen=True, slots=True)
class DeviceNatPolicyIntent:
    device_id: str
    nat_intent: NatIntent

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id must be a non-empty string")
        if not isinstance(self.nat_intent, NatIntent):
            raise ValueError("nat_intent must be NatIntent")
