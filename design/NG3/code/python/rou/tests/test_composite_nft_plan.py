from __future__ import annotations

import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.binding import LogicalPathId
from rou.composite_nft_plan import (
    CompositeNftStepKind,
    select_composite_nft_step,
)
from rou.composite_nft_policy import (
    CompositeNftPolicyComparison,
)
from rou.device_firewall_compare import DeviceFirewallComparison
from rou.device_firewall_desired import DeviceFirewallChainSpec
from rou.device_firewall_structure import (
    ObservedDeviceFirewallChain,
    ObservedDeviceFirewallJump,
)
from rou.interface_identity import InterfaceIdentity
from rou.local_publication_observation import (
    LocalPublicationComparison,
    ObservedLocalPublicationRule,
)
from rou.local_publication_policy import (
    LocalPublicationDesiredState,
    LocalPublicationHook,
    LocalPublicationRuleSpec,
    PublicationProtocol,
)
from rou.nft_namespace_inventory import NftNamespaceStatus
from rou.nft_payload_scaffold import (
    NftPayloadScaffoldComparison,
    PAYLOAD_NFT_SCAFFOLD,
)
from rou.payload_forward_compare import PayloadForwardComparison
from rou.payload_forward_desired import PayloadForwardRuleSpec
from rou.payload_forward_observation import (
    ObservedPayloadForwardRule,
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from rou.payload_nat_desired import PayloadMasqueradeSpec
from rou.payload_nat_observation import (
    ObservedPayloadMasquerade,
    PayloadNatComparison,
)
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_local_observation import (
    ObservedProbeLocalRule,
    ProbeLocalComparison,
)
from rou.probe_policy import ProbeLocalHook, ProbeLocalRuleSpec


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)
PREFIX = IPv4Network("10.0.0.0/8")
PROFILE_SPEC = PayloadForwardRuleSpec(
    PayloadForwardRuleKind.NEW,
    HOST,
    VPN,
    PayloadForwardRemoteField.DESTINATION,
    PREFIX,
)
NAT_SPEC = PayloadMasqueradeSpec(
    LogicalPathId("device", 0, 0),
    HOST,
    VPN,
)
DEVICE_SPEC = DeviceFirewallChainSpec(
    ingress=HOST,
    egress=VPN,
    child_chain_name="dfw_out",
    rules=(),
)
SCAFFOLD = NftPayloadScaffoldComparison(
    namespace_status=NftNamespaceStatus.OWNED,
    confirmed_chains=PAYLOAD_NFT_SCAFFOLD,
    missing_chains=(),
    conflicts=(),
    unclassified_objects=(),
)


def comparison(
    *,
    profile_missing=(),
    profile_stale=(),
    nat_missing=(),
    nat_stale=(),
    device_missing=(),
    device_stale_chains=(),
    device_stale_jumps=(),
    local_missing=(),
    local_stale=(),
    probe_missing=(),
    probe_stale=(),
):
    return CompositeNftPolicyComparison(
        scaffold=SCAFFOLD,
        profile_forward=PayloadForwardComparison(
            confirmed=(),
            missing=profile_missing,
            stale=profile_stale,
            conflicts=(),
        ),
        payload_nat=PayloadNatComparison(
            confirmed=(),
            missing=nat_missing,
            stale=nat_stale,
            conflicts=(),
        ),
        device_firewall=DeviceFirewallComparison(
            confirmed=(),
            missing=device_missing,
            stale_chains=device_stale_chains,
            stale_jumps=device_stale_jumps,
            conflicts=(),
        ),
        local_publication=LocalPublicationComparison(
            confirmed=(),
            missing=local_missing,
            stale=local_stale,
            conflicts=(),
        ),
        probe_local=ProbeLocalComparison(
            confirmed=(),
            missing=probe_missing,
            stale=probe_stale,
            conflicts=(),
        ),
        conflicts=(),
    )


