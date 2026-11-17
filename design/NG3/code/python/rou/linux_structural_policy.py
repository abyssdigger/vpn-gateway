"""Linux backend for one cross-domain structural NetworkPolicy snapshot/mutation."""

from __future__ import annotations

from dataclasses import dataclass

from .device_firewall_desired import DeviceFirewallChainSpec
from .interface_inventory import parse_ip_link_inventory
from .linux_composite_nft import LinuxCompositeNftBackend
from .linux_nft_scaffold import NftScriptRunner
from .linux_structural_routing import LinuxStructuralRoutingBackend
from .local_integration_mutation import IntegrationLocalMutationStep
from .local_publication_mutation import LocalPublicationMutationStep
from .network_policy_layout import NetworkPolicyPlatformSpace
from .nft_namespace_inventory import parse_nft_namespace_ruleset
from .payload_forward_desired import PayloadForwardRuleSpec
from .payload_nat_desired import PayloadMasqueradeSpec
from .payload_routing_desired import ManagedRouteSpec, ManagedRuleSpec
from .structural_policy_mutation import StructuralPolicyPhysicalSnapshot
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    parse_structural_routing_inventory,
)


@dataclass(slots=True)
class LinuxStructuralPolicyBackend:
    runner: NftScriptRunner
    namespace: str
    platform: NetworkPolicyPlatformSpace

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")
        if not isinstance(self.platform, NetworkPolicyPlatformSpace):
            raise ValueError("platform must be NetworkPolicyPlatformSpace")

    def observe_structural_snapshot(self) -> StructuralPolicyPhysicalSnapshot:
        before = self._links()
        routes = self.runner.run(
            (
                "ip", "-n", self.namespace,
                "-j", "-N", "-4",
                "route", "show", "table", "all",
            )
        )
        rules = self.runner.run(
            (
                "ip", "-n", self.namespace,
                "-j", "-N", "-4",
                "rule", "show",
            )
        )
        nft = self.runner.run(
            (
                "ip", "netns", "exec", self.namespace,
                "nft", "-j", "list", "ruleset",
            )
        )
        after = self._links()
        if before != after:
            raise RuntimeError(
                "interface identity inventory drift during structural observation"
            )

        return StructuralPolicyPhysicalSnapshot(
            interfaces=before,
            routing=parse_structural_routing_inventory(
                routes,
                rules,
                before,
                self.platform,
            ),
            nft=parse_nft_namespace_ruleset(nft),
        )

    def add_route(self, spec: ManagedRouteSpec) -> None:
        self._routing().add_route(spec)

    def delete_route(self, route: ObservedManagedRoute) -> None:
        self._routing().delete_route(route)

    def add_rule(self, spec: ManagedRuleSpec) -> None:
        self._routing().add_rule(spec)

    def delete_rule(self, rule: ObservedManagedRule) -> None:
        self._routing().delete_rule(rule)

    def delete_profile_rule(self, handle: int) -> None:
        self._nft().delete_profile_rule(handle)

    def add_profile_rule(self, spec: PayloadForwardRuleSpec) -> None:
        self._nft().add_profile_rule(spec)

    def delete_device_jump(self, handle: int) -> None:
        self._nft().delete_device_jump(handle)

    def delete_device_child_chain(self, name: str) -> None:
        self._nft().delete_device_child_chain(name)

    def create_device_chain(self, spec: DeviceFirewallChainSpec) -> None:
        self._nft().create_device_chain(spec)

    def delete_nat_rule(self, handle: int) -> None:
        self._nft().delete_nat_rule(handle)

    def add_nat_rule(self, spec: PayloadMasqueradeSpec) -> None:
        self._nft().add_nat_rule(spec)

    def apply_local_publication_step(
        self,
        step: LocalPublicationMutationStep,
    ) -> None:
        self._nft().apply_local_publication_step(step)

    def apply_integration_local_step(
        self,
        step: IntegrationLocalMutationStep,
    ) -> None:
        self._nft().apply_integration_local_step(step)

    def _links(self):
        return parse_ip_link_inventory(
            self.runner.run(
                ("ip", "-n", self.namespace, "-j", "link", "show")
            )
        )

    def _routing(self) -> LinuxStructuralRoutingBackend:
        return LinuxStructuralRoutingBackend(
            runner=self.runner,
            namespace=self.namespace,
        )

    def _nft(self) -> LinuxCompositeNftBackend:
        return LinuxCompositeNftBackend(
            runner=self.runner,
            namespace=self.namespace,
        )
