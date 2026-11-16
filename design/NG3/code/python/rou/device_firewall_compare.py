"""Pure exact actual-vs-desired comparison for ordered Device firewall structure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallDesiredState,
)
from .device_firewall_structure import (
    DeviceFirewallStructureConflict,
    ObservedDeviceFirewallChain,
    ObservedDeviceFirewallJump,
    observe_device_firewall_structure,
)
from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObservation


class DeviceFirewallComparisonError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeviceFirewallComparison:
    confirmed: tuple[DeviceFirewallChainSpec, ...]
    missing: tuple[DeviceFirewallChainSpec, ...]
    stale_chains: tuple[ObservedDeviceFirewallChain, ...]
    stale_jumps: tuple[ObservedDeviceFirewallJump, ...]
    conflicts: tuple[DeviceFirewallStructureConflict, ...]

    @property
    def desired_confirmed(self) -> bool:
        return (
            not self.missing
            and not self.stale_chains
            and not self.stale_jumps
            and not self.conflicts
        )


def compare_device_firewall(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: DeviceFirewallDesiredState,
) -> DeviceFirewallComparison:
    if not isinstance(desired, DeviceFirewallDesiredState):
        raise DeviceFirewallComparisonError(
            "desired must be DeviceFirewallDesiredState"
        )

    current_interfaces = tuple(interfaces)
    current_set = set(current_interfaces)
    for chain in desired.chains:
        if (
            chain.ingress not in current_set
            or chain.egress not in current_set
        ):
            raise DeviceFirewallComparisonError(
                "desired Device firewall endpoints are not current"
            )

    observed = observe_device_firewall_structure(
        observation,
        current_interfaces,
    )

    observed_chains = {chain.name: chain for chain in observed.chains}
    current_jumps = {
        (
            jump.ingress,
            jump.egress,
            jump.target_chain,
        ): jump
        for jump in observed.current_jumps
    }

    confirmed: list[DeviceFirewallChainSpec] = []
    missing: list[DeviceFirewallChainSpec] = []
    used_chain_names: set[str] = set()
    used_jump_handles: set[int] = set()

    for expected in desired.chains:
        observed_chain = observed_chains.get(expected.child_chain_name)
        jump = current_jumps.get(
            (
                expected.ingress,
                expected.egress,
                expected.child_chain_name,
            )
        )

        if (
            observed_chain is not None
            and jump is not None
            and _rules_match(observed_chain, expected)
        ):
            confirmed.append(expected)
            used_chain_names.add(observed_chain.name)
            used_jump_handles.add(jump.handle)
        else:
            missing.append(expected)

    stale_chains = tuple(
        chain
        for chain in observed.chains
        if chain.name not in used_chain_names
    )
    stale_jumps = tuple(
        jump
        for jump in observed.current_jumps
        if jump.handle not in used_jump_handles
    ) + observed.stale_jumps

    return DeviceFirewallComparison(
        confirmed=tuple(confirmed),
        missing=tuple(missing),
        stale_chains=stale_chains,
        stale_jumps=stale_jumps,
        conflicts=observed.conflicts,
    )


def _rules_match(
    observed: ObservedDeviceFirewallChain,
    expected: DeviceFirewallChainSpec,
) -> bool:
    if len(observed.rules) != len(expected.rules):
        return False
    for actual, desired in zip(observed.rules, expected.rules):
        if (
            actual.match_expr_json != desired.match_expr_json
            or actual.action != desired.action
            or actual.action_json != desired.action_json
            or actual.terminal_fallthrough != desired.terminal_fallthrough
        ):
            return False
    return True
