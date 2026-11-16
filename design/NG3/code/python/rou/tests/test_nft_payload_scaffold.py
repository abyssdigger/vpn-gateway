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
    specs = {spec.name: spec for spec in PAYLOAD_NFT_SCAFFOLD}
    spec = specs[name]
    handle = next(
        index
        for index, candidate in enumerate(PAYLOAD_NFT_SCAFFOLD, start=1)
        if candidate.name == name
    )
    payload = {
        "family": "ip",
        "table": "vpn_gate",
        "name": name,
        "handle": handle,
        "type": spec.chain_type,
        "hook": spec.hook,
        "prio": spec.priority,
        "policy": spec.policy,
        "comment": spec.comment,
    }
    if bad:
        payload.update(bad)
    return obj("chain", payload)


def exact_objects():
    return tuple(chain(spec.name) for spec in PAYLOAD_NFT_SCAFFOLD)


class NftPayloadScaffoldTests(unittest.TestCase):
    def test_absent_namespace_reports_all_chains_missing(self):
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.ABSENT,
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(result.missing_chains, PAYLOAD_NFT_SCAFFOLD)
        self.assertEqual(result.conflicts, ())

    def test_exact_exp032_exp040_metadata_confirms_scaffold(self):
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=tuple(reversed(exact_objects())),
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
                objects=tuple(
                    chain(spec.name)
                    for spec in PAYLOAD_NFT_SCAFFOLD
                    if spec.name != PAYLOAD_POSTROUTING_CHAIN
                ),
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
        objects = []
        for spec in PAYLOAD_NFT_SCAFFOLD:
            if spec.name == PAYLOAD_FORWARD_CHAIN:
                objects.append(chain(spec.name, bad={"policy": "accept"}))
            else:
                objects.append(chain(spec.name))
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=tuple(objects),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("policy", result.conflicts[0].reason)

    def test_handle_change_does_not_change_scaffold_identity(self):
        objects = []
        for spec in PAYLOAD_NFT_SCAFFOLD:
            if spec.name == PAYLOAD_FORWARD_CHAIN:
                objects.append(chain(spec.name, bad={"handle": 999}))
            else:
                objects.append(chain(spec.name))
        result = compare_payload_nft_scaffold(
            NftNamespaceObservation(
                status=NftNamespaceStatus.OWNED,
                objects=tuple(objects),
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
                objects=exact_objects() + (rule, future_chain),
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
                objects=exact_objects() + (duplicate,),
                observed_comment="vpn-gate:ng3:owner-v1",
            )
        )
        self.assertFalse(result.scaffold_confirmed)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("duplicate", result.conflicts[0].reason)


if __name__ == "__main__":
    unittest.main()
