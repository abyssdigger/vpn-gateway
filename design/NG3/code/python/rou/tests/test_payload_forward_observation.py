from __future__ import annotations

import json
from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.nft_namespace_inventory import parse_nft_namespace_ruleset
from rou.payload_forward_observation import (
    PayloadForwardObservationError,
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
    observe_payload_forward,
)


HOST = InterfaceIdentity("host0", 5)
OLD = InterfaceIdentity("vpn0", 9)
NEW = InterfaceIdentity("vpn0", 11)
OTHER = InterfaceIdentity("vpn1", 12)

NEW_COMMENT = "vpn-gate:ng3:payload-forward-new-v1"
RETURN_COMMENT = "vpn-gate:ng3:payload-forward-return-v1"


def ct_state(value):
    return {
        "match": {
            "op": "in",
            "left": {"ct": {"key": "state"}},
            "right": value,
        }
    }


def iface(key, value):
    return {
        "match": {
            "op": "==",
            "left": {"meta": {"key": key}},
            "right": value,
        }
    }


def remote(field, value):
    return {
        "match": {
            "op": "==",
            "left": {"payload": {"protocol": "ip", "field": field}},
            "right": value,
        }
    }


def prefix(addr="10.0.0.0", length=24):
    return {"prefix": {"addr": addr, "len": length}}


def rule(
    *,
    kind="new",
    iif="host0",
    oif="vpn0",
    field="daddr",
    value=None,
    handle=30,
    comment=None,
    expr=None,
    chain="payload_forward",
    **changes,
):
    if kind == "new":
        state = "new"
        owner = NEW_COMMENT
    else:
        state = ["established", "related"]
        owner = RETURN_COMMENT
    if value is None:
        value = prefix()
    if expr is None:
        expr = [
            ct_state(state),
            iface("iif", iif),
            iface("oif", oif),
            remote(field, value),
            {"accept": None},
        ]
    payload = {
        "family": "ip",
        "table": "vpn_gate",
        "chain": chain,
        "handle": handle,
        "comment": owner if comment is None else comment,
        "expr": expr,
    }
    payload.update(changes)
    return {"rule": payload}


def observation(*rules):
    rows = [
        {
            "table": {
                "family": "ip",
                "name": "vpn_gate",
                "comment": "vpn-gate:ng3:owner-v1",
            }
        },
        {
            "chain": {
                "family": "ip",
                "table": "vpn_gate",
                "name": "stack_input",
                "type": "filter",
                "hook": "input",
                "prio": 0,
                "policy": "drop",
                "comment": "vpn-gate:ng3:stack-input-v1",
            }
        },
        {
            "chain": {
                "family": "ip",
                "table": "vpn_gate",
                "name": "payload_forward",
                "type": "filter",
                "hook": "forward",
                "prio": 0,
                "policy": "drop",
                "comment": "vpn-gate:ng3:payload-forward-v1",
            }
        },
        {
            "chain": {
                "family": "ip",
                "table": "vpn_gate",
                "name": "stack_output",
                "type": "filter",
                "hook": "output",
                "prio": 0,
                "policy": "drop",
                "comment": "vpn-gate:ng3:stack-output-v1",
            }
        },
        {
            "chain": {
                "family": "ip",
                "table": "vpn_gate",
                "name": "payload_postrouting",
                "type": "nat",
                "hook": "postrouting",
                "prio": 100,
                "policy": "accept",
                "comment": "vpn-gate:ng3:payload-postrouting-v1",
            }
        },
        *rules,
    ]
    return parse_nft_namespace_ruleset(json.dumps({"nftables": rows}))


