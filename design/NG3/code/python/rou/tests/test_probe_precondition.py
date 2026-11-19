from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
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
from rou.probe_local_observation import PROBE_LOCAL_RULE_COMMENT
from rou.probe_policy import (
    ProbeLocalHook,
    ProbeLocalRuleSpec,
    ProbeNetworkPolicyDesiredState,
    ProbeRuleSpec,
)
from rou.probe_precondition import verify_probe_execution_precondition
from rou.structural_policy_mutation import StructuralPolicyPhysicalSnapshot
from rou.structural_routing_inventory import (
    ObservedManagedRule,
    StructuralRoutingObservation,
)


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


def _local_rules():
    return (
        ProbeLocalRuleSpec(
            owner=OWNER,
            hook=ProbeLocalHook.OUTPUT,
            endpoint=EP,
            target=TARGET,
            conntrack_mark=0x20000001,
            process_uid=4242,
        ),
        ProbeLocalRuleSpec(
            owner=OWNER,
            hook=ProbeLocalHook.INPUT,
            endpoint=EP,
            target=TARGET,
            conntrack_mark=0x20000001,
        ),
    )


def _output_rule(handle=20):
    return _obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "stack_output",
            "handle": handle,
            "comment": PROBE_LOCAL_RULE_COMMENT,
            "expr": [
                {"match": {"left": {"meta": {"key": "skuid"}}, "op": "==", "right": 4242}},
                {"match": {"left": {"meta": {"key": "oif"}}, "op": "==", "right": "vpn0"}},
                {"match": {"left": {"payload": {"field": "daddr", "protocol": "ip"}}, "op": "==", "right": str(TARGET)}},
                {"match": {"left": {"payload": {"field": "protocol", "protocol": "ip"}}, "op": "==", "right": 1}},
                {"mangle": {"key": {"ct": {"key": "mark"}}, "value": 0x20000001}},
                {"accept": None},
            ],
        },
        handle,
    )


def _input_rule(handle=21):
    return _obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "stack_input",
            "handle": handle,
            "comment": PROBE_LOCAL_RULE_COMMENT,
            "expr": [
                {"match": {"left": {"meta": {"key": "iif"}}, "op": "==", "right": "vpn0"}},
                {"match": {"left": {"payload": {"field": "saddr", "protocol": "ip"}}, "op": "==", "right": str(TARGET)}},
                {"match": {"left": {"payload": {"field": "protocol", "protocol": "ip"}}, "op": "==", "right": 1}},
                {"match": {"left": {"ct": {"key": "mark"}}, "op": "==", "right": 0x20000001}},
                {"accept": None},
            ],
        },
        handle,
    )


def snapshot(*, routing_rules=(), local_exact=False):
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
        routing=StructuralRoutingObservation((), tuple(routing_rules), ()),
        nft=NftNamespaceObservation(
            status=NftNamespaceStatus.OWNED,
            objects=(
                scaffold + ((_output_rule(), _input_rule()) if local_exact else ())
            ),
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
        rule = ProbeRuleSpec(
            owner=OWNER,
            priority=0x2000,
            process_uid=4242,
            endpoint=EP,
            target=TARGET,
            table=0xC0000000,
        )
        desired = ProbeNetworkPolicyDesiredState(
            (),
            (rule,),
            _local_rules(),
        )
        result = verify_probe_execution_precondition(
            snapshot(local_exact=True),
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(len(result.routing.missing_rules), 1)
        self.assertTrue(result.local.desired_confirmed)

    def test_missing_local_admission_blocks_execution_readiness(self):
        rule = ProbeRuleSpec(
            owner=OWNER,
            priority=0x2000,
            process_uid=4242,
            endpoint=EP,
            target=TARGET,
            table=0xC0000000,
        )
        observed_rule = ObservedManagedRule(
            priority=rule.priority,
            table=rule.table,
            ingress=None,
            destination=IPv4Network(f"{TARGET}/32"),
            uid_start=rule.process_uid,
            uid_end=rule.process_uid,
            ipproto=1,
            egress=rule.endpoint,
        )
        desired = ProbeNetworkPolicyDesiredState(
            (),
            (rule,),
            _local_rules(),
        )
        result = verify_probe_execution_precondition(
            snapshot(routing_rules=(observed_rule,)),
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertFalse(result.confirmed)
        self.assertTrue(result.routing.confirmed)
        self.assertEqual(len(result.local.missing), 1)


if __name__ == "__main__":
    unittest.main()
