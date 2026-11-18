from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from rou.forwarding_gate import ForwardingGateState
from rou.network_policy_activation import (
    NetworkPolicyActivationStatus,
    activate_network_policy,
)
from rou.nft_namespace_inventory import parse_nft_namespace_ruleset


def scaffold_rows():
    return [
        {"table": {
            "family": "ip",
            "name": "vpn_gate",
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
    ]


def observation(rows):
    return parse_nft_namespace_ruleset(
        json.dumps({"nftables": rows})
    )


class FakeGate:
    def __init__(self):
        self.state = ForwardingGateState.ENABLED
        self.writes = []
        self.fail_disable = False

    def observe_forwarding_gate(self):
        return self.state

    def set_forwarding_gate(self, desired):
        self.writes.append(desired)
        if desired is ForwardingGateState.DISABLED and self.fail_disable:
            return
        self.state = desired


class FakeScaffold:
    def __init__(self, current):
        self.current = current
        self.actions = []
        self.observe_error = None

    def observe_nft_namespace(self):
        if self.observe_error is not None:
            raise self.observe_error
        return self.current

    def create_payload_scaffold(self):
        self.actions.append(("create",))
        self.current = observation(scaffold_rows())

    def add_payload_scaffold_chains(self, missing):
        self.actions.append(("repair", tuple(spec.name for spec in missing)))
        self.current = observation(scaffold_rows())


def confirmed_transaction():
    result = Mock()
    result.confirmed = True
    result.diagnostic = None
    return result


def failed_transaction(diagnostic="synthetic structural failure"):
    result = Mock()
    result.confirmed = False
    result.diagnostic = diagnostic
    return result


class NetworkPolicyActivationTests(unittest.TestCase):
    def invoke(self, gate, scaffold, transaction):
        def run_structural(*args):
            if transaction.confirmed:
                gate.state = ForwardingGateState.ENABLED
            return transaction

        with patch(
            "rou.network_policy_activation.converge_structural_policy",
            side_effect=run_structural,
        ) as structural:
            result = activate_network_policy(
                gate,
                scaffold,
                object(),
                object(),
                object(),
                object(),
            )
        return result, structural

    def test_absent_scaffold_is_bootstrapped_before_structural_transaction(self):
        gate = FakeGate()
        scaffold = FakeScaffold(observation([]))
        transaction = confirmed_transaction()

        result, structural = self.invoke(gate, scaffold, transaction)

        self.assertEqual(result.status, NetworkPolicyActivationStatus.READY)
        self.assertTrue(result.ready)
        self.assertEqual(scaffold.actions, [("create",)])
        structural.assert_called_once()
        self.assertTrue(result.scaffold_prepare.confirmed)
        self.assertEqual(gate.state, ForwardingGateState.ENABLED)

    def test_exact_scaffold_with_policy_objects_skips_scaffold_only_repair(self):
        gate = FakeGate()
        rows = scaffold_rows()
        rows.append({
            "rule": {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_forward",
                "handle": 10,
                "comment": "vpn-gate:ng3:payload-forward-new-v1",
                "expr": [],
            }
        })
        scaffold = FakeScaffold(observation(rows))

        with (
            patch(
                "rou.network_policy_activation.prepare_payload_nft_scaffold_once"
            ) as prepare,
            patch(
                "rou.network_policy_activation.converge_structural_policy",
                return_value=confirmed_transaction(),
            ) as structural,
        ):
            result = activate_network_policy(
                gate, scaffold, object(), object(), object(), object()
            )

        self.assertEqual(result.status, NetworkPolicyActivationStatus.READY)
        self.assertTrue(result.scaffold.scaffold_confirmed)
        self.assertTrue(result.scaffold.unclassified_objects)
        prepare.assert_not_called()
        structural.assert_called_once()

    def test_partial_scaffold_without_other_objects_is_repaired(self):
        gate = FakeGate()
        rows = scaffold_rows()[:-1]
        scaffold = FakeScaffold(observation(rows))

        result, structural = self.invoke(
            gate,
            scaffold,
            confirmed_transaction(),
        )

        self.assertEqual(result.status, NetworkPolicyActivationStatus.READY)
        self.assertEqual(
            scaffold.actions,
            [("repair", ("payload_postrouting",))],
        )
        structural.assert_called_once()

    def test_partial_scaffold_with_other_objects_is_not_repaired(self):
        gate = FakeGate()
        rows = scaffold_rows()[:-1]
        rows.append({
            "rule": {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_forward",
                "handle": 10,
                "comment": "foreign",
                "expr": [],
            }
        })
        scaffold = FakeScaffold(observation(rows))

        with patch(
            "rou.network_policy_activation.prepare_payload_nft_scaffold_once"
        ) as prepare, patch(
            "rou.network_policy_activation.converge_structural_policy"
        ) as structural:
            result = activate_network_policy(
                gate, scaffold, object(), object(), object(), object()
            )

        self.assertEqual(
            result.status,
            NetworkPolicyActivationStatus.SCAFFOLD_CONFLICT,
        )
        self.assertFalse(result.ready)
        self.assertIn("repair is not proven", result.diagnostic)
        prepare.assert_not_called()
        structural.assert_not_called()
        self.assertTrue(result.failure_containment.confirmed)
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)

    def test_reserved_table_owner_conflict_never_reaches_structural_transaction(self):
        gate = FakeGate()
        scaffold = FakeScaffold(observation([
            {"table": {
                "family": "ip",
                "name": "vpn_gate",
                "comment": "somebody-else",
            }}
        ]))

        with patch(
            "rou.network_policy_activation.converge_structural_policy"
        ) as structural:
            result = activate_network_policy(
                gate, scaffold, object(), object(), object(), object()
            )

        self.assertEqual(
            result.status,
            NetworkPolicyActivationStatus.SCAFFOLD_CONFLICT,
        )
        structural.assert_not_called()
        self.assertTrue(result.failure_containment.confirmed)
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)

    def test_scaffold_observation_failure_is_contained(self):
        gate = FakeGate()
        scaffold = FakeScaffold(observation([]))
        scaffold.observe_error = RuntimeError("synthetic observation failure")

        result, structural = self.invoke(
            gate,
            scaffold,
            confirmed_transaction(),
        )

        self.assertEqual(
            result.status,
            NetworkPolicyActivationStatus.SCAFFOLD_OBSERVATION_FAILED,
        )
        structural.assert_not_called()
        self.assertTrue(result.failure_containment.confirmed)
        self.assertIn("synthetic observation failure", result.diagnostic)


    def test_stack_affinity_converges_before_structural_transaction(self):
        gate = FakeGate()
        scaffold = FakeScaffold(observation(scaffold_rows()))
        events = []
        affinity = Mock()
        affinity.confirmed = True
        affinity.diagnostic = None

        def do_affinity(*args):
            events.append("affinity")
            return affinity

        def do_structural(*args):
            events.append("structural")
            gate.state = ForwardingGateState.ENABLED
            return confirmed_transaction()

        with (
            patch(
                "rou.network_policy_activation.converge_stack_return_affinity_once",
                side_effect=do_affinity,
            ) as affinity_mock,
            patch(
                "rou.network_policy_activation.converge_structural_policy",
                side_effect=do_structural,
            ) as structural,
        ):
            result = activate_network_policy(
                gate,
                scaffold,
                object(),
                object(),
                object(),
                object(),
                object(),
                object(),
            )

        self.assertEqual(result.status, NetworkPolicyActivationStatus.READY)
        self.assertEqual(events, ["affinity", "structural"])
        affinity_mock.assert_called_once()
        structural.assert_called_once()
        self.assertIs(result.stack_return_affinity, affinity)

    def test_stack_affinity_failure_blocks_structural_and_remains_contained(self):
        gate = FakeGate()
        scaffold = FakeScaffold(observation(scaffold_rows()))
        affinity = Mock()
        affinity.confirmed = False
        affinity.diagnostic = "synthetic affinity conflict"

        with (
            patch(
                "rou.network_policy_activation.converge_stack_return_affinity_once",
                return_value=affinity,
            ),
            patch(
                "rou.network_policy_activation.converge_structural_policy",
            ) as structural,
        ):
            result = activate_network_policy(
                gate,
                scaffold,
                object(),
                object(),
                object(),
                object(),
                object(),
                object(),
            )

        self.assertEqual(
            result.status,
            NetworkPolicyActivationStatus.STACK_RETURN_AFFINITY_FAILED,
        )
        self.assertFalse(result.ready)
        structural.assert_not_called()
        self.assertTrue(result.failure_containment.confirmed)
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)
        self.assertIn("synthetic affinity conflict", result.diagnostic)


    def test_structural_failure_is_not_retried_and_is_contained(self):
        gate = FakeGate()
        scaffold = FakeScaffold(observation(scaffold_rows()))
        transaction = failed_transaction()

        result, structural = self.invoke(gate, scaffold, transaction)

        self.assertEqual(
            result.status,
            NetworkPolicyActivationStatus.STRUCTURAL_FAILED,
        )
        self.assertFalse(result.ready)
        structural.assert_called_once()
        self.assertIs(result.structural, transaction)
        self.assertTrue(result.failure_containment.confirmed)
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)

    def test_initial_containment_failure_stops_before_scaffold_observation(self):
        gate = FakeGate()
        gate.fail_disable = True
        scaffold = FakeScaffold(observation([]))

        result, structural = self.invoke(
            gate,
            scaffold,
            confirmed_transaction(),
        )

        self.assertEqual(
            result.status,
            NetworkPolicyActivationStatus.INITIAL_CONTAINMENT_FAILED,
        )
        self.assertFalse(result.ready)
        self.assertEqual(scaffold.actions, [])
        structural.assert_not_called()
        self.assertIsNone(result.failure_containment)

    def test_failure_recontainment_failure_is_distinct(self):
        gate = FakeGate()
        scaffold = FakeScaffold(observation(scaffold_rows()))
        transaction = failed_transaction()

        def structural_failure(*args):
            gate.state = ForwardingGateState.ENABLED
            gate.fail_disable = True
            return transaction

        with patch(
            "rou.network_policy_activation.converge_structural_policy",
            side_effect=structural_failure,
        ) as structural:
            result = activate_network_policy(
                gate, scaffold, object(), object(), object(), object()
            )

        self.assertEqual(
            result.status,
            NetworkPolicyActivationStatus.FAILURE_CONTAINMENT_FAILED,
        )
        self.assertEqual(
            result.failure_status,
            NetworkPolicyActivationStatus.STRUCTURAL_FAILED,
        )
        self.assertFalse(result.ready)
        structural.assert_called_once()
        self.assertFalse(result.failure_containment.confirmed)
        self.assertIn("failure containment is not confirmed", result.diagnostic)


if __name__ == "__main__":
    unittest.main()
