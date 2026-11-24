from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class InterfaceIdentity:
    ifname: str
    ifindex: int

    def __post_init__(self) -> None:
        if not isinstance(self.ifname, str) or not self.ifname:
            raise ValueError("ifname must be a non-empty string")
        if len(self.ifname.encode("utf-8")) > 15:
            raise ValueError("ifname exceeds Linux IFNAMSIZ-1")
        if type(self.ifindex) is not int or self.ifindex <= 0:
            raise ValueError("ifindex must be a positive integer")
