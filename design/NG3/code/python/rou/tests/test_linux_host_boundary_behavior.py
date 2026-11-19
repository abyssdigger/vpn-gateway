from __future__ import annotations

import json
import unittest

from rou.host_boundary_behavior import (
    HostBoundaryBehaviorIntent,
    HostBoundaryBehaviorLane,
)
from rou.linux_host_boundary_behavior import (
    HOST_BEHAVIOR_OUTPUT_COMMENT,
    HOST_BEHAVIOR_POSTROUTING_COMMENT,
    HOST_BEHAVIOR_PREROUTING_COMMENT,
    HOST_BEHAVIOR_TABLE,
    HOST_BEHAVIOR_TABLE_COMMENT,
    HostBoundaryBehaviorHostLane,
    LinuxHostBoundaryBehaviorNftBackend,
    build_host_boundary_behavior_nft_desired,
    converge_host_boundary_behavior_nft_once,
    parse_host_boundary_behavior_nft_observation,
    render_host_boundary_behavior_nft,
)
from rou.linux_policy_platform import (
    NG3_HOST_BOUNDARY_BEHAVIOR_LINUX_ALLOCATION,
)


LANES = (
    HostBoundaryBehaviorHostLane(
        HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
        "vnga-host0",
    ),
    HostBoundaryBehaviorHostLane(
        HostBoundaryBehaviorLane.STATEFUL_NAT,
        "vnga-host1",
    ),
    HostBoundaryBehaviorHostLane(
        HostBoundaryBehaviorLane.ROUTE_NO_NAT,
        "vnga-host2",
    ),
    HostBoundaryBehaviorHostLane(
        HostBoundaryBehaviorLane.ROUTE_NAT,
        "vnga-host3",
    ),
)


def desired_all():
    return build_host_boundary_behavior_nft_desired(
        (
            HostBoundaryBehaviorIntent(
                "s0",
                HostBoundaryBehaviorLane.STATEFUL_NO_NAT,
            ),
            HostBoundaryBehaviorIntent(
                "s1",
                HostBoundaryBehaviorLane.STATEFUL_NAT,
            ),
            HostBoundaryBehaviorIntent(
                "r0",
                HostBoundaryBehaviorLane.ROUTE_NO_NAT,
            ),
            HostBoundaryBehaviorIntent(
                "r1",
                HostBoundaryBehaviorLane.ROUTE_NAT,
            ),
        ),
        LANES,
        NG3_HOST_BOUNDARY_BEHAVIOR_LINUX_ALLOCATION,
    )


def exact_json(spec):
    rows = [
        {"table": {
            "family": "inet",
            "name": HOST_BEHAVIOR_TABLE,
            "comment": HOST_BEHAVIOR_TABLE_COMMENT,
        }},
        {"chain": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "name": "prerouting",
            "type": "filter",
            "hook": "prerouting",
            "prio": -150,
            "policy": "accept",
            "comment": HOST_BEHAVIOR_PREROUTING_COMMENT,
        }},
        {"chain": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "name": "output",
            "type": "route",
            "hook": "output",
            "prio": -150,
            "policy": "accept",
            "comment": HOST_BEHAVIOR_OUTPUT_COMMENT,
        }},
        {"chain": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "name": "postrouting",
            "type": "nat",
            "hook": "postrouting",
            "prio": 100,
            "policy": "accept",
            "comment": HOST_BEHAVIOR_POSTROUTING_COMMENT,
        }},
    ]

    for item in spec.lanes:
        suffix = item.lane.value.replace("_", "-")
        rows.append({"rule": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "chain": "prerouting",
            "comment": f"vpn-gate:ng3:host-behavior-classify-v1:{suffix}",
            "expr": [
                {"match": {"left": {"meta": {"key": "iifname"}}, "right": item.host_interface}},
                {"match": {"left": {"ct": {"key": "state"}}, "right": "new"}},
                {"mangle": {"key": {"ct": {"key": "mark"}}, "value": item.class_mark}},
                {"return": None},
            ],
        }})
        rows.append({"rule": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "chain": "prerouting",
            "comment": f"vpn-gate:ng3:host-behavior-lane-return-v1:{suffix}",
            "expr": [
                {"match": {"left": {"meta": {"key": "iifname"}}, "right": item.host_interface}},
                {"return": None},
            ],
        }})

    for item in spec.lanes:
        if not item.lane.stateful_return:
            continue
        suffix = item.lane.value.replace("_", "-")
        rows.append({"rule": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "chain": "prerouting",
            "comment": f"vpn-gate:ng3:host-behavior-preroute-return-v1:{suffix}",
            "expr": [
                {"match": {"left": {"ct": {"key": "mark"}}, "right": item.class_mark}},
                {"mangle": {"key": {"meta": {"key": "mark"}}, "value": spec.return_mark}},
            ],
        }})

    for item in spec.lanes:
        if not item.lane.stateful_return:
            continue
        suffix = item.lane.value.replace("_", "-")
        rows.append({"rule": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "chain": "output",
            "comment": f"vpn-gate:ng3:host-behavior-output-return-v1:{suffix}",
            "expr": [
                {"match": {"left": {"ct": {"key": "mark"}}, "right": item.class_mark}},
                {"mangle": {"key": {"meta": {"key": "mark"}}, "value": spec.return_mark}},
            ],
        }})

    for item in spec.lanes:
        if not item.lane.gateway_nat:
            continue
        suffix = item.lane.value.replace("_", "-")
        rows.append({"rule": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "chain": "postrouting",
            "comment": f"vpn-gate:ng3:host-behavior-nat-v1:{suffix}",
            "expr": [
                {"match": {"left": {"ct": {"key": "mark"}}, "right": item.class_mark}},
                {"masquerade": None},
            ],
        }})

    return json.dumps({"nftables": rows})


