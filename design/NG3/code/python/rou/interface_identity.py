from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class InterfaceIdentity:
    ifname: str
    ifindex: int

    def __post_init__(self) -> None:
        if not self.ifname:
            raise ValueError("ifname must not be empty")
        if self.ifindex <= 0:
            raise ValueError("ifindex must be positive")
