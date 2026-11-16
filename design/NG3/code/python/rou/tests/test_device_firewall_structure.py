from __future__ import annotations

import json
import unittest

from rou.device_firewall_structure import (
    DEVICE_FIREWALL_CHILD_COMMENT,
    DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
    DEVICE_FIREWALL_JUMP_COMMENT,
    DEVICE_FIREWALL_RULE_COMMENT,
    DeviceFirewallRuleAction,
    observe_device_firewall_structure,
)
from rou.interface_identity import InterfaceIdentity
from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import PAYLOAD_NFT_SCAFFOLD


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
    result = []
    for order, spec in enumerate(PAYLOAD_NFT_SCAFFOLD, start=1):
        result.append(
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
    return tuple(result)


def child_chain(name: str = "device_fw_test", order: int = 10):
    return obj(
        "chain",
        {
            "family": "ip",
            "table": "vpn_gate",
            "name": name,
            "handle": 50,
            "comment": DEVICE_FIREWALL_CHILD_COMMENT,
        },
        order,
    )


def interface_match(key: str, value: str) -> dict:
    return {
        "match": {
            "op": "==",
            "left": {"meta": {"key": key}},
            "right": value,
        }
    }


def jump(
    *,
    target: str = "device_fw_test",
    ingress: str = "host0",
    egress: str = "vpn0",
    order: int = 15,
):
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "payload_forward",
            "handle": 60,
            "comment": DEVICE_FIREWALL_JUMP_COMMENT,
            "expr": [
                interface_match("iif", ingress),
                interface_match("oif", egress),
                {"jump": {"target": target}},
            ],
        },
        order,
    )


def explicit_rule(
    *,
    action: dict,
    order: int,
    handle: int,
    comment: str = DEVICE_FIREWALL_RULE_COMMENT,
):
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "device_fw_test",
            "handle": handle,
            "comment": comment,
            "expr": [
                {
                    "match": {
                        "op": "==",
                        "left": {
                            "payload": {
                                "protocol": "ip",
                                "field": "daddr",
                            }
                        },
                        "right": "10.41.2.2",
                    }
                },
                action,
            ],
        },
        order,
    )


def fallthrough(order: int = 30):
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": "device_fw_test",
            "handle": 99,
            "comment": DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
            "expr": [{"drop": None}],
        },
        order,
    )


def owned(*extra: NftNamespaceObject) -> NftNamespaceObservation:
    return NftNamespaceObservation(
        status=NftNamespaceStatus.OWNED,
        objects=scaffold_objects() + tuple(extra),
        observed_comment=NG3_NFT_OWNER_COMMENT,
    )


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)


class DeviceFirewallStructureTests(unittest.TestCase):
    def test_child_rule_order_uses_physical_source_order(self):
        later_return = explicit_rule(
            action={"return": None},
            order=21,
            handle=71,
        )
        earlier_reject = explicit_rule(
            action={"reject": {"type": "icmp", "expr": "port-unreachable"}},
            order=20,
            handle=70,
        )
        value = observe_device_firewall_structure(
            owned(
                child_chain(),
                jump(),
                later_return,
                fallthrough(order=22),
                earlier_reject,
            ),
            (HOST, VPN),
        )
        self.assertTrue(value.conflict_free)
        self.assertEqual(len(value.chains), 1)
        self.assertEqual(
            [rule.action for rule in value.chains[0].rules],
            [
                DeviceFirewallRuleAction.REJECT,
                DeviceFirewallRuleAction.RETURN,
                DeviceFirewallRuleAction.DROP,
            ],
        )
        self.assertTrue(value.chains[0].rules[-1].terminal_fallthrough)
        self.assertEqual(len(value.current_jumps), 1)
        self.assertFalse(value.current_jumps[0].stale)

    def test_terminal_fallthrough_must_be_last(self):
        value = observe_device_firewall_structure(
            owned(
                child_chain(),
                jump(),
                fallthrough(order=20),
                explicit_rule(
                    action={"return": None},
                    order=21,
                    handle=71,
                ),
            ),
            (HOST, VPN),
        )
        self.assertFalse(value.conflict_free)
        self.assertTrue(
            any("fallthrough is not last" in item.reason for item in value.conflicts)
        )

    def test_jump_target_must_be_owned_child_chain(self):
        value = observe_device_firewall_structure(
            owned(jump(target="missing")),
            (HOST, VPN),
        )
        self.assertFalse(value.conflict_free)
        self.assertTrue(
            any("target is not an owned child chain" in item.reason for item in value.conflicts)
        )

    def test_unresolved_numeric_jump_is_stale_not_current(self):
        value = observe_device_firewall_structure(
            owned(
                child_chain(),
                jump(ingress="99", egress="100"),
            ),
            (HOST, VPN),
        )
        self.assertTrue(value.conflict_free)
        self.assertEqual(value.current_jumps, ())
        self.assertEqual(len(value.stale_jumps), 1)
        self.assertTrue(value.stale_jumps[0].stale)

    def test_unrecognized_rule_in_owned_child_is_conflict(self):
        value = observe_device_firewall_structure(
            owned(
                child_chain(),
                jump(),
                explicit_rule(
                    action={"accept": None},
                    order=20,
                    handle=70,
                ),
            ),
            (HOST, VPN),
        )
        self.assertFalse(value.conflict_free)
        self.assertTrue(
            any("action is not return/drop/reject" in item.reason for item in value.conflicts)
        )


if __name__ == "__main__":
    unittest.main()
