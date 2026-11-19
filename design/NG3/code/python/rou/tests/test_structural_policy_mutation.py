from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import json
import unittest

from rou.binding import LogicalPathId
from rou.composite_nft_policy import CompositeNftDesiredState
from rou.device_firewall_desired import DeviceFirewallDesiredState
from rou.forwarding_gate import ForwardingGateState
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.local_publication_policy import LocalPublicationDesiredState
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_policy import ProbeLocalHook, ProbeLocalRuleSpec
from rou.nft_namespace_inventory import (
    NftNamespaceObservation,
    NftNamespaceStatus,
    parse_nft_namespace_ruleset,
)
from rou.payload_forward_desired import PayloadForwardDesiredState
from rou.payload_nat_desired import PayloadNatDesiredState
from rou.payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
    PayloadRoutingDesiredState,
)
from rou.structural_policy_mutation import (
    StructuralPolicyMutationStatus,
    StructuralPolicyPhysicalSnapshot,
    converge_structural_policy_step_once,
    structural_policy_distance,
)
from rou.structural_policy_plan import StructuralPolicyStepKind
from rou.structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    StructuralRoutingObservation,
)


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)
PATH = LogicalPathId("device", 0, 0)
PREFIX = IPv4Network("10.0.0.0/8")

GUARD = ManagedRouteSpec(
    table=0x80000000,
    destination=IPv4Network("0.0.0.0/0"),
    route_type=ManagedRouteType.BLACKHOLE,
    protocol=201,
    metric=0xFFFFFFFF,
)
PATH_ROUTE = ManagedRouteSpec(
    table=0x80000000,
    destination=PREFIX,
    route_type=ManagedRouteType.UNICAST,
    protocol=202,
    metric=1,
    path_id=PATH,
    endpoint=VPN,
)
RULE = ManagedRuleSpec(
    priority=0x4000,
    ingress=HOST,
    destination=PREFIX,
    table=0x80000000,
)
ROUTING_DESIRED = PayloadRoutingDesiredState(
    host_boundary=HOST,
    routes=(GUARD, PATH_ROUTE),
    rules=(RULE,),
)
NFT_DESIRED = CompositeNftDesiredState(
    PayloadForwardDesiredState(()),
    PayloadNatDesiredState(()),
    DeviceFirewallDesiredState(()),
    LocalPublicationDesiredState(()),
)

PROBE_OWNER = ProbePolicyOwner("corp", PATH)
PROBE_LOCAL_SPEC = ProbeLocalRuleSpec(
    owner=PROBE_OWNER,
    hook=ProbeLocalHook.INPUT,
    endpoint=VPN,
    target=IPv4Address("198.51.100.7"),
    conntrack_mark=0x20000001,
)
PROBE_NFT_DESIRED = CompositeNftDesiredState(
    PayloadForwardDesiredState(()),
    PayloadNatDesiredState(()),
    DeviceFirewallDesiredState(()),
    LocalPublicationDesiredState(()),
    probe_local=(PROBE_LOCAL_SPEC,),
)


def scaffold_observation():
    return parse_nft_namespace_ruleset(json.dumps({"nftables": [
        {"table": {
            "family": "ip", "name": "vpn_gate",
            "comment": "vpn-gate:ng3:owner-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "stack_input",
            "type": "filter", "hook": "input", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:stack-input-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "payload_forward",
            "type": "filter", "hook": "forward", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:payload-forward-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "stack_output",
            "type": "filter", "hook": "output", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:stack-output-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "payload_postrouting",
            "type": "nat", "hook": "postrouting", "prio": 100,
            "policy": "accept",
            "comment": "vpn-gate:ng3:payload-postrouting-v1",
        }},
    ]}))


def probe_local_observation():
    payload = json.loads(json.dumps({"nftables": [
        {"table": {
            "family": "ip", "name": "vpn_gate",
            "comment": "vpn-gate:ng3:owner-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "stack_input",
            "type": "filter", "hook": "input", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:stack-input-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "payload_forward",
            "type": "filter", "hook": "forward", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:payload-forward-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "stack_output",
            "type": "filter", "hook": "output", "prio": 0,
            "policy": "drop", "comment": "vpn-gate:ng3:stack-output-v1",
        }},
        {"chain": {
            "family": "ip", "table": "vpn_gate", "name": "payload_postrouting",
            "type": "nat", "hook": "postrouting", "prio": 100,
            "policy": "accept",
            "comment": "vpn-gate:ng3:payload-postrouting-v1",
        }},
        {"rule": {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "stack_input",
            "handle": 50,
            "comment": "vpn-gate:ng3:probe-local-v1",
            "expr": [
                {"match": {
                    "left": {"meta": {"key": "iif"}},
                    "op": "==",
                    "right": "vpn0",
                }},
                {"match": {
                    "left": {
                        "payload": {"protocol": "ip", "field": "saddr"}
                    },
                    "op": "==",
                    "right": "198.51.100.7",
                }},
                {"match": {
                    "left": {
                        "payload": {"protocol": "ip", "field": "protocol"}
                    },
                    "op": "==",
                    "right": 1,
                }},
                {"match": {
                    "left": {"ct": {"key": "mark"}},
                    "op": "==",
                    "right": 0x20000001,
                }},
                {"accept": None},
            ],
        }},
    ]}))
    return parse_nft_namespace_ruleset(json.dumps(payload))


