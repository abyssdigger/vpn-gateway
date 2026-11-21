"""Linux nft Backend composition for combined materialized NG3 policy owner classes."""

from __future__ import annotations

from dataclasses import dataclass

from .composite_nft_mutation import CompositeNftPhysicalSnapshot
from .device_firewall_desired import DeviceFirewallChainSpec
from .interface_inventory import parse_ip_link_inventory
from .linux_device_firewall import LinuxDeviceFirewallDriver
from .linux_local_integration import LinuxIntegrationLocalDriver
from .linux_nft_scaffold import NftScriptRunner
from .linux_local_publication import LinuxLocalPublicationDriver
from .linux_probe_local import LinuxProbeLocalDriver
from .local_integration_mutation import IntegrationLocalMutationStep
from .local_publication_mutation import LocalPublicationMutationStep
from .probe_local_mutation import ProbeLocalMutationStep
from .linux_payload_nat import LinuxPayloadNatDriver
from .nft_namespace_inventory import parse_nft_namespace_ruleset
from .payload_forward_desired import PayloadForwardRuleSpec
from .payload_forward_observation import (
    PAYLOAD_FORWARD_NEW_COMMENT,
    PAYLOAD_FORWARD_RETURN_COMMENT,
    PayloadForwardRuleKind,
)
from .payload_nat_desired import PayloadMasqueradeSpec


@dataclass(slots=True)
class LinuxCompositeNftBackend:
    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)

    def _links(self):
        return parse_ip_link_inventory(
            self.runner.run(self._cmd("ip", "-j", "link", "show"))
        )

    def observe_composite_snapshot(self) -> CompositeNftPhysicalSnapshot:
        before = self._links()
        nft = parse_nft_namespace_ruleset(
            self.runner.run(
                self._cmd("nft", "-j", "list", "ruleset")
            )
        )
        after = self._links()
        if before != after:
            raise RuntimeError(
                "interface identity inventory drift during composite nft observation"
            )
        return CompositeNftPhysicalSnapshot(
            observation=nft,
            interfaces=before,
        )

    def delete_profile_rule(self, handle: int) -> None:
        if type(handle) is not int or handle < 0:
            raise ValueError("handle must be a non-negative integer")
        self.runner.run(
            self._cmd(
                "nft", "delete", "rule", "ip", "vpn_gate",
                "payload_forward", "handle", str(handle),
            )
        )

    def add_profile_rule(self, spec: PayloadForwardRuleSpec) -> None:
        if not isinstance(spec, PayloadForwardRuleSpec):
            raise ValueError("spec must be PayloadForwardRuleSpec")

        if spec.kind is PayloadForwardRuleKind.NEW:
            state = "new"
            comment = PAYLOAD_FORWARD_NEW_COMMENT
        elif spec.kind is PayloadForwardRuleKind.RETURN:
            state = "established,related"
            comment = PAYLOAD_FORWARD_RETURN_COMMENT
        else:
            raise ValueError("unsupported Profile forward rule kind")

        script = (
            "add rule ip vpn_gate payload_forward "
            f"ct state {state} "
            f"meta iif {spec.ingress.ifindex} "
            f"meta oif {spec.egress.ifindex} "
            f"ip {spec.remote_field.value} {spec.remote_prefix.with_prefixlen} "
            f'accept comment "{comment}"\n'
        )
        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            script,
        )

    def delete_device_jump(self, handle: int) -> None:
        self._device_driver().delete_device_jump(handle)

    def delete_device_child_chain(self, name: str) -> None:
        self._device_driver().delete_device_child_chain(name)

    def create_device_chain(self, spec: DeviceFirewallChainSpec) -> None:
        self._device_driver().create_device_chain(spec)

    def delete_nat_rule(self, handle: int) -> None:
        self._nat_driver().delete_nat_rule(handle)

    def add_nat_rule(self, spec: PayloadMasqueradeSpec) -> None:
        self._nat_driver().add_nat_rule(spec)

    def apply_local_publication_step(
        self,
        step: LocalPublicationMutationStep,
    ) -> None:
        self._local_publication_driver().apply_local_publication_step(step)

    def apply_integration_local_step(
        self,
        step: IntegrationLocalMutationStep,
    ) -> None:
        self._integration_local_driver().apply_integration_local_step(step)

    def apply_probe_local_step(
        self,
        step: ProbeLocalMutationStep,
    ) -> None:
        self._probe_local_driver().apply_probe_local_step(step)

    def _device_driver(self) -> LinuxDeviceFirewallDriver:
        return LinuxDeviceFirewallDriver(
            runner=self.runner,
            namespace=self.namespace,
        )

    def _nat_driver(self) -> LinuxPayloadNatDriver:
        return LinuxPayloadNatDriver(
            runner=self.runner,
            namespace=self.namespace,
        )

    def _local_publication_driver(self) -> LinuxLocalPublicationDriver:
        return LinuxLocalPublicationDriver(
            runner=self.runner,
            namespace=self.namespace,
        )

    def _integration_local_driver(self) -> LinuxIntegrationLocalDriver:
        return LinuxIntegrationLocalDriver(
            runner=self.runner,
            namespace=self.namespace,
        )

    def _probe_local_driver(self) -> LinuxProbeLocalDriver:
        return LinuxProbeLocalDriver(
            runner=self.runner,
            namespace=self.namespace,
        )
