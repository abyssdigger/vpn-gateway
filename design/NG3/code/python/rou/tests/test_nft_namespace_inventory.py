from __future__ import annotations

import json
import unittest

from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    LinuxNftNamespaceBackend,
    NftNamespaceInventoryError,
    NftNamespaceStatus,
    parse_nft_namespace_ruleset,
)


class FakeRunner:
    def __init__(self, output):
        self.output = output
        self.commands = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def doc(*rows):
    return json.dumps({"nftables": list(rows)})


def table(*, comment_marker=True, handle=2, **extra):
    payload = {
        "family": "ip",
        "name": "vpn_gate",
        "handle": handle,
    }
    if comment_marker is True:
        payload["comment"] = NG3_NFT_OWNER_COMMENT
    elif isinstance(comment_marker, str):
        payload["comment"] = comment_marker
    payload.update(extra)
    return {"table": payload}


class NftNamespaceInventoryTests(unittest.TestCase):
    def test_absent_reserved_table_is_valid_empty_state(self):
        value = parse_nft_namespace_ruleset(
            doc(
                {"metainfo": {"json_schema_version": 1}},
                {
                    "table": {
                        "family": "ip",
                        "name": "foreign",
                        "handle": 1,
                    }
                },
            )
        )
        self.assertEqual(value.status, NftNamespaceStatus.ABSENT)
        self.assertEqual(value.objects, ())
        self.assertFalse(value.marker_confirmed)

    def test_exact_marker_confirms_table_level_ownership(self):
        value = parse_nft_namespace_ruleset(
            doc(table())
        )
        self.assertEqual(value.status, NftNamespaceStatus.OWNED)
        self.assertTrue(value.marker_confirmed)
        self.assertEqual(
            value.observed_comment,
            NG3_NFT_OWNER_COMMENT,
        )

    def test_table_handle_is_not_ownership_identity(self):
        one = parse_nft_namespace_ruleset(doc(table(handle=2)))
        two = parse_nft_namespace_ruleset(doc(table(handle=999)))
        self.assertEqual(one, two)

    def test_unmarked_or_wrong_marker_is_conflict(self):
        missing = parse_nft_namespace_ruleset(
            doc(table(comment_marker=False))
        )
        wrong = parse_nft_namespace_ruleset(
            doc(table(comment_marker="other-owner"))
        )
        self.assertEqual(missing.status, NftNamespaceStatus.CONFLICT)
        self.assertEqual(wrong.status, NftNamespaceStatus.CONFLICT)
        self.assertIsNone(missing.observed_comment)
        self.assertEqual(wrong.observed_comment, "other-owner")

    def test_unknown_table_semantics_are_conflict_not_silently_ignored(self):
        value = parse_nft_namespace_ruleset(
            doc(table(flags=["dormant"]))
        )
        self.assertEqual(value.status, NftNamespaceStatus.CONFLICT)
        self.assertIn("unsupported fields", value.conflict_reason)

    def test_contained_objects_are_preserved_canonically(self):
        value = parse_nft_namespace_ruleset(
            doc(
                table(),
                {
                    "rule": {
                        "family": "ip",
                        "table": "vpn_gate",
                        "chain": "payload_forward",
                        "handle": 8,
                        "expr": [{"drop": None}],
                    }
                },
                {
                    "chain": {
                        "family": "ip",
                        "table": "vpn_gate",
                        "name": "payload_forward",
                        "handle": 4,
                    }
                },
            )
        )
        self.assertEqual(value.status, NftNamespaceStatus.OWNED)
        self.assertEqual(
            [item.kind for item in value.objects],
            ["chain", "rule"],
        )
        self.assertTrue(
            all("vpn_gate" in item.canonical_json for item in value.objects)
        )
        # Canonical object sorting remains stable for existing consumers, while
        # source_order preserves the physical nft JSON sequence for ordered
        # policy observers.
        self.assertEqual(
            [item.source_order for item in value.objects],
            [2, 1],
        )

    def test_foreign_family_or_table_objects_are_ignored(self):
        value = parse_nft_namespace_ruleset(
            doc(
                table(),
                {
                    "chain": {
                        "family": "ip",
                        "table": "foreign",
                        "name": "x",
                    }
                },
                {
                    "chain": {
                        "family": "inet",
                        "table": "vpn_gate",
                        "name": "x",
                    }
                },
            )
        )
        self.assertEqual(value.objects, ())

    def test_reserved_objects_without_table_are_observation_error(self):
        with self.assertRaisesRegex(
            NftNamespaceInventoryError,
            "without reserved table",
        ):
            parse_nft_namespace_ruleset(
                doc(
                    {
                        "chain": {
                            "family": "ip",
                            "table": "vpn_gate",
                            "name": "x",
                        }
                    }
                )
            )

    def test_malformed_json_is_not_absent(self):
        with self.assertRaisesRegex(
            NftNamespaceInventoryError,
            "invalid nft ruleset JSON",
        ):
            parse_nft_namespace_ruleset("{")

    def test_backend_uses_full_ruleset_inventory(self):
        runner = FakeRunner(doc(table()))
        backend = LinuxNftNamespaceBackend(
            runner=runner,
            namespace="managed",
        )
        value = backend.observe_nft_namespace()
        self.assertTrue(value.marker_confirmed)
        self.assertEqual(
            runner.commands,
            [
                (
                    "ip",
                    "netns",
                    "exec",
                    "managed",
                    "nft",
                    "-j",
                    "list",
                    "ruleset",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
