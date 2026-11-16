from __future__ import annotations

import json
import unittest

from rou.device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallDesiredState,
    DeviceFirewallRuleSpec,
)
from rou.device_firewall_mutation import (
    DeviceFirewallMutationStatus,
    DeviceFirewallPhysicalSnapshot,
    converge_device_firewall_step_once,
)
from rou.device_firewall_structure import (
    DEVICE_FIREWALL_CHILD_COMMENT,
    DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
    DEVICE_FIREWALL_JUMP_COMMENT,
    DeviceFirewallRuleAction,
)
from rou.forwarding_gate import ForwardingGateState
from rou.interface_identity import InterfaceIdentity
from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import PAYLOAD_NFT_SCAFFOLD


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)
OTHER = InterfaceIdentity("vpn1", 30)
CHAIN = "dfw_out"


class FakeGate:
    def __init__(self, states):
        self.states = list(states)
        self.set_calls = []

    def observe_forwarding_gate(self):
        value = self.states.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def set_forwarding_gate(self, desired):
        self.set_calls.append(desired)


class FakeFirewallBackend:
    def __init__(
        self,
        snapshots,
        *,
        delete_jump_error=None,
        delete_chain_error=None,
        create_error=None,
    ):
        self.snapshots = list(snapshots)
        self.delete_jump_error = delete_jump_error
        self.delete_chain_error = delete_chain_error
        self.create_error = create_error
        self.calls = []

    def observe_device_firewall_snapshot(self):
        value = self.snapshots.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def delete_device_jump(self, handle):
        self.calls.append(("delete-jump", handle))
        if self.delete_jump_error:
            raise self.delete_jump_error

    def delete_device_child_chain(self, name):
        self.calls.append(("delete-chain", name))
        if self.delete_chain_error:
            raise self.delete_chain_error

    def create_device_chain(self, spec):
        self.calls.append(("create-chain", spec.child_chain_name))
        if self.create_error:
            raise self.create_error


def obj(kind: str, payload: dict, order: int) -> NftNamespaceObject:
    return NftNamespaceObject(
        kind=kind,
        canonical_json=json.dumps(
            {kind: payload},
            sort_keys=True,
            separators=(",", ":"),
        ),
        source_order=order,
    )


def scaffold_objects():
    values = []
    for order, spec in enumerate(PAYLOAD_NFT_SCAFFOLD, start=1):
        values.append(
            obj(
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
        )
    return tuple(values)


def iface(key: str, value: str) -> dict:
    return {
        "match": {
            "op": "==",
            "left": {"meta": {"key": key}},
            "right": value,
        }
    }


def child(order=10):
    return obj(
        "chain",
        {
            "family": "ip",
            "table": "vpn_gate",
            "name": CHAIN,
            "handle": 50,
            "comment": DEVICE_FIREWALL_CHILD_COMMENT,
        },
        order,
    )


def jump(*, egress="vpn0", order=11, handle=60):
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "payload_forward",
            "handle": handle,
            "comment": DEVICE_FIREWALL_JUMP_COMMENT,
            "expr": [
                iface("iif", "host0"),
                iface("oif", egress),
                {"jump": {"target": CHAIN}},
            ],
        },
        order,
    )


def fallthrough(order=12):
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": CHAIN,
            "handle": 70,
            "comment": DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
            "expr": [{"drop": None}],
        },
        order,
    )


def snapshot(*extra, interfaces=(HOST, VPN)):
    return DeviceFirewallPhysicalSnapshot(
        NftNamespaceObservation(
            status=NftNamespaceStatus.OWNED,
            objects=scaffold_objects() + tuple(extra),
            observed_comment=NG3_NFT_OWNER_COMMENT,
        ),
        interfaces,
    )


def desired():
    terminal = DeviceFirewallRuleSpec(
        match_expr_json=(),
        action=DeviceFirewallRuleAction.DROP,
        action_json='{"drop":null}',
        terminal_fallthrough=True,
    )
    return DeviceFirewallDesiredState(
        chains=(
            DeviceFirewallChainSpec(
                ingress=HOST,
                egress=VPN,
                child_chain_name=CHAIN,
                rules=(terminal,),
            ),
        )
    )


EXACT = snapshot(child(), jump(), fallthrough())
MISSING = snapshot()
CHAIN_ONLY = snapshot(child(), fallthrough())
STALE_JUMP = snapshot(
    child(),
    jump(egress="vpn1"),
    fallthrough(),
    interfaces=(HOST, VPN, OTHER),
)


class DeviceFirewallMutationTests(unittest.TestCase):
    def test_exact_state_is_noop_confirmed(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        backend = FakeFirewallBackend((EXACT,))
        result = converge_device_firewall_step_once(
            gate,
            backend,
            desired(),
        )
        self.assertTrue(result.confirmed)
        self.assertFalse(result.mutation_attempted)
        self.assertEqual(backend.calls, [])

    def test_stale_jump_is_deleted_before_stale_chain(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        backend = FakeFirewallBackend(
            (
                STALE_JUMP,
                snapshot(
                    child(),
                    fallthrough(),
                    interfaces=(HOST, VPN, OTHER),
                ),
            )
        )
        result = converge_device_firewall_step_once(
            gate,
            backend,
            desired(),
        )
        self.assertEqual(
            result.status,
            DeviceFirewallMutationStatus.STEP_APPLIED,
        )
        self.assertEqual(backend.calls, [("delete-jump", 60)])

    def test_unreferenced_stale_chain_is_deleted_next(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        backend = FakeFirewallBackend((CHAIN_ONLY, MISSING))
        result = converge_device_firewall_step_once(
            gate,
            backend,
            desired(),
        )
        self.assertEqual(
            result.status,
            DeviceFirewallMutationStatus.STEP_APPLIED,
        )
        self.assertEqual(backend.calls, [("delete-chain", CHAIN)])

    def test_missing_chain_is_created_as_one_step(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        backend = FakeFirewallBackend((MISSING, EXACT))
        result = converge_device_firewall_step_once(
            gate,
            backend,
            desired(),
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(backend.calls, [("create-chain", CHAIN)])

    def test_foreign_policy_rule_blocks_mutation(self):
        foreign = obj(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_postrouting",
                "handle": 90,
                "comment": "vpn-gate:ng3:payload-nat-v1",
                "expr": [{"masquerade": None}],
            },
            20,
        )
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        backend = FakeFirewallBackend((snapshot(foreign),))
        result = converge_device_firewall_step_once(
            gate,
            backend,
            desired(),
        )
        self.assertEqual(
            result.status,
            DeviceFirewallMutationStatus.CONFLICT,
        )
        self.assertEqual(backend.calls, [])

    def test_barrier_loss_prevents_write(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.ENABLED,
            )
        )
        backend = FakeFirewallBackend((MISSING,))
        result = converge_device_firewall_step_once(
            gate,
            backend,
            desired(),
        )
        self.assertEqual(
            result.status,
            DeviceFirewallMutationStatus.BARRIER_LOST,
        )
        self.assertEqual(backend.calls, [])

    def test_apply_error_can_still_confirm_from_fresh_state(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        backend = FakeFirewallBackend(
            (MISSING, EXACT),
            create_error=RuntimeError("wrapper failed after apply"),
        )
        result = converge_device_firewall_step_once(
            gate,
            backend,
            desired(),
        )
        self.assertTrue(result.confirmed)
        self.assertIn("independently", result.diagnostic or "")


if __name__ == "__main__":
    unittest.main()
