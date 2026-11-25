from __future__ import annotations

from ipaddress import IPv4Address, IPv4Interface, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.probe_runtime import (
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from rou.release1_config import (
    ManagedVpnKind,
    ManagedWireGuardConfig,
    ManagedWireGuardGroupConfig,
    ManagedWireGuardPeerConfig,
    WireGuardPeerMembershipConfig,
)
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_peer_manager import WireGuardPeerManager
from rou.wireguard_peer_ownership import (
    WireGuardPeerOwnershipObservation,
    WireGuardPeerOwnershipResult,
)


PATH = LogicalPathId("wg", 0, 0)
EP = InterfaceIdentity("wg0", 17)
ROUTE = RoutePriorityPathRoute(PATH, EP)
CORP = IPv4Network("10.77.0.0/24")
STORAGE = IPv4Network("10.88.0.0/24")


def peer(peer_id, key, target):
    return ManagedWireGuardPeerConfig(
        peer_id=peer_id,
        public_key=key,
        endpoint_address=IPv4Address("198.51.100.10"),
        endpoint_port=51820,
        probe_target=IPv4Address(target),
    )


A = peer("a", "a-key", "10.201.0.1")
B = peer("b", "b-key", "10.201.0.2")
C = peer("c", "c-key", "10.201.0.3")


def config(peers=(A, B, C)):
    return ManagedWireGuardConfig(
        kind=ManagedVpnKind.WIREGUARD,
        interface="wg0",
        address=IPv4Interface("10.200.0.1/32"),
        private_key_file="/run/private.key",
        listen_port=None,
        peers=tuple(peers),
    )


def membership(peer_id, reserve=False):
    return WireGuardPeerMembershipConfig(peer_id, reserve)


def group(profile_id, prefixes, memberships, *, availability_check=None):
    return ManagedWireGuardGroupConfig(
        profile_id=profile_id,
        device_id="wg",
        prefixes=tuple(prefixes),
        peer_memberships=tuple(memberships),
        availability_check=availability_check,
    )


def reply():
    return ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)


def no_reply():
    return ProbeTechnicalObservation(ProbeTechnicalOutcome.NO_REPLY)


def local_error(text="local error"):
    return ProbeTechnicalObservation(
        ProbeTechnicalOutcome.LOCAL_ERROR,
        text,
    )


class Probe:
    def __init__(self, outcomes):
        self.outcomes = {
            peer_id: list(values)
            for peer_id, values in outcomes.items()
        }
        self.calls = []

    def check(self, owner, peer, path_route):
        self.calls.append((owner, peer.peer_id, path_route))
        return self.outcomes[peer.peer_id].pop(0)


class Ownership:
    def __init__(self, *, confirmed=True, diagnostic=None):
        self.confirmed = confirmed
        self.diagnostic = diagnostic
        self.calls = []

    def converge(self, desired):
        self.calls.append(desired)
        observation = WireGuardPeerOwnershipObservation(
            desired.device_id,
            desired.interface,
            desired.peers,
        )
        return WireGuardPeerOwnershipResult(
            self.confirmed,
            True,
            observation if self.confirmed else None,
            None if self.confirmed else (self.diagnostic or "not confirmed"),
        )


def allowed_by_key(desired):
    return {
        item.public_key: item.allowed_ips
        for item in desired.peers
    }


