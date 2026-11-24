"""Strict Linux nft Driver for payload NAT observation and mutation primitives."""

from __future__ import annotations

from dataclasses import dataclass

from .interface_identity import InterfaceIdentity
from .interface_inventory import parse_ip_link_inventory
from .linux_nft_scaffold import NftScriptRunner
from .nft_namespace_inventory import (
    NftNamespaceObservation,
    parse_nft_namespace_ruleset,
)
from .payload_nat_desired import (
    PayloadMasqueradeSpec,
    PayloadNatRuleSpec,
    PayloadProfileSnatSpec,
)


@dataclass(frozen=True, slots=True)
class PayloadNatPhysicalSnapshot:
    """Stable link-generation bracket plus the corresponding nft observation."""

    observation: NftNamespaceObservation
    interfaces: tuple[InterfaceIdentity, ...]


@dataclass(slots=True)
class LinuxPayloadNatDriver:
    """Observe and mutate the owned payload-postrouting NAT representation."""

    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)

    def _links(self) -> tuple[InterfaceIdentity, ...]:
        return parse_ip_link_inventory(
            self.runner.run(self._cmd("ip", "-j", "link", "show"))
        )

    def observe_nat_snapshot(self) -> PayloadNatPhysicalSnapshot:
        """Return nft state bracketed by one stable interface generation."""

        before = self._links()
        nft = parse_nft_namespace_ruleset(
            self.runner.run(self._cmd("nft", "-j", "list", "ruleset"))
        )
        after = self._links()
        if before != after:
            raise RuntimeError(
                "interface identity inventory drift during nft observation"
            )
        return PayloadNatPhysicalSnapshot(nft, before)

    def add_nat_rule(self, spec: PayloadNatRuleSpec) -> None:
        """Add one exact desired payload NAT rule; return is not confirmation."""

        if isinstance(spec, PayloadMasqueradeSpec):
            script = (
                "add rule ip vpn_gate payload_postrouting "
                f"meta iif {spec.ingress.ifindex} meta oif {spec.egress.ifindex} "
                'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n'
            )
        elif isinstance(spec, PayloadProfileSnatSpec):
            script = (
                "add rule ip vpn_gate payload_postrouting "
                f"ct mark {hex(spec.mark)} meta oif {spec.egress.ifindex} "
                f"snat to {spec.source_address} "
                'comment "vpn-gate:ng3:profile-snat-v1"\n'
            )
        else:
            raise ValueError("spec must be a supported payload NAT rule")
        self.runner.run_script(self._cmd("nft", "-f", "-"), script)

    def delete_nat_rule(self, handle: int) -> None:
        """Delete one exact owned payload NAT rule by nft handle."""

        if type(handle) is not int or handle < 0:
            raise ValueError("handle must be a non-negative integer")
        self.runner.run(
            self._cmd(
                "nft",
                "delete",
                "rule",
                "ip",
                "vpn_gate",
                "payload_postrouting",
                "handle",
                str(handle),
            )
        )


# Historical executable-evidence compatibility alias.
LinuxPayloadNatBackend = LinuxPayloadNatDriver
