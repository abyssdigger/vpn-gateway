from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network

from .port_bundle import PortBundle


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


class DeviceFirewallDirection(str, Enum):
    """Direction relative to one Device/path, not Linux INPUT/OUTPUT."""

    IN = "in"
    OUT = "out"


class DeviceFirewallAction(str, Enum):
    """Normalized Device verdict semantics, independent of nft spelling."""

    ALLOW = "allow"
    DENY = "deny"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class DeviceFirewallRuleIntent:
    """One normalized ordered Device firewall rule.

    This is an internal semantic contract. It does not define external config
    grammar and deliberately leaves the accepted protocol vocabulary to the
    separate configuration-format/compiler gate.
    """

    direction: DeviceFirewallDirection
    action: DeviceFirewallAction
    protocol: str | None = None
    source_ports: PortBundle | int | None = None
    destination_ports: PortBundle | int | None = None
    source_ipv4_cidr: IPv4Network | None = None
    destination_ipv4_cidr: IPv4Network | None = None
    path_ifname: str | None = None
    private_peer_ipv4: IPv4Address | None = None
    comment: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.direction, DeviceFirewallDirection):
            raise ValueError("direction must be DeviceFirewallDirection")
        if not isinstance(self.action, DeviceFirewallAction):
            raise ValueError("action must be DeviceFirewallAction")
        if self.protocol is not None and (
            not isinstance(self.protocol, str) or not self.protocol
        ):
            raise ValueError("protocol must be non-empty text when present")
        for field_name in ("source_ports", "destination_ports"):
            value = getattr(self, field_name)
            if type(value) is int:
                value = PortBundle.single(value)
                object.__setattr__(self, field_name, value)
            if value is not None and not isinstance(value, PortBundle):
                raise ValueError(
                    f"{field_name} must be PortBundle or exact integer when present"
                )
        for field_name, value in (
            ("source_ipv4_cidr", self.source_ipv4_cidr),
            ("destination_ipv4_cidr", self.destination_ipv4_cidr),
        ):
            if value is not None and not isinstance(value, IPv4Network):
                raise ValueError(
                    f"{field_name} must be IPv4Network when present"
                )
        if self.path_ifname is not None:
            if (
                not isinstance(self.path_ifname, str)
                or not self.path_ifname
                or any(ch.isspace() for ch in self.path_ifname)
                or "*" in self.path_ifname
                or len(self.path_ifname.encode("utf-8")) > 15
            ):
                raise ValueError(
                    "path_ifname must be an exact Linux interface name when present"
                )
        if (
            self.private_peer_ipv4 is not None
            and not isinstance(self.private_peer_ipv4, IPv4Address)
        ):
            raise ValueError(
                "private_peer_ipv4 must be IPv4Address when present"
            )
        if self.path_ifname is not None and self.private_peer_ipv4 is not None:
            raise ValueError(
                "path_ifname and private_peer_ipv4 are mutually exclusive"
            )
        if self.comment is not None and not isinstance(self.comment, str):
            raise ValueError("comment must be text when present")


@dataclass(frozen=True, slots=True)
class DeviceFirewallPolicyIntent:
    """Ordered Device firewall semantics.

    rules=None means the Device firewall is omitted and therefore adds no
    restriction. An explicit policy must contain at least one rule; its
    no-match result is DROP at the lower realization boundary.
    """

    device_id: str
    rules: tuple[DeviceFirewallRuleIntent, ...] | None

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id must be a non-empty string")
        if self.rules is None:
            return
        if not isinstance(self.rules, tuple) or not self.rules:
            raise ValueError(
                "explicit Device firewall policy must be a non-empty tuple"
            )
        if not all(
            isinstance(rule, DeviceFirewallRuleIntent)
            for rule in self.rules
        ):
            raise ValueError(
                "rules must contain DeviceFirewallRuleIntent values"
            )
