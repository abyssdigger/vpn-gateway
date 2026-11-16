from __future__ import annotations

import json
import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.composite_nft_policy import (
    CompositeNftDesiredState,
    compare_composite_nft_policy,
)
from rou.binding import LogicalPathId
from rou.device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallDesiredState,
    DeviceFirewallRuleSpec,
)
from rou.device_firewall_structure import DeviceFirewallRuleAction
from rou.interface_identity import InterfaceIdentity
from rou.local_publication_policy import (
    PublicationLocalEndpointIntent,
    PublicationProtocol,
    build_local_publication_desired,
)
from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import PAYLOAD_NFT_SCAFFOLD
from rou.payload_forward_desired import (
    PayloadForwardDesiredState,
    PayloadForwardRuleSpec,
)
from rou.payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from rou.payload_nat_desired import (
    PayloadMasqueradeSpec,
    PayloadNatDesiredState,
)


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


def observation(*extra: NftNamespaceObject) -> NftNamespaceObservation:
    return NftNamespaceObservation(
        status=NftNamespaceStatus.OWNED,
        objects=scaffold_objects() + tuple(extra),
        observed_comment=NG3_NFT_OWNER_COMMENT,
    )


EMPTY = CompositeNftDesiredState(
    profile_forward=PayloadForwardDesiredState(()),
    payload_nat=PayloadNatDesiredState(()),
    device_firewall=DeviceFirewallDesiredState(()),
)


