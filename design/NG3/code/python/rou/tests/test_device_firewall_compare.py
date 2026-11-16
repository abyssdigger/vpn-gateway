from __future__ import annotations

import json
import unittest

from rou.device_firewall_compare import compare_device_firewall
from rou.device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallDesiredError,
    DeviceFirewallDesiredState,
    DeviceFirewallRuleSpec,
)
from rou.device_firewall_structure import (
    DEVICE_FIREWALL_CHILD_COMMENT,
    DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
    DEVICE_FIREWALL_JUMP_COMMENT,
    DEVICE_FIREWALL_RULE_COMMENT,
    DeviceFirewallRuleAction,
)
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
CHAIN = "device_fw_test"


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


def scaffold_objects() -> tuple[NftNamespaceObject, ...]:
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


def match(field: str, value: str) -> dict:
    return {
        "match": {
            "op": "==",
            "left": {"payload": {"protocol": "ip", "field": field}},
            "right": value,
        }
    }


def iface(key: str, value: str) -> dict:
    return {
        "match": {
            "op": "==",
            "left": {"meta": {"key": key}},
            "right": value,
        }
    }


def observed(*, second_first: bool = False, extra_chain: bool = False):
    child = obj(
        "chain",
        {
            "family": "ip",
            "table": "vpn_gate",
            "name": CHAIN,
            "handle": 50,
            "comment": DEVICE_FIREWALL_CHILD_COMMENT,
        },
        10,
    )
    jump = obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "payload_forward",
            "handle": 60,
            "comment": DEVICE_FIREWALL_JUMP_COMMENT,
            "expr": [
                iface("iif", "host0"),
                iface("oif", "vpn0"),
                {"jump": {"target": CHAIN}},
            ],
        },
        11,
    )
    first = obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": CHAIN,
            "handle": 70,
            "comment": DEVICE_FIREWALL_RULE_COMMENT,
            "expr": [match("daddr", "10.0.0.0/8"), {"return": None}],
        },
        20 if not second_first else 21,
    )
    second = obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": CHAIN,
            "handle": 71,
            "comment": DEVICE_FIREWALL_RULE_COMMENT,
            "expr": [match("daddr", "10.1.0.0/16"), {"drop": None}],
        },
        21 if not second_first else 20,
    )
    fallthrough = obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": CHAIN,
            "handle": 72,
            "comment": DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
            "expr": [{"drop": None}],
        },
        22,
    )
    extras = []
    if extra_chain:
        extras.append(
            obj(
                "chain",
                {
                    "family": "ip",
                    "table": "vpn_gate",
                    "name": "device_fw_stale",
                    "handle": 80,
                    "comment": DEVICE_FIREWALL_CHILD_COMMENT,
                },
                30,
            )
        )
    return NftNamespaceObservation(
        status=NftNamespaceStatus.OWNED,
        objects=scaffold_objects() + (child, jump, first, second, fallthrough, *extras),
        observed_comment=NG3_NFT_OWNER_COMMENT,
    )


def rule_spec(
    *,
    field: str,
    value: str,
    action: DeviceFirewallRuleAction,
    action_json: str,
) -> DeviceFirewallRuleSpec:
    return DeviceFirewallRuleSpec(
        match_expr_json=(
            json.dumps(match(field, value), sort_keys=True, separators=(",", ":")),
        ),
        action=action,
        action_json=action_json,
    )


def desired() -> DeviceFirewallDesiredState:
    return DeviceFirewallDesiredState(
        chains=(
            DeviceFirewallChainSpec(
                ingress=HOST,
                egress=VPN,
                child_chain_name=CHAIN,
                rules=(
                    rule_spec(
                        field="daddr",
                        value="10.0.0.0/8",
                        action=DeviceFirewallRuleAction.RETURN,
                        action_json='{"return":null}',
                    ),
                    rule_spec(
                        field="daddr",
                        value="10.1.0.0/16",
                        action=DeviceFirewallRuleAction.DROP,
                        action_json='{"drop":null}',
                    ),
                    DeviceFirewallRuleSpec(
                        match_expr_json=(),
                        action=DeviceFirewallRuleAction.DROP,
                        action_json='{"drop":null}',
                        terminal_fallthrough=True,
                    ),
                ),
            ),
        )
    )


class DeviceFirewallCompareTests(unittest.TestCase):
    def test_exact_ordered_structure_confirms(self):
        result = compare_device_firewall(
            observed(),
            (HOST, VPN),
            desired(),
        )
        self.assertTrue(result.desired_confirmed)
        self.assertEqual(result.missing, ())
        self.assertEqual(result.stale_chains, ())
        self.assertEqual(result.stale_jumps, ())

    def test_same_rules_wrong_order_is_not_confirmed(self):
        result = compare_device_firewall(
            observed(second_first=True),
            (HOST, VPN),
            desired(),
        )
        self.assertFalse(result.desired_confirmed)
        self.assertEqual(len(result.missing), 1)
        self.assertEqual(len(result.stale_chains), 1)
        self.assertEqual(len(result.stale_jumps), 1)

    def test_extra_owned_chain_is_stale(self):
        result = compare_device_firewall(
            observed(extra_chain=True),
            (HOST, VPN),
            desired(),
        )
        self.assertFalse(result.desired_confirmed)
        self.assertEqual(
            [chain.name for chain in result.stale_chains],
            ["device_fw_stale"],
        )

    def test_non_current_desired_endpoint_is_rejected(self):
        stale = InterfaceIdentity("vpn-old", 30)
        bad = DeviceFirewallDesiredState(
            chains=(
                DeviceFirewallChainSpec(
                    ingress=HOST,
                    egress=stale,
                    child_chain_name=CHAIN,
                    rules=desired().chains[0].rules,
                ),
            )
        )
        with self.assertRaisesRegex(Exception, "not current"):
            compare_device_firewall(
                observed(),
                (HOST, VPN),
                bad,
            )

    def test_terminal_fallthrough_must_be_last_in_desired(self):
        terminal = DeviceFirewallRuleSpec(
            match_expr_json=(),
            action=DeviceFirewallRuleAction.DROP,
            action_json='{"drop":null}',
            terminal_fallthrough=True,
        )
        ordinary = rule_spec(
            field="daddr",
            value="10.0.0.0/8",
            action=DeviceFirewallRuleAction.RETURN,
            action_json='{"return":null}',
        )
        with self.assertRaisesRegex(
            DeviceFirewallDesiredError,
            "must be the final rule",
        ):
            DeviceFirewallChainSpec(
                ingress=HOST,
                egress=VPN,
                child_chain_name=CHAIN,
                rules=(terminal, ordinary),
            )


if __name__ == "__main__":
    unittest.main()
