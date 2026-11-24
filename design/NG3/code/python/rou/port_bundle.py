"""Normalized bounded TCP/UDP port bundle value objects.

A PortBundle preserves user-declared item order. Overlap is rejected so the same
port cannot be represented twice, including through intersecting ranges.
"""

from __future__ import annotations

from dataclasses import dataclass
from .ip_port import IP_PORT_MAX, IP_PORT_MIN, is_ip_port


@dataclass(frozen=True, slots=True)
class PortSpan:
    first: int
    last: int

    def __post_init__(self) -> None:
        for name, value in (("first", self.first), ("last", self.last)):
            if not is_ip_port(value):
                raise ValueError(
                    f"{name} must be an integer in "
                    f"[{IP_PORT_MIN}, {IP_PORT_MAX}]"
                )
        if self.first > self.last:
            raise ValueError("port span first must be <= last")

    @property
    def cardinality(self) -> int:
        return self.last - self.first + 1

    @property
    def is_single(self) -> bool:
        return self.first == self.last


@dataclass(frozen=True, slots=True)
class PortBundle:
    spans: tuple[PortSpan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.spans, tuple) or not self.spans:
            raise ValueError("port bundle must be a non-empty tuple")
        if not all(isinstance(span, PortSpan) for span in self.spans):
            raise ValueError("port bundle must contain PortSpan values")
        for index, left in enumerate(self.spans):
            for right in self.spans[index + 1 :]:
                if left.first <= right.last and right.first <= left.last:
                    raise ValueError("port bundle spans must not overlap")

    @classmethod
    def single(cls, port: int) -> "PortBundle":
        return cls((PortSpan(port, port),))

    @property
    def cardinality(self) -> int:
        return sum(span.cardinality for span in self.spans)

    def expanded(self):
        for span in self.spans:
            yield from range(span.first, span.last + 1)
