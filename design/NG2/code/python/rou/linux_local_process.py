from __future__ import annotations

from dataclasses import dataclass


class LinuxLocalProcessError(ValueError):
    pass


@dataclass(frozen=True)
class LinuxLocalProcessConfig:
    """Linux-only identity for semantic LOCAL_PROCESS traffic.

    These values are deliberately absent from NetworkRulesSpec. They are runtime
    lower-domain allocation/configuration used by the Linux backend only.
    """

    uid: int
    ct_mark: int

    def __post_init__(self) -> None:
        if type(self.uid) is not int or not 0 <= self.uid < (1 << 32) - 1:
            raise LinuxLocalProcessError(
                "local-process uid must be an unsigned 32-bit uid other than UINT32_MAX"
            )
        if type(self.ct_mark) is not int or not 1 <= self.ct_mark <= 0xFFFFFFFF:
            raise LinuxLocalProcessError(
                "local-process conntrack mark must be 1..0xffffffff"
            )