class StatefulFakeRunner:
    def __init__(self, exact):
        self.exact = exact
        self.present = False
        self.scripts = []

    def run(self, argv):
        if self.present:
            return self.exact
        return json.dumps({"nftables": []})

    def run_script(self, argv, script):
        self.scripts.append((tuple(argv), script))
        self.present = HOST_BEHAVIOR_TABLE in script


class HostBoundaryBehaviorLinuxTests(unittest.TestCase):
    def test_profiles_with_same_behavior_share_one_host_lane_rule_set(self):
        desired = build_host_boundary_behavior_nft_desired(
            (
                HostBoundaryBehaviorIntent(
                    "a",
                    HostBoundaryBehaviorLane.STATEFUL_NAT,
                ),
                HostBoundaryBehaviorIntent(
                    "b",
                    HostBoundaryBehaviorLane.STATEFUL_NAT,
                ),
            ),
            LANES,
            NG3_HOST_BOUNDARY_BEHAVIOR_LINUX_ALLOCATION,
        )
        self.assertIsNotNone(desired)
        self.assertEqual(len(desired.lanes), 1)
        self.assertIs(
            desired.lanes[0].lane,
            HostBoundaryBehaviorLane.STATEFUL_NAT,
        )

    def test_renderer_has_lane_guard_return_stateful_restore_and_nat(self):
        spec = desired_all()
        self.assertIsNotNone(spec)
        script = render_host_boundary_behavior_nft(spec)
        self.assertIn(
            'iifname "vnga-host1" ct state new ct mark set 0x30000002 return',
            script,
        )
        self.assertIn(
            'iifname "vnga-host1" return',
            script,
        )
        self.assertIn(
            'ct mark 0x30000002 meta mark set 0x56504e47',
            script,
        )
        self.assertIn(
            'ct mark 0x30000002 masquerade',
            script,
        )
        self.assertIn(
            'ct mark 0x30000004 masquerade',
            script,
        )
        self.assertNotIn(
            'ct mark 0x30000003 masquerade',
            script,
        )

    def test_exact_authoritative_observation_accepts_all_four_classes(self):
        spec = desired_all()
        self.assertIsNotNone(spec)
        observed = parse_host_boundary_behavior_nft_observation(
            exact_json(spec),
            spec,
        )
        self.assertTrue(observed.exact)
        self.assertEqual(observed.conflicts, ())

    def test_foreign_rule_in_owned_table_is_conflict(self):
        spec = desired_all()
        self.assertIsNotNone(spec)
        root = json.loads(exact_json(spec))
        root["nftables"].append({"rule": {
            "family": "inet",
            "table": HOST_BEHAVIOR_TABLE,
            "chain": "postrouting",
            "comment": "foreign",
            "expr": [{"accept": None}],
        }})
        observed = parse_host_boundary_behavior_nft_observation(
            json.dumps(root),
            spec,
        )
        self.assertFalse(observed.exact)
        self.assertTrue(observed.conflicts)

    def test_convergence_replaces_absent_owner_and_confirms_fresh_state(self):
        spec = desired_all()
        self.assertIsNotNone(spec)
        runner = StatefulFakeRunner(exact_json(spec))
        backend = LinuxHostBoundaryBehaviorNftBackend(runner)
        result = converge_host_boundary_behavior_nft_once(
            backend,
            spec,
        )
        self.assertTrue(result.exact)
        self.assertEqual(len(runner.scripts), 1)


if __name__ == "__main__":
    unittest.main()