class WireGuardPeerManagerTests(unittest.TestCase):
    def test_groups_can_select_different_peers_and_share_fresh_peer_probe(self):
        groups = (
            group("corp", (CORP,), (membership("a"), membership("b"))),
            group("storage", (STORAGE,), (membership("b"), membership("a"))),
        )
        probe = Probe({"a": [reply()], "b": [reply()]})
        ownership = Ownership()

        result = WireGuardPeerManager().reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=probe,
            ownership=ownership,
        )

        self.assertTrue(result.ready)
        self.assertEqual(result.owner_for("corp"), "a")
        self.assertEqual(result.owner_for("storage"), "b")
        self.assertEqual([item[1] for item in probe.calls], ["a", "b"])
        by_key = allowed_by_key(ownership.calls[-1])
        self.assertIn(CORP, by_key[A.public_key])
        self.assertNotIn(STORAGE, by_key[A.public_key])
        self.assertIn(STORAGE, by_key[B.public_key])
        self.assertNotIn(CORP, by_key[B.public_key])

    def test_ordinary_owner_is_sticky_when_preferred_peer_recovers(self):
        groups = (
            group("corp", (CORP,), (membership("a"), membership("b"))),
        )
        manager = WireGuardPeerManager()
        first = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [no_reply()], "b": [reply()]}),
            ownership=Ownership(),
        )
        self.assertEqual(first.owner_for("corp"), "b")

        probe = Probe({"b": [reply()]})
        second = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=probe,
            ownership=Ownership(),
        )
        self.assertEqual(second.owner_for("corp"), "b")
        self.assertEqual(second.generation, first.generation)
        self.assertEqual([item[1] for item in probe.calls], ["b"])

    def test_reserve_owner_fails_back_to_preferred_ordinary_peer(self):
        groups = (
            group(
                "corp",
                (CORP,),
                (membership("a"), membership("b", reserve=True)),
            ),
        )
        manager = WireGuardPeerManager()
        first = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [no_reply()], "b": [reply()]}),
            ownership=Ownership(),
        )
        self.assertEqual(first.owner_for("corp"), "b")

        probe = Probe({"b": [reply()], "a": [reply()]})
        second = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=probe,
            ownership=Ownership(),
        )
        self.assertEqual(second.owner_for("corp"), "a")
        self.assertNotEqual(second.generation, first.generation)
        self.assertEqual([item[1] for item in probe.calls], ["b", "a"])

    def test_failed_peer_recovers_only_its_groups_and_probe_is_cached(self):
        groups = (
            group("corp", (CORP,), (membership("a"), membership("b"))),
            group("storage", (STORAGE,), (membership("b"), membership("a"))),
        )
        manager = WireGuardPeerManager()
        first = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()], "b": [reply()]}),
            ownership=Ownership(),
        )
        self.assertEqual(first.owner_for("corp"), "a")
        self.assertEqual(first.owner_for("storage"), "b")

        probe = Probe({"a": [no_reply()], "b": [reply()]})
        second = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=probe,
            ownership=Ownership(),
        )
        self.assertEqual(second.owner_for("corp"), "b")
        self.assertEqual(second.owner_for("storage"), "b")
        self.assertEqual([item[1] for item in probe.calls], ["a", "b"])

    def test_group_without_suitable_peer_has_no_owner_but_other_group_survives(self):
        groups = (
            group("corp", (CORP,), (membership("a"), membership("b"))),
            group("storage", (STORAGE,), (membership("c"),)),
        )
        ownership = Ownership()
        result = WireGuardPeerManager().reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({
                "a": [no_reply()],
                "b": [no_reply()],
                "c": [reply()],
            }),
            ownership=ownership,
        )

        self.assertFalse(result.ready)
        self.assertIsNone(result.owner_for("corp"))
        self.assertEqual(result.owner_for("storage"), "c")
        self.assertIsNotNone(result.generation)
        by_key = allowed_by_key(ownership.calls[-1])
        self.assertTrue(all(CORP not in allowed for allowed in by_key.values()))
        self.assertIn(STORAGE, by_key[C.public_key])

    def test_current_local_error_blocks_mutation_and_invalidates_generation(self):
        groups = (
            group("corp", (CORP,), (membership("a"), membership("b"))),
        )
        manager = WireGuardPeerManager()
        manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(),
        )
        ownership = Ownership()

        result = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [local_error("probe failed")]}),
            ownership=ownership,
        )

        self.assertFalse(result.ready)
        self.assertEqual(result.group_owners, ())
        self.assertIsNone(result.generation)
        self.assertIn("unconfirmed", result.problem)
        self.assertEqual(ownership.calls, [])
        self.assertIsNone(manager.current_state())

    def test_d003_failure_does_not_publish_new_generation(self):
        groups = (
            group("corp", (CORP,), (membership("a"),)),
        )
        result = WireGuardPeerManager().reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(confirmed=False, diagnostic="apply mismatch"),
        )

        self.assertEqual(result.group_owners, ())
        self.assertIsNone(result.generation)
        self.assertIn("apply mismatch", result.problem)

    def test_group_policy_or_owner_change_changes_device_generation(self):
        groups = (
            group("corp", (CORP,), (membership("a"), membership("b"))),
        )
        manager = WireGuardPeerManager()
        first = manager.reconcile(
            "wg",
            config(),
            groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(),
        )
        changed_groups = (
            group(
                "corp",
                (CORP,),
                (membership("a"), membership("b", reserve=True)),
            ),
        )
        second = manager.reconcile(
            "wg",
            config(),
            changed_groups,
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(),
        )
        self.assertNotEqual(second.generation, first.generation)

    def test_group_endpoint_is_rejected_before_probe_or_mutation(self):
        from rou.release1_config import AvailabilityCheckConfig

        groups = (
            group(
                "corp",
                (CORP,),
                (membership("a"),),
                availability_check=AvailabilityCheckConfig(
                    "icmp",
                    IPv4Address("10.77.0.1"),
                ),
            ),
        )
        probe = Probe({"a": [reply()]})
        ownership = Ownership()
        with self.assertRaisesRegex(
            ValueError,
            "group endpoint probing is not materialized",
        ):
            WireGuardPeerManager().reconcile(
                "wg",
                config(),
                groups,
                base_generation="base-a",
                path_route=ROUTE,
                probe=probe,
                ownership=ownership,
            )
        self.assertEqual(probe.calls, [])
        self.assertEqual(ownership.calls, [])


if __name__ == "__main__":
    unittest.main()
