from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import json
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import (
    ProbePolicyOwner,
    WireGuardPeerProbeOwner,
)
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
from rou.probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
    require_probe_execution_context,
    verify_probe_execution_precondition,
    verify_probe_execution_precondition_scoped,
)
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

    def test_generic_execution_gate_accepts_distinct_peer_owner(self):
        peer_owner = WireGuardPeerProbeOwner("device", "edge-a")
        context = ProbeExecutionContextKey(
            peer_owner,
            ProbeRuleSpec(
                owner=peer_owner,
                priority=0x2000,
                process_uid=4242,
                endpoint=EP,
                target=TARGET,
                table=0xC0000000,
            ).mechanism,
            TARGET,
            EP,
        )
        precondition = ProbeExecutionPrecondition(
            routing=type("Routing", (), {"confirmed": True})(),
            local=type("Local", (), {"desired_confirmed": True})(),
            interfaces_stable_snapshot=(EP,),
            contexts=frozenset({context}),
        )
        require_probe_execution_context(precondition, context)
        with self.assertRaisesRegex(RuntimeError, "differs"):
            require_probe_execution_context(
                precondition,
                ProbeExecutionContextKey(
                    peer_owner,
                    context.mechanism,
                    IPv4Address("198.51.100.8"),
                    EP,
                ),
            )

    def test_routing_and_local_owner_sets_must_match(self):
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
        with self.assertRaisesRegex(
            ValueError,
            "owner sets do not match",
        ):
            verify_probe_execution_precondition(
                snapshot(),
                desired,
                NG3_LINUX_POLICY_PLATFORM,
            )

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
        self.assertEqual(len(result.local.missing), 2)


class ProbeScopedExecutionPreconditionTests(unittest.TestCase):
    @staticmethod
    def _peer_owner():
        return WireGuardPeerProbeOwner("device", "edge-a")

    @staticmethod
    def _rule(owner, priority, table):
        return ProbeRuleSpec(
            owner=owner,
            priority=priority,
            process_uid=4242,
            endpoint=EP,
            target=TARGET,
            table=table,
        )

    @staticmethod
    def _locals(owner):
        return (
            ProbeLocalRuleSpec(
                owner=owner,
                hook=ProbeLocalHook.OUTPUT,
                endpoint=EP,
                target=TARGET,
                conntrack_mark=0x20000001,
                process_uid=4242,
            ),
            ProbeLocalRuleSpec(
                owner=owner,
                hook=ProbeLocalHook.INPUT,
                endpoint=EP,
                target=TARGET,
                conntrack_mark=0x20000001,
            ),
        )

    @staticmethod
    def _observed(rule):
        return ObservedManagedRule(
            priority=rule.priority,
            table=rule.table,
            ingress=None,
            destination=IPv4Network(f"{rule.target}/32"),
            uid_start=rule.process_uid,
            uid_end=rule.process_uid,
            ipproto=1,
            egress=rule.endpoint,
        )

    def _full_desired(self):
        peer_owner = self._peer_owner()
        profile_rule = self._rule(OWNER, 0x2000, 0xC0000000)
        peer_rule = self._rule(peer_owner, 0x2001, 0xC0000001)
        return (
            peer_owner,
            profile_rule,
            peer_rule,
            ProbeNetworkPolicyDesiredState(
                (),
                (profile_rule, peer_rule),
                self._locals(OWNER) + self._locals(peer_owner),
            ),
        )

    def test_exact_siblings_confirm_each_owner_and_share_physical_local_rules(self):
        peer_owner, profile_rule, peer_rule, desired = self._full_desired()
        current = snapshot(
            routing_rules=(
                self._observed(profile_rule),
                self._observed(peer_rule),
            ),
            local_exact=True,
        )

        profile = verify_probe_execution_precondition_scoped(
            current,
            desired,
            frozenset({OWNER}),
            NG3_LINUX_POLICY_PLATFORM,
        )
        peer = verify_probe_execution_precondition_scoped(
            current,
            desired,
            frozenset({peer_owner}),
            NG3_LINUX_POLICY_PLATFORM,
        )

        self.assertTrue(profile.confirmed)
        self.assertTrue(peer.confirmed)
        self.assertEqual(profile.owners, frozenset({OWNER}))
        self.assertEqual(peer.owners, frozenset({peer_owner}))
        self.assertEqual(len(profile.local.confirmed), 1)
        self.assertEqual(len(peer.local.confirmed), 1)

    def test_missing_sibling_does_not_block_requested_owner_but_legacy_union_fails(self):
        peer_owner, profile_rule, _peer_rule, desired = self._full_desired()
        current = snapshot(
            routing_rules=(self._observed(profile_rule),),
            local_exact=True,
        )

        scoped = verify_probe_execution_precondition_scoped(
            current,
            desired,
            frozenset({OWNER}),
            NG3_LINUX_POLICY_PLATFORM,
        )
        legacy = verify_probe_execution_precondition(
            current,
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )

        self.assertTrue(scoped.confirmed)
        self.assertFalse(legacy.confirmed)
        self.assertEqual(scoped.routing.missing_rules, ())
        self.assertEqual(len(legacy.routing.missing_rules), 1)
        self.assertIn(peer_owner, legacy.owners)

    def test_missing_requested_owner_blocks_scoped_readiness(self):
        peer_owner, _profile_rule, peer_rule, desired = self._full_desired()
        current = snapshot(
            routing_rules=(self._observed(peer_rule),),
            local_exact=True,
        )

        scoped = verify_probe_execution_precondition_scoped(
            current,
            desired,
            frozenset({OWNER}),
            NG3_LINUX_POLICY_PLATFORM,
        )

        self.assertFalse(scoped.confirmed)
        self.assertEqual(len(scoped.routing.missing_rules), 1)
        self.assertNotIn(peer_owner, scoped.owners)

    def test_unknown_reserved_sibling_state_blocks_every_scoped_owner(self):
        peer_owner, profile_rule, peer_rule, desired = self._full_desired()
        unknown_rule = self._rule(
            WireGuardPeerProbeOwner("device", "unknown"),
            0x2002,
            0xC0000002,
        )
        current = snapshot(
            routing_rules=(
                self._observed(profile_rule),
                self._observed(peer_rule),
                self._observed(unknown_rule),
            ),
            local_exact=True,
        )

        for requested in (OWNER, peer_owner):
            with self.subTest(requested=requested):
                scoped = verify_probe_execution_precondition_scoped(
                    current,
                    desired,
                    frozenset({requested}),
                    NG3_LINUX_POLICY_PLATFORM,
                )
                self.assertFalse(scoped.confirmed)
                self.assertEqual(len(scoped.routing.stale_rules), 1)



if __name__ == "__main__":
    unittest.main()
