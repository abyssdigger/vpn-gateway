from __future__ import annotations

import json
import unittest
from ipaddress import IPv4Address

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import PAYLOAD_NFT_SCAFFOLD
from rou.probe_local_observation import (
    PROBE_LOCAL_RULE_COMMENT,
    compare_probe_local,
)
from rou.probe_policy import ProbeLocalHook, ProbeLocalRuleSpec


PATH = LogicalPathId("device", 0, 0)
EP = InterfaceIdentity("path0", 2)
TARGET = IPv4Address("198.51.100.7")
MARK = 0x20000001
UID = 4242


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


def observation(*extra: NftNamespaceObject) -> NftNamespaceObservation:
    scaffold = tuple(
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
        for order, spec in enumerate(PAYLOAD_NFT_SCAFFOLD, start=1)
    )
    return NftNamespaceObservation(
        status=NftNamespaceStatus.OWNED,
        objects=scaffold + tuple(extra),
        observed_comment=NG3_NFT_OWNER_COMMENT,
    )


def desired(owner_name="corp"):
    owner = ProbePolicyOwner(owner_name, PATH)
    return (
        ProbeLocalRuleSpec(
            owner=owner,
            hook=ProbeLocalHook.OUTPUT,
            endpoint=EP,
            target=TARGET,
            conntrack_mark=MARK,
            process_uid=UID,
        ),
        ProbeLocalRuleSpec(
            owner=owner,
            hook=ProbeLocalHook.INPUT,
            endpoint=EP,
            target=TARGET,
            conntrack_mark=MARK,
        ),
    )


def output_rule(handle=20, iface="path0"):
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "stack_output",
            "handle": handle,
            "comment": PROBE_LOCAL_RULE_COMMENT,
            "expr": [
                {"match": {"left": {"meta": {"key": "skuid"}}, "op": "==", "right": UID}},
                {"match": {"left": {"meta": {"key": "oif"}}, "op": "==", "right": iface}},
                {"match": {"left": {"payload": {"field": "daddr", "protocol": "ip"}}, "op": "==", "right": str(TARGET)}},
                {"match": {"left": {"payload": {"field": "protocol", "protocol": "ip"}}, "op": "==", "right": 1}},
                {"mangle": {"key": {"ct": {"key": "mark"}}, "value": MARK}},
                {"accept": None},
            ],
        },
        handle,
    )


def input_rule(handle=21, iface="path0"):
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "stack_input",
            "handle": handle,
            "comment": PROBE_LOCAL_RULE_COMMENT,
            "expr": [
                {"match": {"left": {"meta": {"key": "iif"}}, "op": "==", "right": iface}},
                {"match": {"left": {"payload": {"field": "saddr", "protocol": "ip"}}, "op": "==", "right": str(TARGET)}},
                {"match": {"left": {"payload": {"field": "protocol", "protocol": "ip"}}, "op": "==", "right": 1}},
                {"match": {"left": {"ct": {"key": "mark"}}, "op": "==", "right": MARK}},
                {"accept": None},
            ],
        },
        handle,
    )


class ProbeLocalObservationTests(unittest.TestCase):
    def test_exp066_exact_pair_is_confirmed(self):
        result = compare_probe_local(
            observation(output_rule(), input_rule()),
            (EP,),
            desired(),
        )
        self.assertTrue(result.desired_confirmed)
        self.assertEqual(len(result.confirmed), 2)

    def test_raw_old_ifindex_is_stale_after_same_name_replacement(self):
        current = InterfaceIdentity("path0", 3)
        specs = tuple(
            ProbeLocalRuleSpec(
                owner=rule.owner,
                hook=rule.hook,
                endpoint=current,
                target=rule.target,
                conntrack_mark=rule.conntrack_mark,
                process_uid=rule.process_uid,
            )
            for rule in desired()
        )
        result = compare_probe_local(
            observation(output_rule(iface="2"), input_rule(iface="2")),
            (current,),
            specs,
        )
        self.assertFalse(result.desired_confirmed)
        self.assertEqual(len(result.stale), 2)
        self.assertEqual(len(result.missing), 2)

    def test_identical_physical_rules_from_two_semantic_owners_coalesce(self):
        specs = desired("corp") + desired("guest")
        result = compare_probe_local(
            observation(output_rule(), input_rule()),
            (EP,),
            specs,
        )
        self.assertTrue(result.desired_confirmed)
        self.assertEqual(len(result.confirmed), 2)

    def test_wrong_output_mark_shape_is_conflict(self):
        bad = output_rule()
        row = json.loads(bad.canonical_json)
        row["rule"]["expr"][4] = {
            "match": {
                "left": {"ct": {"key": "mark"}},
                "op": "==",
                "right": MARK,
            }
        }
        bad = NftNamespaceObject(
            "rule",
            json.dumps(row, sort_keys=True, separators=(",", ":")),
            bad.source_order,
        )
        result = compare_probe_local(
            observation(bad, input_rule()),
            (EP,),
            desired(),
        )
        self.assertFalse(result.desired_confirmed)
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(len(result.missing), 1)

    def test_duplicate_physical_rule_is_conflict(self):
        result = compare_probe_local(
            observation(output_rule(20), output_rule(22), input_rule()),
            (EP,),
            desired(),
        )
        self.assertFalse(result.desired_confirmed)
        self.assertEqual(len(result.conflicts), 1)



    def test_symbolic_icmp_protocol_json_is_equivalent(self):
        raw = exact_ruleset()
        for item in raw["nftables"]:
            rule = item.get("rule")
            if not isinstance(rule, dict):
                continue
            for expr in rule.get("expr", ()):
                match = expr.get("match") if isinstance(expr, dict) else None
                if (
                    isinstance(match, dict)
                    and match.get("left")
                    == {"payload": {"field": "protocol", "protocol": "ip"}}
                    and match.get("right") == 1
                ):
                    match["right"] = "icmp"
        value = compare_probe_local(
            parse_nft_namespace_ruleset(json.dumps(raw)),
            (PATH,),
            DESIRED,
        )
        self.assertTrue(value.desired_confirmed)
        self.assertEqual(value.conflicts, ())

if __name__ == "__main__":
    unittest.main()
