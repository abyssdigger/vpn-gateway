from __future__ import annotations

import json
import unittest
from ipaddress import IPv4Network

from rou.linux_aggressive_escape_guard import (
    AGGRESSIVE_GUARD_OWNER_COMMENT,
    AGGRESSIVE_GUARD_TABLE,
    AggressiveEscapeGuardDesired,
    AggressiveEscapeGuardObservationStatus,
    AggressiveEscapeGuardState,
    parse_aggressive_escape_guard_ruleset,
)
from rou.linux_aggressive_routing_authority import (
    _is_standard_local_rule,
)


def doc(*rows):
    return json.dumps({"nftables": list(rows)})


class AggressiveEscapeGuardTests(unittest.TestCase):
    def test_full_tunnel_collapses_narrower_destinations(self):
        desired = AggressiveEscapeGuardDesired(
            AggressiveEscapeGuardState.ENABLED,
            "vpng0",
            (
                IPv4Network("10.0.0.0/8"),
                IPv4Network("0.0.0.0/0"),
            ),
        )
        self.assertEqual(
            desired.managed_destinations,
            (IPv4Network("0.0.0.0/0"),),
        )

    def test_absent_and_foreign_table_are_distinct(self):
        desired = AggressiveEscapeGuardDesired(
            AggressiveEscapeGuardState.ENABLED,
            "vpng0",
            (IPv4Network("10.0.0.0/8"),),
        )
        absent = parse_aggressive_escape_guard_ruleset(
            doc({"metainfo": {}}),
            desired,
        )
        foreign = parse_aggressive_escape_guard_ruleset(
            doc(
                {
                    "table": {
                        "family": "inet",
                        "name": AGGRESSIVE_GUARD_TABLE,
                        "comment": "foreign",
                    }
                }
            ),
            desired,
        )
        self.assertEqual(
            absent.status,
            AggressiveEscapeGuardObservationStatus.ABSENT,
        )
        self.assertEqual(
            foreign.status,
            AggressiveEscapeGuardObservationStatus.CONFLICT,
        )

    def test_disabled_owned_table_is_repairable_drift(self):
        desired = AggressiveEscapeGuardDesired(
            AggressiveEscapeGuardState.DISABLED
        )
        value = parse_aggressive_escape_guard_ruleset(
            doc(
                {
                    "table": {
                        "family": "inet",
                        "name": AGGRESSIVE_GUARD_TABLE,
                        "comment": AGGRESSIVE_GUARD_OWNER_COMMENT,
                    }
                }
            ),
            desired,
        )
        self.assertEqual(
            value.status,
            AggressiveEscapeGuardObservationStatus.OWNED_DRIFT,
        )

    def test_only_canonical_local_rule_is_exempt_from_preemption(self):
        self.assertTrue(
            _is_standard_local_rule(
                {"priority": 0, "table": "local", "protocol": "kernel"}
            )
        )
        self.assertFalse(
            _is_standard_local_rule(
                {
                    "priority": 0,
                    "table": "local",
                    "protocol": "kernel",
                    "fwmark": 1,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
