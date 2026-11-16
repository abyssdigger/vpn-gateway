from __future__ import annotations

import json
from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.nft_namespace_inventory import parse_nft_namespace_ruleset
from rou.payload_forward_compare import (
    PayloadForwardComparisonError,
    compare_payload_forward,
)
from rou.payload_forward_desired import (
    PayloadForwardDesiredError,
    PayloadForwardDesiredState,
    PayloadForwardRuleSpec,
)
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)


HOST = InterfaceIdentity("host0", 5)
VPN = InterfaceIdentity("vpn0", 9)
VPN_NEW = InterfaceIdentity("vpn0", 11)

NEW_SPEC = PayloadForwardRuleSpec(
    kind=PayloadForwardRuleKind.NEW,
    ingress=HOST,
    egress=VPN,
    remote_field=PayloadForwardRemoteField.DESTINATION,
    remote_prefix=IPv4Network("10.50.0.0/24"),
)
RETURN_SPEC = PayloadForwardRuleSpec(
    kind=PayloadForwardRuleKind.RETURN,
    ingress=VPN,
    egress=HOST,
    remote_field=PayloadForwardRemoteField.SOURCE,
    remote_prefix=IPv4Network("10.50.0.0/24"),
)


def ct(value):
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


def prefix(network: IPv4Network):
    if network.prefixlen == 32:
        return str(network.network_address)
    return {
        "prefix": {
            "addr": str(network.network_address),
            "len": network.prefixlen,
        }
    }


def rule(spec=NEW_SPEC, *, handle=30, ingress=None, egress=None,
         comment=None, remote_prefix=None):
    if spec.kind is PayloadForwardRuleKind.NEW:
        state = "new"
        owner = "vpn-gate:ng3:payload-forward-new-v1"
    else:
        state = ["established", "related"]
        owner = "vpn-gate:ng3:payload-forward-return-v1"
    iif = ingress if ingress is not None else spec.ingress.ifname
    oif = egress if egress is not None else spec.egress.ifname
    network = remote_prefix or spec.remote_prefix
    return {
        "rule": {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "payload_forward",
            "handle": handle,
            "comment": owner if comment is None else comment,
            "expr": [
                ct(state),
                iface("iif", iif),
                iface("oif", oif),
                remote(spec.remote_field.value, prefix(network)),
                {"accept": None},
            ],
        }
    }