class CompositeNftPolicyTests(unittest.TestCase):
    def test_empty_scaffold_is_exact_current_composite_state(self):
        result = compare_composite_nft_policy(
            observation(),
            (),
            EMPTY,
        )
        self.assertTrue(result.desired_confirmed)
        self.assertEqual(result.conflicts, ())


    def test_profile_device_and_nat_coexist_as_one_confirmed_scope(self):
        host = InterfaceIdentity("host0", 10)
        vpn = InterfaceIdentity("vpn0", 20)
        path_id = LogicalPathId("device", 0, 0)

        forward_spec = PayloadForwardRuleSpec(
            kind=PayloadForwardRuleKind.NEW,
            ingress=host,
            egress=vpn,
            remote_field=PayloadForwardRemoteField.DESTINATION,
            remote_prefix=IPv4Network("10.0.0.0/8"),
        )
        nat_spec = PayloadMasqueradeSpec(path_id, host, vpn)
        terminal = DeviceFirewallRuleSpec(
            match_expr_json=(),
            action=DeviceFirewallRuleAction.DROP,
            action_json='{"drop":null}',
            terminal_fallthrough=True,
        )
        device_spec = DeviceFirewallChainSpec(
            ingress=host,
            egress=vpn,
            child_chain_name="dfw_out",
            rules=(terminal,),
        )
        desired = CompositeNftDesiredState(
            profile_forward=PayloadForwardDesiredState((forward_spec,)),
            payload_nat=PayloadNatDesiredState((nat_spec,)),
            device_firewall=DeviceFirewallDesiredState((device_spec,)),
        )

        forward = obj(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_forward",
                "handle": 40,
                "comment": "vpn-gate:ng3:payload-forward-new-v1",
                "expr": [
                    {"match": {"op": "in", "left": {"ct": {"key": "state"}}, "right": "new"}},
                    {"match": {"op": "==", "left": {"meta": {"key": "iif"}}, "right": "host0"}},
                    {"match": {"op": "==", "left": {"meta": {"key": "oif"}}, "right": "vpn0"}},
                    {"match": {"op": "==", "left": {"payload": {"protocol": "ip", "field": "daddr"}}, "right": {"prefix": {"addr": "10.0.0.0", "len": 8}}}},
                    {"accept": None},
                ],
            },
            40,
        )
        nat = obj(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_postrouting",
                "handle": 41,
                "comment": "vpn-gate:ng3:payload-nat-v1",
                "expr": [
                    {"match": {"op": "==", "left": {"meta": {"key": "iif"}}, "right": "host0"}},
                    {"match": {"op": "==", "left": {"meta": {"key": "oif"}}, "right": "vpn0"}},
                    {"masquerade": None},
                ],
            },
            41,
        )
        child = obj(
            "chain",
            {
                "family": "ip",
                "table": "vpn_gate",
                "name": "dfw_out",
                "handle": 42,
                "comment": "vpn-gate:ng3:device-fw-child-v1",
            },
            42,
        )
        jump = obj(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_forward",
                "handle": 43,
                "comment": "vpn-gate:ng3:device-fw-jump-v1",
                "expr": [
                    {"match": {"op": "==", "left": {"meta": {"key": "iif"}}, "right": "host0"}},
                    {"match": {"op": "==", "left": {"meta": {"key": "oif"}}, "right": "vpn0"}},
                    {"jump": {"target": "dfw_out"}},
                ],
            },
            43,
        )
        fallthrough = obj(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "dfw_out",
                "handle": 44,
                "comment": "vpn-gate:ng3:device-fw-fallthrough-v1",
                "expr": [{"drop": None}],
            },
            44,
        )

        result = compare_composite_nft_policy(
            observation(child, jump, forward, nat, fallthrough),
            (host, vpn),
            desired,
        )
        self.assertTrue(result.desired_confirmed)
        self.assertEqual(result.conflicts, ())


    def test_exact_local_publication_is_classified_in_composite_scope(self):
        host = InterfaceIdentity("host0", 10)
        address = IPv4Address("198.51.100.46")
        local_desired = build_local_publication_desired(
            (
                PublicationLocalEndpointIntent(
                    "device",
                    PublicationProtocol.TCP,
                    address,
                    44443,
                    host,
                ),
            )
        )
        desired = CompositeNftDesiredState(
            profile_forward=PayloadForwardDesiredState(()),
            payload_nat=PayloadNatDesiredState(()),
            device_firewall=DeviceFirewallDesiredState(()),
            local_publication=local_desired,
        )

        def local_rule(chain, ifkey, addr_field, port_field, handle):
            return obj(
                "rule",
                {
                    "family": "ip",
                    "table": "vpn_gate",
                    "chain": chain,
                    "handle": handle,
                    "comment": "vpn-gate:ng3:local-publication-v1",
                    "expr": [
                        {"match": {"op": "==", "left": {"meta": {"key": ifkey}}, "right": "host0"}},
                        {"match": {"op": "==", "left": {"payload": {"protocol": "ip", "field": addr_field}}, "right": str(address)}},
                        {"match": {"op": "==", "left": {"payload": {"protocol": "tcp", "field": port_field}}, "right": 44443}},
                        {"accept": None},
                    ],
                },
                handle,
            )

        result = compare_composite_nft_policy(
            observation(
                local_rule("stack_input", "iif", "daddr", "dport", 50),
                local_rule("stack_output", "oif", "saddr", "sport", 51),
            ),
            (host,),
            desired,
        )
        self.assertTrue(result.desired_confirmed)
        self.assertEqual(result.conflicts, ())

    def test_unclassified_local_system_rule_is_conflict(self):
        local = obj(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "stack_input",
                "handle": 20,
                "comment": "vpn-gate:ng3:future-local-v1",
                "expr": [{"accept": None}],
            },
            20,
        )
        result = compare_composite_nft_policy(
            observation(local),
            (),
            EMPTY,
        )
        self.assertFalse(result.desired_confirmed)
        self.assertTrue(
            any("unclassified nft rule" in item.reason for item in result.conflicts)
        )

    def test_unclassified_child_chain_is_conflict(self):
        chain = obj(
            "chain",
            {
                "family": "ip",
                "table": "vpn_gate",
                "name": "foreign_child",
                "handle": 30,
                "comment": "foreign",
            },
            30,
        )
        result = compare_composite_nft_policy(
            observation(chain),
            (),
            EMPTY,
        )
        self.assertFalse(result.desired_confirmed)
        self.assertTrue(
            any("unclassified nft chain" in item.reason for item in result.conflicts)
        )


if __name__ == "__main__":
    unittest.main()
