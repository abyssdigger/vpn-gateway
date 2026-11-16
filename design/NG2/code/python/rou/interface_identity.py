from __future__ import annotations

from dataclasses import dataclass


class InterfaceIdentityError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class InterfaceIdentity:
    """Canonical identity of one observed interface generation."""

    ifname: str
    ifindex: int

    def __post_init__(self) -> None:
        if not self.ifname:
            raise InterfaceIdentityError("ifname must be non-empty")
        if len(self.ifname.encode("utf-8")) > 15:
            raise InterfaceIdentityError("ifname exceeds Linux IFNAMSIZ-1")
        if type(self.ifindex) is not int or self.ifindex <= 0:
            raise InterfaceIdentityError("ifindex must be a positive integer")