def observation(*rules):
    return parse_nft_namespace_ruleset(
        json.dumps(
            {
                "nftables": [
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
            }
        )
    )


class PayloadForwardCompareTests(unittest.TestCase):
    def compare(self, *rules, desired=(NEW_SPEC,), interfaces=(HOST, VPN)):
        return compare_payload_forward(
            observation(*rules),
            interfaces,
            PayloadForwardDesiredState(tuple(desired)),
        )

    def test_exact_rule_confirms_desired(self):
        result = self.compare(rule())
        self.assertEqual(result.confirmed, (NEW_SPEC,))
        self.assertEqual(result.missing, ())
        self.assertEqual(result.stale, ())
        self.assertEqual(result.conflicts, ())
        self.assertTrue(result.desired_confirmed)

    def test_exact_new_and_return_pair_confirms(self):
        desired = PayloadForwardDesiredState((RETURN_SPEC, NEW_SPEC))
        result = compare_payload_forward(
            observation(rule(NEW_SPEC), rule(RETURN_SPEC, handle=31)),
            (HOST, VPN),
            desired,
        )
        self.assertEqual(result.confirmed, desired.rules)
        self.assertTrue(result.desired_confirmed)

    def test_absent_rule_is_missing(self):
        result = self.compare()
        self.assertEqual(result.missing, (NEW_SPEC,))
        self.assertFalse(result.desired_confirmed)

    def test_unexpected_current_identity_rule_is_stale(self):
        other = IPv4Network("10.51.0.0/24")
        result = self.compare(rule(remote_prefix=other))
        self.assertEqual(result.missing, (NEW_SPEC,))
        self.assertEqual(len(result.stale), 1)
        self.assertEqual(result.stale[0].remote_prefix, other)

    def test_stale_numeric_generation_is_stale_and_desired_missing(self):
        successor = PayloadForwardRuleSpec(
            kind=PayloadForwardRuleKind.NEW,
            ingress=HOST,
            egress=VPN_NEW,
            remote_field=PayloadForwardRemoteField.DESTINATION,
            remote_prefix=NEW_SPEC.remote_prefix,
        )
        result = self.compare(
            rule(egress="9"),
            desired=(successor,),
            interfaces=(HOST, VPN_NEW),
        )
        self.assertEqual(result.missing, (successor,))
        self.assertEqual(len(result.stale), 1)
        self.assertEqual(result.stale[0].egress, 9)

    def test_observer_conflict_is_preserved(self):
        result = self.compare(rule(comment="foreign"))
        self.assertTrue(result.conflicts)
        self.assertEqual(result.missing, (NEW_SPEC,))
        self.assertFalse(result.desired_confirmed)

    def test_duplicate_observed_physical_rule_never_confirms_exact_state(self):
        result = self.compare(rule(handle=30), rule(handle=31))
        self.assertEqual(result.confirmed, (NEW_SPEC,))
        self.assertTrue(result.conflicts)
        self.assertFalse(result.desired_confirmed)

    def test_duplicate_desired_physical_rule_is_rejected(self):
        with self.assertRaisesRegex(
            PayloadForwardDesiredError,
            "duplicate desired",
        ):
            PayloadForwardDesiredState((NEW_SPEC, NEW_SPEC))

    def test_desired_rules_are_canonicalized_independent_of_input_order(self):
        state = PayloadForwardDesiredState((RETURN_SPEC, NEW_SPEC))
        reverse = PayloadForwardDesiredState((NEW_SPEC, RETURN_SPEC))
        self.assertEqual(state.rules, reverse.rules)

    def test_non_current_desired_endpoint_is_invalid_input(self):
        successor = PayloadForwardRuleSpec(
            kind=NEW_SPEC.kind,
            ingress=HOST,
            egress=VPN_NEW,
            remote_field=NEW_SPEC.remote_field,
            remote_prefix=NEW_SPEC.remote_prefix,
        )
        with self.assertRaisesRegex(
            PayloadForwardComparisonError,
            "not current",
        ):
            self.compare(
                desired=(successor,),
                interfaces=(HOST, VPN),
            )

    def test_wrong_desired_container_type_is_rejected(self):
        with self.assertRaisesRegex(
            PayloadForwardComparisonError,
            "PayloadForwardDesiredState",
        ):
            compare_payload_forward(
                observation(),
                (HOST, VPN),
                object(),
            )

    def test_zero_prefix_compares_exactly(self):
        zero = PayloadForwardRuleSpec(
            kind=NEW_SPEC.kind,
            ingress=HOST,
            egress=VPN,
            remote_field=NEW_SPEC.remote_field,
            remote_prefix=IPv4Network("0.0.0.0/0"),
        )
        result = self.compare(
            rule(zero),
            desired=(zero,),
        )
        self.assertTrue(result.desired_confirmed)

    def test_host_prefix_compares_exactly(self):
        host = PayloadForwardRuleSpec(
            kind=NEW_SPEC.kind,
            ingress=HOST,
            egress=VPN,
            remote_field=NEW_SPEC.remote_field,
            remote_prefix=IPv4Network("10.50.0.7/32"),
        )
        result = self.compare(
            rule(host),
            desired=(host,),
        )
        self.assertTrue(result.desired_confirmed)

    def test_unexpected_return_rule_is_stale_not_desired(self):
        result = self.compare(
            rule(NEW_SPEC),
            rule(RETURN_SPEC, handle=31),
            desired=(NEW_SPEC,),
        )
        self.assertEqual(result.confirmed, (NEW_SPEC,))
        self.assertEqual(len(result.stale), 1)
        self.assertEqual(
            result.stale[0].kind,
            PayloadForwardRuleKind.RETURN,
        )

    def test_empty_desired_and_empty_chain_is_exact(self):
        result = self.compare(desired=())
        self.assertTrue(result.desired_confirmed)

    def test_empty_desired_with_recognized_rule_is_not_exact(self):
        result = self.compare(rule(), desired=())
        self.assertEqual(len(result.stale), 1)
        self.assertFalse(result.desired_confirmed)

    def test_rule_spec_rejects_non_network_prefix(self):
        with self.assertRaisesRegex(
            PayloadForwardDesiredError,
            "remote_prefix",
        ):
            PayloadForwardRuleSpec(
                kind=NEW_SPEC.kind,
                ingress=HOST,
                egress=VPN,
                remote_field=NEW_SPEC.remote_field,
                remote_prefix="10.50.0.0/24",
            )


if __name__ == "__main__":
    unittest.main()
