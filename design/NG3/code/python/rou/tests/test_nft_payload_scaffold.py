from __future__ import annotations

import json
import unittest

from rou.nft_namespace_inventory import (
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import (
    PAYLOAD_FORWARD_CHAIN,
    PAYLOAD_NFT_SCAFFOLD,
    PAYLOAD_POSTROUTING_CHAIN,
    compare_payload_nft_scaffold,
)


def obj(kind, payload):
    return NftNamespaceObject(
        kind=kind,
        canonical_json=json.dumps(
            {kind: payload},
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def chain(name, *, bad=None):
    if name == PAYLOAD_FORWARD_CHAIN:
        payload = {
            "family": "ip",
            "table": "vpn_gate",
            "name": name,
            "handle": 1,
            "type": "filter",
            "hook": "forward",
            "prio": 0,
            "policy": "drop",
            "comment": "vpn-gate:ng3:payload-forward-v1",
        }
    else:
        payload = {
            "family": "ip",
            "table": "vpn_gate",
            "name": name,
            "handle": 2,
            "type": "nat",
            "hook": "postrouting",
            "prio": 100,
            "policy": "accept",
            "comment": "vpn-gate:ng3:payload-postrouting-v1",
        }
    if bad:
        payload.update(bad)
    return obj("chain", payload)


class NftPayloadScaffoldTests(unittest.TestCase):
    def test_absent_namespace_reports_both_chains_missing(self):
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.ABSENT,
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(result.missing_chains, PAYLOAD_NFT_SCAFFOLD)
        self.assertEqual(result.conflicts, ())

    def test_exact_exp032_metadata_confirms_scaffold(self):
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=(
                    chain(PAYLOAD_POSTROUTING_CHAIN),
                    chain(PAYLOAD_FORWARD_CHAIN),
                ),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertTrue(result.scaffold_confirmed)
        self.assertTrue(result.full_policy_classified)
        self.assertEqual(result.confirmed_chains, PAYLOAD_NFT_SCAFFOLD)

    def test_missing_chain_is_repairable_missing_not_marker_conflict(self):
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=(chain(PAYLOAD_FORWARD_CHAIN),),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(
            [item.name for item in result.missing_chains],
            [PAYLOAD_POSTROUTING_CHAIN],
        )
        self.assertEqual(result.conflicts, ())

    def test_wrong_invariant_chain_metadata_is_conflict(self):
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=(
                    chain(PAYLOAD_FORWARD_CHAIN, bad={"policy": "accept"}),
                    chain(PAYLOAD_POSTROUTING_CHAIN),
                ),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("policy", result.conflicts[0].reason)

    def test_handle_change_does_not_change_scaffold_identity(self):
        forward = chain(PAYLOAD_FORWARD_CHAIN, bad={"handle": 999})
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=(
                    forward,
                    chain(PAYLOAD_POSTROUTING_CHAIN),
                ),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertTrue(result.scaffold_confirmed)

    def test_rules_and_future_objects_remain_unclassified(self):
        rule = obj(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_forward",
                "handle": 8,
                "expr": [{"accept": None}],
            },
        )
        future_chain = obj(
            "chain",
            {
                "family": "ip",
                "table": "vpn_gate",
                "name": "probe_output",
                "handle": 9,
            },
        )
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=(
                    chain(PAYLOAD_FORWARD_CHAIN),
                    chain(PAYLOAD_POSTROUTING_CHAIN),
                    rule,
                    future_chain,
                ),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertTrue(result.scaffold_confirmed)
        self.assertFalse(result.full_policy_classified)
        self.assertEqual(
            {item.kind for item in result.unclassified_objects},
            {"rule", "chain"},
        )

    def test_table_conflict_propagates_without_adoption(self):
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.CONFLICT,
                observed_comment="foreign",
                conflict_reason="wrong marker",
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("wrong marker", result.conflicts[0].reason)

    def test_duplicate_invariant_chain_is_conflict(self):
        duplicate = chain(PAYLOAD_FORWARD_CHAIN, bad={"handle": 50})
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=(
                    chain(PAYLOAD_FORWARD_CHAIN),
                    duplicate,
                    chain(PAYLOAD_POSTROUTING_CHAIN),
                ),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("duplicate", result.conflicts[0].reason)


if __name__ == "__main__":
    unittest.main()