class CompositeNftPlanTests(unittest.TestCase):
    def test_stale_local_publication_precedes_payload_cleanup(self):
        stale_local = ObservedLocalPublicationRule(
            handle=9,
            hook=LocalPublicationHook.INPUT,
            protocol=PublicationProtocol.TCP,
            host_boundary=HOST,
            local_address=IPv4Address("198.51.100.46"),
            local_port=44443,
        )
        stale_profile = ObservedPayloadForwardRule(
            10,
            PayloadForwardRuleKind.NEW,
            HOST,
            VPN,
            PayloadForwardRemoteField.DESTINATION,
            PREFIX,
        )
        step = select_composite_nft_step(
            comparison(
                profile_stale=(stale_profile,),
                local_stale=(stale_local,),
            )
        )
        self.assertEqual(
            step.kind,
            CompositeNftStepKind.APPLY_LOCAL_PUBLICATION,
        )
        self.assertEqual(
            step.local_publication_step.delete_rules[0].handle,
            9,
        )

    def test_stale_probe_local_precedes_payload_cleanup(self):
        owner = ProbePolicyOwner("corp", LogicalPathId("device", 0, 0))
        stale_probe = ObservedProbeLocalRule(
            handle=8,
            hook=ProbeLocalHook.INPUT,
            endpoint=VPN,
            target=IPv4Address("198.51.100.7"),
            conntrack_mark=0x20000001,
        )
        stale_profile = ObservedPayloadForwardRule(
            10,
            PayloadForwardRuleKind.NEW,
            HOST,
            VPN,
            PayloadForwardRemoteField.DESTINATION,
            PREFIX,
        )
        step = select_composite_nft_step(
            comparison(
                profile_stale=(stale_profile,),
                probe_stale=(stale_probe,),
            ),
            probe_local_desired=(
                ProbeLocalRuleSpec(
                    owner=owner,
                    hook=ProbeLocalHook.INPUT,
                    endpoint=VPN,
                    target=IPv4Address("203.0.113.9"),
                    conntrack_mark=0x20000001,
                ),
            ),
        )
        self.assertEqual(step.kind, CompositeNftStepKind.APPLY_PROBE_LOCAL)
        self.assertEqual(step.probe_local_step.delete_rules[0].handle, 8)

    def test_missing_probe_local_is_added_after_payload_and_other_local_work(self):
        owner = ProbePolicyOwner("corp", LogicalPathId("device", 0, 0))
        probe = ProbeLocalRuleSpec(
            owner=owner,
            hook=ProbeLocalHook.INPUT,
            endpoint=VPN,
            target=IPv4Address("198.51.100.7"),
            conntrack_mark=0x20000001,
        )
        step = select_composite_nft_step(
            comparison(
                profile_missing=(PROFILE_SPEC,),
                probe_missing=(probe,),
            ),
            probe_local_desired=(probe,),
        )
        self.assertEqual(step.kind, CompositeNftStepKind.ADD_PROFILE_RULE)

        step = select_composite_nft_step(
            comparison(probe_missing=(probe,)),
            probe_local_desired=(probe,),
        )
        self.assertEqual(step.kind, CompositeNftStepKind.APPLY_PROBE_LOCAL)

    def test_cleanup_precedence_starts_with_stale_profile_admission(self):
        stale_profile = ObservedPayloadForwardRule(
            10,
            PayloadForwardRuleKind.NEW,
            HOST,
            VPN,
            PayloadForwardRemoteField.DESTINATION,
            PREFIX,
        )
        stale_jump = ObservedDeviceFirewallJump(
            11, 1, HOST, VPN, "dfw_old",
        )
        stale_chain = ObservedDeviceFirewallChain(
            "dfw_old", 12, 2, (),
        )
        stale_nat = ObservedPayloadMasquerade(13, HOST, VPN)
        step = select_composite_nft_step(
            comparison(
                profile_stale=(stale_profile,),
                nat_stale=(stale_nat,),
                device_stale_chains=(stale_chain,),
                device_stale_jumps=(stale_jump,),
            )
        )
        self.assertEqual(step.kind, CompositeNftStepKind.DELETE_PROFILE_RULE)
        self.assertEqual(step.handle, 10)

    def test_device_jump_precedes_chain_and_nat_cleanup(self):
        stale_jump = ObservedDeviceFirewallJump(
            11, 1, HOST, VPN, "dfw_old",
        )
        stale_chain = ObservedDeviceFirewallChain(
            "dfw_old", 12, 2, (),
        )
        stale_nat = ObservedPayloadMasquerade(13, HOST, VPN)
        step = select_composite_nft_step(
            comparison(
                nat_stale=(stale_nat,),
                device_stale_chains=(stale_chain,),
                device_stale_jumps=(stale_jump,),
            )
        )
        self.assertEqual(step.kind, CompositeNftStepKind.DELETE_DEVICE_JUMP)

    def test_addition_precedence_is_nat_then_device_then_profile(self):
        step = select_composite_nft_step(
            comparison(
                profile_missing=(PROFILE_SPEC,),
                nat_missing=(NAT_SPEC,),
                device_missing=(DEVICE_SPEC,),
            )
        )
        self.assertEqual(step.kind, CompositeNftStepKind.ADD_NAT_RULE)

        step = select_composite_nft_step(
            comparison(
                profile_missing=(PROFILE_SPEC,),
                device_missing=(DEVICE_SPEC,),
            )
        )
        self.assertEqual(step.kind, CompositeNftStepKind.CREATE_DEVICE_CHAIN)

        step = select_composite_nft_step(
            comparison(profile_missing=(PROFILE_SPEC,))
        )
        self.assertEqual(step.kind, CompositeNftStepKind.ADD_PROFILE_RULE)


    def test_missing_local_publication_is_atomic_step_after_profile_addition(self):
        local_input = LocalPublicationRuleSpec(
            hook=LocalPublicationHook.INPUT,
            protocol=PublicationProtocol.TCP,
            host_boundary=HOST,
            local_address=IPv4Address("198.51.100.46"),
            local_port=44443,
        )
        local_output = LocalPublicationRuleSpec(
            hook=LocalPublicationHook.OUTPUT,
            protocol=PublicationProtocol.TCP,
            host_boundary=HOST,
            local_address=IPv4Address("198.51.100.46"),
            local_port=44443,
        )
        local_desired = LocalPublicationDesiredState(
            (local_input, local_output)
        )

        step = select_composite_nft_step(
            comparison(
                profile_missing=(PROFILE_SPEC,),
                local_missing=(local_input, local_output),
            ),
            local_desired,
        )
        self.assertEqual(
            step.kind,
            CompositeNftStepKind.ADD_PROFILE_RULE,
        )

        step = select_composite_nft_step(
            comparison(
                local_missing=(local_input, local_output),
            ),
            local_desired,
        )
        self.assertEqual(
            step.kind,
            CompositeNftStepKind.APPLY_LOCAL_PUBLICATION,
        )
        self.assertEqual(
            [rule.hook for rule in step.local_publication_step.add_rules],
            [LocalPublicationHook.OUTPUT, LocalPublicationHook.INPUT],
        )

    def test_exact_state_has_no_step(self):
        self.assertIsNone(select_composite_nft_step(comparison()))


if __name__ == "__main__":
    unittest.main()
