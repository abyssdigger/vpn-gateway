from __future__ import annotations

import json
import unittest

from rou.binding import LogicalPathId
from rou.forwarding_gate import ForwardingGateState
from rou.interface_identity import InterfaceIdentity
from rou.nft_namespace_inventory import parse_nft_namespace_ruleset
from rou.payload_nat_desired import PayloadMasqueradeSpec, PayloadNatDesiredState
from rou.payload_nat_mutation import (
    PayloadNatMutationStatus, PayloadNatPhysicalSnapshot,
    converge_payload_nat_step_once,
)


HOST = InterfaceIdentity("host0", 5)
OLD = InterfaceIdentity("tun0", 9)
NEW = InterfaceIdentity("tun0", 11)
SPEC = PayloadMasqueradeSpec(LogicalPathId("device", 0, 0), HOST, NEW)
DESIRED = PayloadNatDesiredState((SPEC,))


def match(key, right):
    return {"match": {"op": "==", "left": {"meta": {"key": key}}, "right": right}}


def rule(handle, iif="5", oif="11", comment="vpn-gate:ng3:payload-nat-v1",
         chain="payload_postrouting"):
    return {"rule": {
        "family": "ip", "table": "vpn_gate", "chain": chain,
        "handle": handle, "comment": comment,
        "expr": [match("iif", iif), match("oif", oif), {"masquerade": None}],
    }}


def base_rows():
    return [
        {"table": {"family": "ip", "name": "vpn_gate",
                   "comment": "vpn-gate:ng3:owner-v1"}},
        {"chain": {"family": "ip", "table": "vpn_gate", "name": "payload_forward",
                   "type": "filter", "hook": "forward", "prio": 0, "policy": "drop",
                   "comment": "vpn-gate:ng3:payload-forward-v1"}},
        {"chain": {"family": "ip", "table": "vpn_gate", "name": "payload_postrouting",
                   "type": "nat", "hook": "postrouting", "prio": 100,
                   "policy": "accept",
                   "comment": "vpn-gate:ng3:payload-postrouting-v1"}},
    ]


class FakeGate:
    def __init__(self, *, lose_at=None):
        self.state = ForwardingGateState.ENABLED
        self.observations = 0
        self.lose_at = lose_at
        self.writes = []

    def observe_forwarding_gate(self):
        self.observations += 1
        if self.observations == self.lose_at:
            return ForwardingGateState.ENABLED
        return self.state

    def set_forwarding_gate(self, value):
        self.writes.append(value)
        self.state = value


class FakeNft:
    def __init__(self, *rules, rows=None):
        self.rows = base_rows() if rows is None else rows
        self.rules = list(rules)
        self.interfaces = (HOST, NEW)
        self.actions = []
        self.next_handle = 100
        self.fail_apply = False
        self.extra_delete = False
        self.duplicate_add = False

    def observe_nat_snapshot(self):
        text = json.dumps({"nftables": [*self.rows, *self.rules]})
        return PayloadNatPhysicalSnapshot(
            parse_nft_namespace_ruleset(text),
            self.interfaces,
        )

    def add_nat_rule(self, spec):
        self.actions.append(("add", spec))
        if self.fail_apply:
            raise RuntimeError("synthetic add failure")
        self.rules.append(rule(self.next_handle, str(spec.ingress.ifindex),
                               str(spec.egress.ifindex)))
        self.next_handle += 1
        if self.duplicate_add:
            self.rules.append(rule(self.next_handle, str(spec.ingress.ifindex),
                                   str(spec.egress.ifindex)))
            self.next_handle += 1

    def delete_nat_rule(self, handle):
        self.actions.append(("delete", handle))
        if self.fail_apply:
            raise RuntimeError("synthetic delete failure")
        self.rules = [r for r in self.rules if r["rule"]["handle"] != handle]
        if self.extra_delete:
            self.rules = []


