from __future__ import annotations

import json
import unittest

from rou.composite_nft_policy import (
    CompositeNftDesiredState,
    compare_composite_nft_policy,
)
from rou.device_firewall_desired import DeviceFirewallDesiredState
from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import PAYLOAD_NFT_SCAFFOLD
from rou.payload_forward_desired import PayloadForwardDesiredState
from rou.payload_nat_desired import PayloadNatDesiredState


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
