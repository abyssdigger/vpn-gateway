from __future__ import annotations

import json
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.nft_namespace_inventory import parse_nft_namespace_ruleset
from rou.payload_nat_desired import PayloadNatDesiredState, PayloadMasqueradeSpec
from rou.payload_nat_observation import (
    PayloadNatObservationError,
    compare_payload_nat,
)
from rou.binding import LogicalPathId


HOST = InterfaceIdentity("host0", 5)
OLD = InterfaceIdentity("tun0", 9)
NEW = InterfaceIdentity("tun0", 11)
OTHER = InterfaceIdentity("tun1", 12)
SPEC = PayloadMasqueradeSpec(LogicalPathId("device", 0, 0), HOST, OLD)


def match(key, operand):
    return {"match": {"op": "==", "left": {"meta": {"key": key}}, "right": operand}}


def rule(iif="host0", oif="tun0", handle=30, **changes):
    value = {
        "family": "ip", "table": "vpn_gate", "chain": "payload_postrouting",
        "handle": handle, "comment": "vpn-gate:ng3:payload-nat-v1",
        "expr": [match("iif", iif), match("oif", oif), {"masquerade": None}],
    }
    value.update(changes)
    return {"rule": value}


def observation(*rules):
    rows = [
        {"table": {"family": "ip", "name": "vpn_gate",
                   "comment": "vpn-gate:ng3:owner-v1"}},
        {"chain": {"family": "ip", "table": "vpn_gate",
                   "name": "payload_forward", "type": "filter", "hook": "forward",
                   "prio": 0, "policy": "drop",
                   "comment": "vpn-gate:ng3:payload-forward-v1"}},
        {"chain": {"family": "ip", "table": "vpn_gate",
                   "name": "payload_postrouting", "type": "nat", "hook": "postrouting",
                   "prio": 100, "policy": "accept",
                   "comment": "vpn-gate:ng3:payload-postrouting-v1"}},
        *rules,
    ]
    return parse_nft_namespace_ruleset(json.dumps({"nftables": rows}))


class PayloadNatObservationTests(unittest.TestCase):
    def compare(self, *rules, interfaces=(HOST, OLD), desired=(SPEC,)):
        return compare_payload_nat(
            observation(*rules), interfaces, PayloadNatDesiredState(tuple(desired))
        )

    def test_exact_current_names_confirm(self):
        result = self.compare(rule())
        self.assertEqual(result.confirmed, (SPEC,))
        self.assertEqual(result.missing, ())
        self.assertEqual(result.stale, ())
        self.assertEqual(result.conflicts, ())

    def test_live_numeric_index_maps_to_current_identity(self):
        result = self.compare(rule(iif="5", oif="9"))
        self.assertEqual(result.confirmed, (SPEC,))

    def test_missing_rule_is_missing_not_conflict(self):
        result = self.compare()
        self.assertEqual(result.missing, (SPEC,))
        self.assertTrue(result.mutation_safe)

    def test_missing_old_ifindex_cannot_impersonate_same_name_replacement(self):
        successor = PayloadMasqueradeSpec(SPEC.path_id, HOST, NEW)
        result = self.compare(
            rule(oif="9"), interfaces=(HOST, NEW), desired=(successor,)
        )
        self.assertEqual(result.missing, (successor,))
        self.assertEqual(len(result.stale), 1)
        self.assertEqual(result.stale[0].egress, 9)
        self.assertFalse(result.stale[0].egress == NEW)

    def test_recognized_unexpected_current_rule_is_stale(self):
        result = self.compare(rule(oif="tun1"), interfaces=(HOST, OLD, OTHER))
        self.assertEqual(result.missing, (SPEC,))
        self.assertEqual(result.stale[0].egress, OTHER)

    def test_unknown_owner_inside_owned_chain_is_conflict(self):
        result = self.compare(rule(comment="unowned"))
        self.assertEqual(result.missing, (SPEC,))
        self.assertIn("comment", result.conflicts[0].reason)
        self.assertFalse(result.mutation_safe)

    def test_unexpected_action_is_conflict(self):
        result = self.compare(rule(expr=[match("iif", "host0"), match("oif", "tun0"), {"snat": {"addr": "192.0.2.1"}}]))
        self.assertIn("action", result.conflicts[0].reason)

    def test_extra_expression_is_conflict(self):
        expr = [match("iif", "host0"), match("oif", "tun0"), {"counter": None}, {"masquerade": None}]
        result = self.compare(rule(expr=expr))
        self.assertIn("three expressions", result.conflicts[0].reason)

    def test_wrong_match_order_is_conflict(self):
        result = self.compare(rule(expr=[match("oif", "tun0"), match("iif", "host0"), {"masquerade": None}]))
        self.assertIn("iif", result.conflicts[0].reason)

    def test_duplicate_physical_rules_are_conflict(self):
        result = self.compare(rule(handle=30), rule(handle=31))
        self.assertEqual(result.confirmed, (SPEC,))
        self.assertIn("duplicate physical", result.conflicts[0].reason)

    def test_duplicate_handles_are_conflict(self):
        result = self.compare(rule(handle=30), rule(handle=30))
        self.assertIn("duplicate NAT rule handle", result.conflicts[0].reason)

    def test_unresolved_textual_operand_is_conflict(self):
        result = self.compare(rule(oif="vanished"))
        self.assertIn("unresolved", result.conflicts[0].reason)

    def test_numeric_boolean_and_unknown_fields_are_conflicts(self):
        for bad in [rule(oif=9), rule(oif=True), rule(extra="unexpected")]:
            with self.subTest(bad=bad):
                self.assertFalse(self.compare(bad).mutation_safe)

    def test_non_nat_chain_rule_does_not_interfere(self):
        other = rule(chain="payload_forward")
        result = self.compare(other, rule(handle=31))
        self.assertEqual(result.confirmed, (SPEC,))

    def test_absent_scaffold_is_hard_failure(self):
        rows = {"nftables": [
            {"table": {"family": "ip", "name": "vpn_gate", "comment": "vpn-gate:ng3:owner-v1"}}
        ]}
        with self.assertRaisesRegex(PayloadNatObservationError, "scaffold"):
            compare_payload_nat(parse_nft_namespace_ruleset(json.dumps(rows)),
                                (HOST, OLD), PayloadNatDesiredState((SPEC,)))

    def test_ambiguous_inventory_is_hard_failure(self):
        with self.assertRaisesRegex(PayloadNatObservationError, "ambiguous"):
            self.compare(rule(), interfaces=(HOST, OLD, OLD))

    def test_desired_endpoint_must_be_current(self):
        with self.assertRaisesRegex(PayloadNatObservationError, "not current"):
            self.compare(rule(), interfaces=(HOST, NEW))

    def test_duplicate_desired_physical_rule_is_invalid(self):
        second = PayloadMasqueradeSpec(LogicalPathId("other", 0, 0), HOST, OLD)
        with self.assertRaisesRegex(PayloadNatObservationError, "duplicate desired"):
            self.compare(rule(), desired=(SPEC, second))


if __name__ == "__main__":
    unittest.main()