OBS_GUARD = ObservedManagedRoute(
    table=GUARD.table,
    destination=GUARD.destination,
    route_type=GUARD.route_type,
    protocol=GUARD.protocol,
    metric=GUARD.metric,
    scope=0,
    endpoint=None,
    gateway=None,
    onlink=False,
)
OBS_PATH = ObservedManagedRoute(
    table=PATH_ROUTE.table,
    destination=PATH_ROUTE.destination,
    route_type=PATH_ROUTE.route_type,
    protocol=PATH_ROUTE.protocol,
    metric=PATH_ROUTE.metric,
    scope=253,
    endpoint=VPN,
    gateway=None,
    onlink=False,
)
OBS_RULE = ObservedManagedRule(
    priority=RULE.priority,
    table=RULE.table,
    ingress=HOST,
    destination=RULE.destination,
    fwmark=None,
    fwmask=None,
)


def snapshot(*, routes=(), rules=(), interfaces=(HOST, VPN), nft=None):
    return StructuralPolicyPhysicalSnapshot(
        interfaces=interfaces,
        routing=StructuralRoutingObservation(
            routes=routes,
            rules=rules,
            conflicts=(),
        ),
        nft=scaffold_observation() if nft is None else nft,
    )


class FakeGate:
    def __init__(self):
        self.state = ForwardingGateState.ENABLED
        self.writes = []

    def observe_forwarding_gate(self):
        return self.state

    def set_forwarding_gate(self, desired):
        self.writes.append(desired)
        self.state = desired


class FakeBackend:
    def __init__(self, *snapshots, fail_action=None):
        self.snapshots = list(snapshots)
        self.actions = []
        self.fail_action = fail_action

    def observe_structural_snapshot(self):
        if not self.snapshots:
            raise AssertionError("unexpected structural observation")
        return self.snapshots.pop(0)

    def _act(self, name, value):
        self.actions.append((name, value))
        if self.fail_action == name:
            raise RuntimeError("synthetic apply failure")

    def add_route(self, value): self._act("add_route", value)
    def delete_route(self, value): self._act("delete_route", value)
    def add_rule(self, value): self._act("add_rule", value)
    def delete_rule(self, value): self._act("delete_rule", value)
    def delete_profile_rule(self, value): self._act("delete_profile_rule", value)
    def add_profile_rule(self, value): self._act("add_profile_rule", value)
    def delete_device_jump(self, value): self._act("delete_device_jump", value)
    def delete_device_child_chain(self, value): self._act("delete_device_child_chain", value)
    def create_device_chain(self, value): self._act("create_device_chain", value)
    def delete_nat_rule(self, value): self._act("delete_nat_rule", value)
    def add_nat_rule(self, value): self._act("add_nat_rule", value)
    def apply_local_publication_step(self, value):
        self._act("apply_local_publication_step", value)
    def apply_integration_local_step(self, value):
        self._act("apply_integration_local_step", value)
    def apply_probe_local_step(self, value):
        self._act("apply_probe_local_step", value)


