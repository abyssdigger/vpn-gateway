import json
import unittest
from ipaddress import IPv4Network

from rou.host_boundary_policy import HostReturnClassifierRule
from rou.linux_host_boundary_policy import (
    HOST_RETURN_CLASSIFY_CHAIN_COMMENT,
    HOST_RETURN_INGRESS_RULE_COMMENT,
    HOST_RETURN_OUTPUT_CHAIN_COMMENT,
    HOST_RETURN_OUTPUT_RESTORE_COMMENT,
    HOST_RETURN_PREROUTE_RESTORE_COMMENT,
    HOST_RETURN_PREROUTING_CHAIN_COMMENT,
    HOST_RETURN_TABLE,
    HOST_RETURN_TABLE_COMMENT,
    HostReturnNftSpec,
)
from rou.linux_host_return_nft import parse_host_return_nft_observation


def spec():
    return HostReturnNftSpec(
        interface="vnga-host0",
        mark=83,
        classifier=(
            HostReturnClassifierRule(
                remote_prefix=IPv4Network("10.20.0.0/16"),
                profile_id="route",
                stateful_return=False,
            ),
            HostReturnClassifierRule(
                remote_prefix=IPv4Network("10.0.0.0/8"),
                profile_id="broad",
                stateful_return=True,
            ),
        ),
    )


def nft_json():
    s = spec()
    rows = [
        {"table": {"family":"inet","name":HOST_RETURN_TABLE,"comment":HOST_RETURN_TABLE_COMMENT}},
        {"chain": {"family":"inet","table":HOST_RETURN_TABLE,"name":"classify_remote","comment":HOST_RETURN_CLASSIFY_CHAIN_COMMENT}},
        {"chain": {"family":"inet","table":HOST_RETURN_TABLE,"name":"prerouting","type":"filter","hook":"prerouting","prio":-150,"policy":"accept","comment":HOST_RETURN_PREROUTING_CHAIN_COMMENT}},
        {"chain": {"family":"inet","table":HOST_RETURN_TABLE,"name":"output","type":"route","hook":"output","prio":-150,"policy":"accept","comment":HOST_RETURN_OUTPUT_CHAIN_COMMENT}},
        {"rule": {"family":"inet","table":HOST_RETURN_TABLE,"chain":"classify_remote","comment":"vpn-gate:ng3:host-return-classifier-v1:0:route:10.20.0.0/16","expr":[{"match":{"left":{"payload":{"protocol":"ip","field":"saddr"}},"op":"==","right":{"prefix":{"addr":"10.20.0.0","len":16}}}},{"return":None}]}},
        {"rule": {"family":"inet","table":HOST_RETURN_TABLE,"chain":"classify_remote","comment":"vpn-gate:ng3:host-return-classifier-v1:1:stateful:10.0.0.0/8","expr":[{"match":{"left":{"payload":{"protocol":"ip","field":"saddr"}},"op":"==","right":{"prefix":{"addr":"10.0.0.0","len":8}}}},{"match":{"left":{"ct":{"key":"state"}},"op":"in","right":"new"}},{"mangle":{"key":{"ct":{"key":"mark"}},"value":83}},{"return":None}]}},
        {"rule": {"family":"inet","table":HOST_RETURN_TABLE,"chain":"prerouting","comment":HOST_RETURN_INGRESS_RULE_COMMENT,"expr":[{"match":{"left":{"meta":{"key":"iifname"}},"op":"==","right":"vnga-host0"}},{"jump":{"target":"classify_remote"}}]}},
        {"rule": {"family":"inet","table":HOST_RETURN_TABLE,"chain":"prerouting","comment":HOST_RETURN_PREROUTE_RESTORE_COMMENT,"expr":[{"match":{"left":{"meta":{"key":"iifname"}},"op":"!=","right":"vnga-host0"}},{"match":{"left":{"ct":{"key":"mark"}},"op":"==","right":83}},{"mangle":{"key":{"meta":{"key":"mark"}},"value":{"ct":{"key":"mark"}}}}]}},
        {"rule": {"family":"inet","table":HOST_RETURN_TABLE,"chain":"output","comment":HOST_RETURN_OUTPUT_RESTORE_COMMENT,"expr":[{"match":{"left":{"ct":{"key":"mark"}},"op":"==","right":83}},{"mangle":{"key":{"meta":{"key":"mark"}},"value":{"ct":{"key":"mark"}}}}]}},
    ]
    return json.dumps({"nftables":rows})


class HostReturnNftObservationTests(unittest.TestCase):
    def test_exact_semantic_owner_is_confirmed(self):
        observed = parse_host_return_nft_observation(nft_json(), spec())
        self.assertTrue(observed.table_present)
        self.assertTrue(observed.exact)
        self.assertEqual(observed.conflicts, ())

    def test_foreign_table_comment_is_conflict(self):
        raw = nft_json().replace(HOST_RETURN_TABLE_COMMENT, "foreign", 1)
        observed = parse_host_return_nft_observation(raw, spec())
        self.assertFalse(observed.exact)
        self.assertIn("owner comment mismatch", "; ".join(observed.conflicts))

    def test_rule_expression_tamper_is_detected(self):
        root = json.loads(nft_json())
        for row in root["nftables"]:
            rule = row.get("rule")
            if rule and rule.get("comment") == HOST_RETURN_INGRESS_RULE_COMMENT:
                rule["expr"][0]["match"]["right"] = "eth999"
        observed = parse_host_return_nft_observation(json.dumps(root), spec())
        self.assertFalse(observed.exact)
        self.assertIn("managed interface", "; ".join(observed.conflicts))

    def test_stale_but_owned_policy_is_replaceable_not_conflict(self):
        root = json.loads(nft_json())
        for row in root["nftables"]:
            rule = row.get("rule")
            if rule and rule.get("comment", "").startswith(
                "vpn-gate:ng3:host-return-classifier-v1:0:"
            ):
                rule["comment"] = (
                    "vpn-gate:ng3:host-return-classifier-v1:0:"
                    "route:10.30.0.0/16"
                )
                break
        observed = parse_host_return_nft_observation(json.dumps(root), spec())
        self.assertTrue(observed.table_present)
        self.assertFalse(observed.exact)
        self.assertEqual(observed.conflicts, ())

    def test_owned_table_can_be_observed_for_cleanup_without_desired_policy(self):
        observed = parse_host_return_nft_observation(nft_json(), None)
        self.assertTrue(observed.table_present)
        self.assertFalse(observed.exact)
        self.assertEqual(observed.conflicts, ())

    def test_absence_matches_none_only(self):
        raw = json.dumps({"nftables":[]})
        self.assertTrue(parse_host_return_nft_observation(raw, None).exact)
        self.assertFalse(parse_host_return_nft_observation(raw, spec()).exact)


if __name__ == "__main__":
    unittest.main()