class PayloadNatMutationTests(unittest.TestCase):
    def attempt(self, backend, gate=None, desired=DESIRED):
        gate = gate or FakeGate()
        result = converge_payload_nat_step_once(gate, backend, desired)
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)
        self.assertEqual(gate.writes, [ForwardingGateState.DISABLED])
        return result

    def test_add_missing_one_rule_and_confirm(self):
        nft = FakeNft()
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFIRMED)
        self.assertTrue(result.confirmed)
        self.assertTrue(result.mutation_attempted)
        self.assertEqual(nft.actions, [("add", SPEC)])

    def test_delete_stale_then_add_new_in_independent_attempt(self):
        nft = FakeNft(rule(30, oif="9"))
        first = self.attempt(nft)
        self.assertEqual(first.status, PayloadNatMutationStatus.STEP_APPLIED)
        self.assertFalse(first.confirmed)
        self.assertEqual(nft.actions, [("delete", 30)])
        second = self.attempt(nft)
        self.assertEqual(second.status, PayloadNatMutationStatus.CONFIRMED)
        self.assertTrue(second.confirmed)
        self.assertEqual(nft.actions, [("delete", 30), ("add", SPEC)])

    def test_confirmed_without_any_write(self):
        nft = FakeNft(rule(30))
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFIRMED)
        self.assertFalse(result.mutation_attempted)
        self.assertEqual(nft.actions, [])

    def test_unknown_forward_rule_blocks_mutation(self):
        nft = FakeNft(rule(90, chain="payload_forward"))
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFLICT)
        self.assertEqual(nft.actions, [])

    def test_unknown_nft_object_blocks_mutation(self):
        extra = {"set": {"family": "ip", "table": "vpn_gate", "name": "foreign"}}
        nft = FakeNft(rows=[*base_rows(), extra])
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFLICT)
        self.assertEqual(nft.actions, [])

    def test_wrong_owned_nat_comment_blocks_mutation(self):
        nft = FakeNft(rule(30, comment="unknown"))
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFLICT)
        self.assertEqual(nft.actions, [])

    def test_duplicate_physical_nat_rules_block_mutation(self):
        nft = FakeNft(rule(30), rule(31))
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFLICT)
        self.assertEqual(nft.actions, [])

    def test_missing_scaffold_blocks_mutation(self):
        nft = FakeNft(rows=base_rows()[:2])
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFLICT)
        self.assertEqual(nft.actions, [])

    def test_pre_write_gate_loss_blocks_mutation(self):
        gate = FakeGate(lose_at=3)
        nft = FakeNft()
        result = self.attempt(nft, gate)
        self.assertEqual(result.status, PayloadNatMutationStatus.BARRIER_LOST)
        self.assertFalse(result.mutation_attempted)
        self.assertEqual(nft.actions, [])

    def test_post_write_gate_loss_prevents_confirmation(self):
        gate = FakeGate(lose_at=4)
        nft = FakeNft()
        result = self.attempt(nft, gate)
        self.assertEqual(result.status, PayloadNatMutationStatus.BARRIER_LOST)
        self.assertFalse(result.confirmed)
        self.assertTrue(result.mutation_attempted)

    def test_failed_delete_reobserves_without_retry(self):
        nft = FakeNft(rule(30, oif="9"))
        nft.fail_apply = True
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.APPLY_FAILED)
        self.assertEqual(len(nft.actions), 1)
        self.assertEqual(result.final.stale[0].handle, 30)

    def test_unrelated_deletion_rejected_as_postcondition_failure(self):
        nft = FakeNft(rule(30, oif="9"), rule(31))
        nft.extra_delete = True
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.POSTCONDITION_FAILED)
        self.assertFalse(result.confirmed)

    def test_extra_duplicate_add_rejected_as_postcondition_failure(self):
        nft = FakeNft()
        nft.duplicate_add = True
        result = self.attempt(nft)
        self.assertEqual(result.status, PayloadNatMutationStatus.POSTCONDITION_FAILED)
        self.assertFalse(result.confirmed)

    def test_invalid_desired_endpoint_blocks_mutation(self):
        nft = FakeNft()
        other = PayloadMasqueradeSpec(SPEC.path_id, HOST, OLD)
        result = self.attempt(nft, desired=PayloadNatDesiredState((other,)))
        self.assertEqual(result.status, PayloadNatMutationStatus.CONFLICT)
        self.assertEqual(nft.actions, [])


if __name__ == "__main__":
    unittest.main()
