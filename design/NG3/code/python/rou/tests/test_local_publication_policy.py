from __future__ import annotations

import json
import unittest
from ipaddress import IPv4Address

from rou.interface_identity import InterfaceIdentity
from rou.local_publication_observation import compare_local_publication
from rou.local_publication_policy import (
    LocalPublicationDesiredState,
    LocalPublicationHook,
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


HOST = InterfaceIdentity("host0", 10)
NEW_HOST = InterfaceIdentity("host0", 11)
ADDR = IPv4Address("198.51.100.46")


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


def scaffold_objects():
    rows = []
    for order, spec in enumerate(PAYLOAD_NFT_SCAFFOLD, start=1):
        rows.append(
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
    return tuple(rows)


def match(left, right):
    return {"match": {"op": "==", "left": left, "right": right}}


def pub_rule(*, hook: str, protocol: str, ifref: str, handle: int):
    if hook == "input":
        chain = "stack_input"
        iface = match({"meta": {"key": "iif"}}, ifref)
        addr = match(
            {"payload": {"protocol": "ip", "field": "daddr"}},
            str(ADDR),
        )
        port = match(
            {"payload": {"protocol": protocol, "field": "dport"}},
            44443,
        )
    else:
        chain = "stack_output"
        iface = match({"meta": {"key": "oif"}}, ifref)
        addr = match(
            {"payload": {"protocol": "ip", "field": "saddr"}},
            str(ADDR),
        )
        port = match(
            {"payload": {"protocol": protocol, "field": "sport"}},
            44443,
        )
    return obj(
        "rule",
        {
            "family": "ip",
            "table": "vpn_gate",
            "chain": chain,
            "handle": handle,
            "comment": "vpn-gate:ng3:local-publication-v1",
            "expr": [iface, addr, port, {"accept": None}],
        },
        handle,
    )


def observation(*rules):
    return NftNamespaceObservation(
        status=NftNamespaceStatus.OWNED,
        objects=scaffold_objects() + tuple(rules),
        observed_comment=NG3_NFT_OWNER_COMMENT,
    )


class LocalPublicationPolicyTests(unittest.TestCase):
    def test_projection_builds_input_output_pair_and_deduplicates(self):
        left = PublicationLocalEndpointIntent(
            "device-a",
            PublicationProtocol.TCP,
            ADDR,
            44443,
            HOST,
        )
        right = PublicationLocalEndpointIntent(
            "device-b",
            PublicationProtocol.TCP,
            ADDR,
            44443,
            HOST,
        )
        desired = build_local_publication_desired((left, right))
        self.assertEqual(len(desired.rules), 2)
        self.assertEqual(
            {rule.hook for rule in desired.rules},
            {LocalPublicationHook.INPUT, LocalPublicationHook.OUTPUT},
        )

    def test_exact_tcp_pair_confirms(self):
        desired = build_local_publication_desired(
            (
                PublicationLocalEndpointIntent(
                    "device",
                    PublicationProtocol.TCP,
                    ADDR,
                    44443,
                    HOST,
                ),
            )
        )
        result = compare_local_publication(
            observation(
                pub_rule(
                    hook="input",
                    protocol="tcp",
                    ifref="host0",
                    handle=20,
                ),
                pub_rule(
                    hook="output",
                    protocol="tcp",
                    ifref="host0",
                    handle=21,
                ),
            ),
            (HOST,),
            desired,
        )
        self.assertTrue(result.desired_confirmed)

    def test_same_name_old_ifindex_is_stale_not_current(self):
        desired = build_local_publication_desired(
            (
                PublicationLocalEndpointIntent(
                    "device",
                    PublicationProtocol.UDP,
                    ADDR,
                    44443,
                    NEW_HOST,
                ),
            )
        )
        result = compare_local_publication(
            observation(
                pub_rule(
                    hook="input",
                    protocol="udp",
                    ifref="10",
                    handle=20,
                ),
                pub_rule(
                    hook="output",
                    protocol="udp",
                    ifref="10",
                    handle=21,
                ),
            ),
            (NEW_HOST,),
            desired,
        )
        self.assertFalse(result.desired_confirmed)
        self.assertEqual(len(result.stale), 2)
        self.assertEqual(len(result.missing), 2)

    def test_malformed_owned_rule_is_conflict(self):
        desired = LocalPublicationDesiredState(())
        bad = pub_rule(
            hook="input",
            protocol="tcp",
            ifref="host0",
            handle=20,
        )
        row = json.loads(bad.canonical_json)
        row["rule"]["expr"][-1] = {"drop": None}
        bad = NftNamespaceObject(
            kind="rule",
            canonical_json=json.dumps(
                row, sort_keys=True, separators=(",", ":")
            ),
            source_order=20,
        )
        result = compare_local_publication(
            observation(bad),
            (HOST,),
            desired,
        )
        self.assertFalse(result.desired_confirmed)
        self.assertIn("plain accept", result.conflicts[0].reason)


if __name__ == "__main__":
    unittest.main()