class PayloadForwardObservationTests(unittest.TestCase):
    def observe(self, *rules, interfaces=(HOST, OLD)):
        return observe_payload_forward(
            observation(*rules),
            interfaces,
        )

    def test_new_current_rule_is_recognized(self):
        result = self.observe(rule())
        self.assertTrue(result.conflict_free)
        self.assertEqual(len(result.current_identity_rules), 1)
        found = result.current_identity_rules[0]
        self.assertEqual(found.kind, PayloadForwardRuleKind.NEW)
        self.assertEqual(found.ingress, HOST)
        self.assertEqual(found.egress, OLD)
        self.assertEqual(found.remote_field, PayloadForwardRemoteField.DESTINATION)
        self.assertEqual(found.remote_prefix, IPv4Network("10.0.0.0/24"))
        self.assertEqual(result.stale_identity_rules, ())

    def test_return_current_rule_is_recognized(self):
        result = self.observe(
            rule(
                kind="return",
                iif="vpn0",
                oif="host0",
                field="saddr",
            )
        )
        found = result.current_identity_rules[0]
        self.assertEqual(found.kind, PayloadForwardRuleKind.RETURN)
        self.assertEqual(found.ingress, OLD)
        self.assertEqual(found.egress, HOST)
        self.assertEqual(found.remote_field, PayloadForwardRemoteField.SOURCE)

    def test_32_string_normalizes_to_host_network(self):
        result = self.observe(rule(value="10.0.0.7"))
        self.assertEqual(
            result.current_identity_rules[0].remote_prefix,
            IPv4Network("10.0.0.7/32"),
        )

    def test_zero_prefix_object_is_accepted(self):
        result = self.observe(
            rule(value=prefix("0.0.0.0", 0))
        )
        self.assertEqual(
            result.current_identity_rules[0].remote_prefix,
            IPv4Network("0.0.0.0/0"),
        )

    def test_live_numeric_indices_resolve_to_current_identity(self):
        result = self.observe(rule(iif="5", oif="9"))
        self.assertEqual(result.current_identity_rules[0].ingress, HOST)
        self.assertEqual(result.current_identity_rules[0].egress, OLD)

    def test_stale_numeric_ifindex_cannot_impersonate_same_name_replacement(self):
        result = self.observe(
            rule(oif="9"),
            interfaces=(HOST, NEW),
        )
        self.assertEqual(result.current_identity_rules, ())
        self.assertEqual(len(result.stale_identity_rules), 1)
        self.assertEqual(result.stale_identity_rules[0].egress, 9)
        self.assertNotEqual(result.stale_identity_rules[0].egress, NEW)

    def test_unknown_owner_comment_is_conflict(self):
        result = self.observe(rule(comment="foreign"))
        self.assertFalse(result.conflict_free)
        self.assertIn("owner comment", result.conflicts[0].reason)

    def test_counter_instrumentation_is_not_production_owner_shape(self):
        expr = [
            ct_state("new"),
            iface("iif", "host0"),
            iface("oif", "vpn0"),
            remote("daddr", prefix()),
            {"counter": {"packets": 0, "bytes": 0}},
            {"accept": None},
        ]
        result = self.observe(rule(expr=expr))
        self.assertFalse(result.conflict_free)
        self.assertIn("five expressions", result.conflicts[0].reason)

    def test_wrong_state_set_is_conflict(self):
        expr = [
            ct_state(["new", "established"]),
            iface("iif", "host0"),
            iface("oif", "vpn0"),
            remote("daddr", prefix()),
            {"accept": None},
        ]
        result = self.observe(rule(expr=expr))
        self.assertIn("state set", result.conflicts[0].reason)

    def test_return_comment_requires_return_state_set(self):
        expr = [
            ct_state("new"),
            iface("iif", "vpn0"),
            iface("oif", "host0"),
            remote("saddr", prefix()),
            {"accept": None},
        ]
        result = self.observe(rule(kind="return", expr=expr))
        self.assertIn("state set", result.conflicts[0].reason)

    def test_action_must_be_plain_accept(self):
        expr = [
            ct_state("new"),
            iface("iif", "host0"),
            iface("oif", "vpn0"),
            remote("daddr", prefix()),
            {"drop": None},
        ]
        result = self.observe(rule(expr=expr))
        self.assertIn("plain accept", result.conflicts[0].reason)

    def test_remote_match_must_be_ipv4_source_or_destination(self):
        expr = [
            ct_state("new"),
            iface("iif", "host0"),
            iface("oif", "vpn0"),
            {
                "match": {
                    "op": "==",
                    "left": {"payload": {"protocol": "tcp", "field": "dport"}},
                    "right": 443,
                }
            },
            {"accept": None},
        ]
        result = self.observe(rule(expr=expr))
        self.assertIn("saddr or daddr", result.conflicts[0].reason)

    def test_prefix_object_32_is_not_evidence_backed(self):
        result = self.observe(
            rule(value=prefix("10.0.0.7", 32))
        )
        self.assertIn("[0, 31]", result.conflicts[0].reason)

    def test_string_cidr_is_not_evidence_backed(self):
        result = self.observe(rule(value="10.0.0.0/24"))
        self.assertIn("plain IPv4", result.conflicts[0].reason)

    def test_noncanonical_prefix_object_is_conflict(self):
        result = self.observe(
            rule(value=prefix("10.0.0.7", 24))
        )
        self.assertIn("non-canonical", result.conflicts[0].reason)

    def test_unresolved_textual_interface_is_conflict(self):
        result = self.observe(rule(oif="vanished"))
        self.assertIn("unresolved", result.conflicts[0].reason)

    def test_duplicate_handles_are_conflict(self):
        result = self.observe(
            rule(handle=30),
            rule(handle=30, value=prefix("10.1.0.0", 24)),
        )
        self.assertIn("duplicate forward rule handle", result.conflicts[0].reason)

    def test_duplicate_physical_rules_are_conflict(self):
        result = self.observe(rule(handle=30), rule(handle=31))
        self.assertEqual(len(result.current_identity_rules), 1)
        self.assertIn("duplicate physical", result.conflicts[0].reason)

    def test_same_interfaces_and_prefix_but_different_kind_are_distinct(self):
        result = self.observe(
            rule(handle=30),
            rule(
                kind="return",
                iif="host0",
                oif="vpn0",
                field="daddr",
                handle=31,
            ),
        )
        self.assertTrue(result.conflict_free)
        self.assertEqual(len(result.current_identity_rules), 2)

    def test_non_forward_chain_rule_is_ignored(self):
        result = self.observe(
            rule(chain="payload_postrouting", comment="anything"),
            rule(handle=31),
        )
        self.assertTrue(result.conflict_free)
        self.assertEqual(len(result.current_identity_rules), 1)

    def test_device_firewall_jump_is_delegated_to_separate_observer(self):
        jump = rule(
            handle=40,
            comment="vpn-gate:ng3:device-fw-jump-v1",
            expr=[
                iface("iif", "host0"),
                iface("oif", "vpn0"),
                {"jump": {"target": "device_fw_test"}},
            ],
        )
        result = self.observe(jump, rule(handle=31))
        self.assertTrue(result.conflict_free)
        self.assertEqual(len(result.current_identity_rules), 1)
        self.assertEqual(result.current_identity_rules[0].handle, 31)

    def test_missing_scaffold_is_hard_failure(self):
        rows = {
            "nftables": [
                {
                    "table": {
                        "family": "ip",
                        "name": "vpn_gate",
                        "comment": "vpn-gate:ng3:owner-v1",
                    }
                }
            ]
        }
        with self.assertRaisesRegex(
            PayloadForwardObservationError,
            "scaffold",
        ):
            observe_payload_forward(
                parse_nft_namespace_ruleset(json.dumps(rows)),
                (HOST, OLD),
            )

    def test_ambiguous_inventory_is_hard_failure(self):
        with self.assertRaisesRegex(
            PayloadForwardObservationError,
            "ambiguous",
        ):
            self.observe(rule(), interfaces=(HOST, OLD, OLD))

    def test_missing_rule_chain_is_conflict(self):
        malformed = rule()
        del malformed["rule"]["chain"]
        result = self.observe(malformed)
        self.assertIn("chain", result.conflicts[0].reason)

    def test_unknown_rule_field_is_conflict(self):
        result = self.observe(rule(extra="unexpected"))
        self.assertIn("unsupported forward rule fields", result.conflicts[0].reason)

    def test_boolean_handle_is_invalid(self):
        result = self.observe(rule(handle=True))
        self.assertIn("handle", result.conflicts[0].reason)


if __name__ == "__main__":
    unittest.main()
