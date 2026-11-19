from __future__ import annotations

from ipaddress import IPv4Address
import json
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import ProbePolicyOwner
from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import PAYLOAD_NFT_SCAFFOLD
from rou.probe_policy import (
    ProbeLocalHook,
    ProbeLocalRuleSpec,
    ProbeNetworkPolicyDesiredState,
    ProbeRuleSpec,
)
from rou.probe_precondition import verify_probe_execution_precondition
from rou.structural_policy_mutation import StructuralPolicyPhysicalSnapshot
from rou.structural_routing_inventory import StructuralRoutingObservation


PATH = LogicalPathId("device", 0, 0)
EP = InterfaceIdentity("vpn0", 10)
TARGET = IPv4Address("198.51.100.7")
OWNER = ProbePolicyOwner("corp", PATH)


def _obj(kind, payload, order):
    return NftNamespaceObject(
        kind=kind,
        canonical_json=json.dumps(
            {kind: payload},
            sort_keys=True,
            separators=(",", ":"),
        ),
        source_order=order,
    )


def snapshot():
    scaffold = tuple(
        _obj(
            "chain",
            {
                "family": "ip",
                "table": "vpn_gate",
                "name": spec.name,
                "handle": order,
                "type": spec.chain_type,
                "hook": spec.hook,
                "prio": spec.priority,
                "policy": spec.policy,
                "comment": spec.comment,
            },
            order,
        )
        for order, spec in enumerate(PAYLOAD_NFT_SCAFFOLD, start=1)
    )
    return StructuralPolicyPhysicalSnapshot(
        interfaces=(EP,),
        routing=StructuralRoutingObservation((), (), ()),
        nft=NftNamespaceObservation(
            status=NftNamespaceStatus.OWNED,
            objects=scaffold,
            observed_comment=NG3_NFT_OWNER_COMMENT,
        ),
    )


class ProbeExecutionPreconditionTests(unittest.TestCase):
    def test_empty_probe_plane_is_exact(self):
        result = verify_probe_execution_precondition(
            snapshot(),
            ProbeNetworkPolicyDesiredState((), (), ()),
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(result.interfaces_stable_snapshot, (EP,))

    def test_missing_routing_selector_blocks_execution_readiness(self):
        desired = ProbeNetworkPolicyDesiredState(
            (),
            (
                ProbeRuleSpec(
                    owner=OWNER,
                    priority=0x2000,
                    process_uid=4242,
                    endpoint=EP,
                    target=TARGET,
                    table=0xC0000000,
                ),
            ),
            (),
        )
        result = verify_probe_execution_precondition(
            snapshot(),
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(result.routing.missing_rules), 1)
        self.assertTrue(result.local.desired_confirmed)

    def test_missing_local_admission_blocks_execution_readiness(self):
        desired = ProbeNetworkPolicyDesiredState(
            (),
            (),
            (
                ProbeLocalRuleSpec(
                    owner=OWNER,
                    hook=ProbeLocalHook.OUTPUT,
                    endpoint=EP,
                    target=TARGET,
                    conntrack_mark=0x20000001,
                    process_uid=4242,
                ),
            ),
        )
        result = verify_probe_execution_precondition(
            snapshot(),
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertTrue(result.routing.confirmed)
        self.assertEqual(len(result.local.missing), 1)


if __name__ == "__main__":
    unittest.main()
