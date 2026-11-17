"""Composite read-only comparison for currently materialized NG3 nft policy classes.

This is the observation boundary required before a combined structural Executor.
It does not mutate and deliberately treats any still-unclassified owner class as conflict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Iterable

from .device_firewall_compare import DeviceFirewallComparison, compare_device_firewall
from .device_firewall_desired import DeviceFirewallDesiredState
from .device_firewall_structure import (
    DEVICE_FIREWALL_CHILD_COMMENT,
    DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
    DEVICE_FIREWALL_JUMP_COMMENT,
    DEVICE_FIREWALL_RULE_COMMENT,
)
from .interface_identity import InterfaceIdentity
from .local_integration_observation import (
    LOCAL_INTEGRATION_RULE_COMMENT,
    IntegrationLocalComparison,
    compare_integration_local,
)
from .local_integration_policy import IntegrationLocalDesiredState
from .local_publication_observation import (
    LOCAL_PUBLICATION_RULE_COMMENT,
    LocalPublicationComparison,
    compare_local_publication,
)
from .local_publication_policy import LocalPublicationDesiredState
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import NftPayloadScaffoldComparison, compare_payload_nft_scaffold
from .payload_forward_compare import PayloadForwardComparison, compare_payload_forward
from .payload_forward_desired import PayloadForwardDesiredState
from .payload_forward_observation import (
    PAYLOAD_FORWARD_NEW_COMMENT,
    PAYLOAD_FORWARD_RETURN_COMMENT,
)
from .payload_nat_desired import PayloadNatDesiredState
from .payload_nat_observation import (
    PAYLOAD_NAT_RULE_COMMENT,
    PayloadNatComparison,
    compare_payload_nat,
)


@dataclass(frozen=True, slots=True)
class CompositeNftDesiredState:
    profile_forward: PayloadForwardDesiredState
    payload_nat: PayloadNatDesiredState
    device_firewall: DeviceFirewallDesiredState
    local_publication: LocalPublicationDesiredState = field(
        default_factory=lambda: LocalPublicationDesiredState(())
    )
    local_integration: IntegrationLocalDesiredState = field(
        default_factory=lambda: IntegrationLocalDesiredState(())
    )

    def __post_init__(self) -> None:
        if not isinstance(self.profile_forward, PayloadForwardDesiredState):
            raise ValueError("profile_forward must be PayloadForwardDesiredState")
        if not isinstance(self.payload_nat, PayloadNatDesiredState):
            raise ValueError("payload_nat must be PayloadNatDesiredState")
        if not isinstance(self.device_firewall, DeviceFirewallDesiredState):
            raise ValueError("device_firewall must be DeviceFirewallDesiredState")
        if not isinstance(self.local_publication, LocalPublicationDesiredState):
            raise ValueError("local_publication must be LocalPublicationDesiredState")
        if not isinstance(self.local_integration, IntegrationLocalDesiredState):
            raise ValueError("local_integration must be IntegrationLocalDesiredState")


@dataclass(frozen=True, slots=True)
class CompositeNftPolicyConflict:
    reason: str
    object_kind: str | None = None


@dataclass(frozen=True, slots=True)
class CompositeNftPolicyComparison:
    scaffold: NftPayloadScaffoldComparison
    profile_forward: PayloadForwardComparison
    payload_nat: PayloadNatComparison
    device_firewall: DeviceFirewallComparison
    local_publication: LocalPublicationComparison
    local_integration: IntegrationLocalComparison
    conflicts: tuple[CompositeNftPolicyConflict, ...]

    @property
    def desired_confirmed(self) -> bool:
        return (
            self.scaffold.scaffold_confirmed
            and self.profile_forward.desired_confirmed
            and not self.payload_nat.missing
            and not self.payload_nat.stale
            and not self.payload_nat.conflicts
            and self.device_firewall.desired_confirmed
            and self.local_publication.desired_confirmed
            and self.local_integration.desired_confirmed
            and not self.conflicts
        )


def compare_composite_nft_policy(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: CompositeNftDesiredState,
) -> CompositeNftPolicyComparison:
    if not isinstance(desired, CompositeNftDesiredState):
        raise ValueError("desired must be CompositeNftDesiredState")

    current_interfaces = tuple(interfaces)
    scaffold = compare_payload_nft_scaffold(observation)
    if not scaffold.scaffold_confirmed:
        raise ValueError("invariant nft scaffold is not confirmed")

    profile = compare_payload_forward(
        observation, current_interfaces, desired.profile_forward
    )
    nat = compare_payload_nat(
        observation, current_interfaces, desired.payload_nat
    )
    device = compare_device_firewall(
        observation, current_interfaces, desired.device_firewall
    )
    local_publication = compare_local_publication(
        observation, current_interfaces, desired.local_publication
    )
    local_integration = compare_integration_local(
        observation, current_interfaces, desired.local_integration
    )

    conflicts: list[CompositeNftPolicyConflict] = []
    if profile.conflicts:
        conflicts.extend(
            CompositeNftPolicyConflict("Profile forward: " + item.reason, "rule")
            for item in profile.conflicts
        )
    if nat.conflicts:
        conflicts.extend(
            CompositeNftPolicyConflict("payload NAT: " + item.reason, "rule")
            for item in nat.conflicts
        )
    if device.conflicts:
        conflicts.extend(
            CompositeNftPolicyConflict("Device firewall: " + item.reason)
            for item in device.conflicts
        )
    if local_publication.conflicts:
        conflicts.extend(
            CompositeNftPolicyConflict(
                "local publication: " + item.reason,
                "rule",
            )
            for item in local_publication.conflicts
        )
    if local_integration.conflicts:
        conflicts.extend(
            CompositeNftPolicyConflict(
                "local integration: " + item.reason,
                "rule",
            )
            for item in local_integration.conflicts
        )

    # Structural ownership must be checked against the actual observation, not only
    # desired-confirmed chains. Collect every explicitly marked Device child.
    actual_child_names: set[str] = set()
    for item in observation.objects:
        if item.kind != "chain":
            continue
        payload = _payload(item)
        if payload.get("comment") == DEVICE_FIREWALL_CHILD_COMMENT:
            name = payload.get("name")
            if isinstance(name, str) and name:
                actual_child_names.add(name)

    invariant_names = {spec.name for spec in scaffold.confirmed_chains}
    for item in observation.objects:
        payload = _payload(item)
        if item.kind == "chain":
            name = payload.get("name")
            if name in invariant_names:
                continue
            if (
                isinstance(name, str)
                and name in actual_child_names
                and payload.get("comment") == DEVICE_FIREWALL_CHILD_COMMENT
            ):
                continue
            conflicts.append(
                CompositeNftPolicyConflict(
                    "unclassified nft chain in reserved table", item.kind
                )
            )
            continue

        if item.kind != "rule":
            conflicts.append(
                CompositeNftPolicyConflict(
                    "unclassified nft object in reserved table", item.kind
                )
            )
            continue

        chain = payload.get("chain")
        comment = payload.get("comment")
        if chain == "payload_forward" and comment in {
            PAYLOAD_FORWARD_NEW_COMMENT,
            PAYLOAD_FORWARD_RETURN_COMMENT,
            DEVICE_FIREWALL_JUMP_COMMENT,
        }:
            continue
        if chain == "payload_postrouting" and comment == PAYLOAD_NAT_RULE_COMMENT:
            continue
        if (
            chain in {"stack_input", "stack_output"}
            and comment in {
                LOCAL_PUBLICATION_RULE_COMMENT,
                LOCAL_INTEGRATION_RULE_COMMENT,
            }
        ):
            continue
        if (
            isinstance(chain, str)
            and chain in actual_child_names
            and comment in {
                DEVICE_FIREWALL_RULE_COMMENT,
                DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
            }
        ):
            continue
        conflicts.append(
            CompositeNftPolicyConflict(
                "unclassified nft rule in reserved table", item.kind
            )
        )

    return CompositeNftPolicyComparison(
        scaffold=scaffold,
        profile_forward=profile,
        payload_nat=nat,
        device_firewall=device,
        local_publication=local_publication,
        local_integration=local_integration,
        conflicts=tuple(conflicts),
    )


def _payload(item: NftNamespaceObject) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise ValueError("malformed reserved nft object") from None
    if (
        not isinstance(row, dict)
        or set(row) != {item.kind}
        or not isinstance(row[item.kind], dict)
    ):
        raise ValueError("malformed reserved nft object")
    return row[item.kind]