class StructuralPolicyMutationTests(unittest.TestCase):
    def attempt(self, backend, gate=None):
        gate = gate or FakeGate()
        result = converge_structural_policy_step_once(
            gate,
            backend,
            ROUTING_DESIRED,
            NFT_DESIRED,
            NG3_LINUX_POLICY_PLATFORM,
        )
        return gate, result

    def test_probe_local_diff_counts_in_structural_distance(self):
        from rou.structural_policy_mutation import compare_structural_policy

        comparison = compare_structural_policy(
            snapshot(),
            ROUTING_DESIRED,
            PROBE_NFT_DESIRED,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertEqual(len(comparison.nft.probe_local.missing), 1)
        self.assertEqual(
            structural_policy_distance(comparison),
            4,
        )

    def test_probe_local_repair_uses_structural_backend_delegate(self):
        exact_routes = (OBS_GUARD, OBS_PATH)
        backend = FakeBackend(
            snapshot(
                routes=exact_routes,
                rules=(OBS_RULE,),
            ),
            snapshot(
                routes=exact_routes,
                rules=(OBS_RULE,),
                nft=probe_local_observation(),
            ),
            snapshot(
                routes=exact_routes,
                rules=(OBS_RULE,),
                nft=probe_local_observation(),
            ),
        )
        gate = FakeGate()
        result = converge_structural_policy_step_once(
            gate,
            backend,
            ROUTING_DESIRED,
            PROBE_NFT_DESIRED,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertEqual(
            result.status,
            StructuralPolicyMutationStatus.CONFIRMED,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(
            backend.actions[0][0],
            "apply_probe_local_step",
        )
        self.assertEqual(gate.state, ForwardingGateState.ENABLED)

    def test_absent_invariant_scaffold_is_precondition_not_conflict(self):
        backend = FakeBackend(
            StructuralPolicyPhysicalSnapshot(
                interfaces=(HOST, VPN),
                routing=StructuralRoutingObservation(
                    routes=(),
                    rules=(),
                    conflicts=(),
                ),
                nft=NftNamespaceObservation(
                    status=NftNamespaceStatus.ABSENT,
                ),
            )
        )
        gate, result = self.attempt(backend)

        self.assertEqual(
            result.status,
            StructuralPolicyMutationStatus.PRECONDITION_FAILED,
        )
        self.assertEqual(
            result.diagnostic,
            "invariant nft scaffold is not confirmed",
        )
        self.assertEqual(backend.actions, [])
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)

    def test_one_nonfinal_step_keeps_forwarding_closed(self):
        backend = FakeBackend(
            snapshot(),
            snapshot(routes=(OBS_GUARD,)),
        )
        gate, result = self.attempt(backend)

        self.assertEqual(result.status, StructuralPolicyMutationStatus.STEP_APPLIED)
        self.assertEqual(result.step.kind, StructuralPolicyStepKind.ADD_GUARD_ROUTE)
        self.assertEqual(backend.actions, [("add_route", GUARD)])
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)
        self.assertEqual(gate.writes, [ForwardingGateState.DISABLED])

    def test_last_rpdb_step_activates_only_after_exact_postcondition(self):
        exact_routes = (OBS_GUARD, OBS_PATH)
        backend = FakeBackend(
            snapshot(routes=exact_routes),
            snapshot(routes=exact_routes, rules=(OBS_RULE,)),
            snapshot(routes=exact_routes, rules=(OBS_RULE,)),
        )
        gate, result = self.attempt(backend)

        self.assertEqual(result.status, StructuralPolicyMutationStatus.CONFIRMED)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.step.kind, StructuralPolicyStepKind.ADD_ROUTING_RULE)
        self.assertEqual(backend.actions, [("add_rule", RULE)])
        self.assertEqual(
            gate.writes,
            [ForwardingGateState.DISABLED, ForwardingGateState.ENABLED],
        )
        self.assertEqual(gate.state, ForwardingGateState.ENABLED)

    def test_apply_exception_can_confirm_if_fresh_state_made_progress(self):
        exact_routes = (OBS_GUARD, OBS_PATH)
        backend = FakeBackend(
            snapshot(routes=exact_routes),
            snapshot(routes=exact_routes, rules=(OBS_RULE,)),
            snapshot(routes=exact_routes, rules=(OBS_RULE,)),
            fail_action="add_rule",
        )
        gate, result = self.attempt(backend)

        self.assertEqual(result.status, StructuralPolicyMutationStatus.CONFIRMED)
        self.assertTrue(result.confirmed)
        self.assertIn("apply raised RuntimeError", result.diagnostic)
        self.assertEqual(gate.state, ForwardingGateState.ENABLED)

    def test_post_activation_drift_recloses_forwarding(self):
        exact_routes = (OBS_GUARD, OBS_PATH)
        backend = FakeBackend(
            snapshot(routes=exact_routes, rules=(OBS_RULE,)),
            snapshot(routes=exact_routes),
        )
        gate, result = self.attempt(backend)

        self.assertEqual(
            result.status,
            StructuralPolicyMutationStatus.FINAL_VERIFICATION_FAILED,
        )
        self.assertFalse(result.confirmed)
        self.assertIsNotNone(result.safety_reclose)
        self.assertTrue(result.safety_reclose.confirmed)
        self.assertEqual(
            gate.writes,
            [
                ForwardingGateState.DISABLED,
                ForwardingGateState.ENABLED,
                ForwardingGateState.DISABLED,
            ],
        )
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)

    def test_interface_drift_after_write_rejects_progress_and_keeps_gate_closed(self):
        extra_old = InterfaceIdentity("aux0", 30)
        extra_new = InterfaceIdentity("aux0", 31)
        backend = FakeBackend(
            snapshot(
                routes=(OBS_GUARD, OBS_PATH),
                interfaces=(HOST, VPN, extra_old),
            ),
            snapshot(
                routes=(OBS_GUARD, OBS_PATH),
                rules=(OBS_RULE,),
                interfaces=(HOST, VPN, extra_new),
            ),
        )
        gate, result = self.attempt(backend)

        self.assertEqual(
            result.status,
            StructuralPolicyMutationStatus.POSTCONDITION_FAILED,
        )
        self.assertFalse(result.confirmed)
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)
        self.assertEqual(gate.writes, [ForwardingGateState.DISABLED])


if __name__ == "__main__":
    unittest.main()
