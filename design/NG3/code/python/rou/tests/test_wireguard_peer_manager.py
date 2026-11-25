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
    ManagedWireGuardPeerConfig,
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
SHARED = IPv4Network("10.77.0.0/24")


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


def config(peers=(A, B, C), shared=(SHARED,)):
    return ManagedWireGuardConfig(
        kind=ManagedVpnKind.WIREGUARD,
        interface="wg0",
        address=IPv4Interface("10.200.0.1/32"),
        private_key_file="/run/private.key",
        listen_port=None,
        peers=tuple(peers),
        shared_prefixes=tuple(shared),
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


class WireGuardPeerManagerTests(unittest.TestCase):
    def test_initial_selection_uses_first_confirmed_suitable_peer(self):
        manager = WireGuardPeerManager()
        probe = Probe({"a": [no_reply()], "b": [reply()]})
        ownership = Ownership()

        result = manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=probe,
            ownership=ownership,
        )

        self.assertTrue(result.ready)
        self.assertEqual(result.selected_peer_id, "b")
        self.assertIsNotNone(result.generation)
        self.assertEqual([item[1] for item in probe.calls], ["a", "b"])
        desired = ownership.calls[-1]
        by_key = {item.public_key: item.allowed_ips for item in desired.peers}
        self.assertNotIn(SHARED, by_key[A.public_key])
        self.assertIn(SHARED, by_key[B.public_key])

    def test_current_reply_is_sticky_and_does_not_probe_preferred_peer(self):
        manager = WireGuardPeerManager()
        manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [no_reply()], "b": [reply()]}),
            ownership=Ownership(),
        )
        first = manager.current_state()
        self.assertEqual(first.selected_peer_id, "b")

        probe = Probe({"b": [reply()]})
        result = manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=probe,
            ownership=Ownership(),
        )

        self.assertEqual(result.selected_peer_id, "b")
        self.assertEqual(result.generation, first.generation)
        self.assertEqual([item[1] for item in probe.calls], ["b"])

    def test_current_no_reply_fails_over_to_best_confirmed_suitable_peer(self):
        manager = WireGuardPeerManager()
        manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [no_reply()], "b": [reply()]}),
            ownership=Ownership(),
        )
        old_generation = manager.current_state().generation

        result = manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"b": [no_reply()], "a": [reply()]}),
            ownership=Ownership(),
        )

        self.assertEqual(result.selected_peer_id, "a")
        self.assertNotEqual(result.generation, old_generation)

    def test_current_local_error_blocks_switch_and_invalidates_current_generation(self):
        manager = WireGuardPeerManager()
        manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(),
        )
        ownership = Ownership()

        result = manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [local_error("probe failed")]}),
            ownership=ownership,
        )

        self.assertFalse(result.ready)
        self.assertIsNone(result.selected_peer_id)
        self.assertIsNone(result.generation)
        self.assertIn("unconfirmed", result.problem)
        self.assertEqual(ownership.calls, [])
        self.assertIsNone(manager.current_state())

    def test_no_confirmed_suitable_peer_converges_exact_no_owner_state(self):
        manager = WireGuardPeerManager()
        ownership = Ownership()
        result = manager.reconcile(
            "wg",
            config(peers=(A, B)),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [no_reply()], "b": [no_reply()]}),
            ownership=ownership,
        )

        self.assertFalse(result.ready)
        self.assertIsNone(result.selected_peer_id)
        self.assertIsNotNone(result.generation)
        self.assertIsNone(result.problem)
        self.assertTrue(
            all(
                SHARED not in peer.allowed_ips
                for peer in ownership.calls[-1].peers
            )
        )

    def test_d003_failure_does_not_publish_new_generation(self):
        manager = WireGuardPeerManager()
        result = manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(confirmed=False, diagnostic="apply mismatch"),
        )

        self.assertIsNone(result.selected_peer_id)
        self.assertIsNone(result.generation)
        self.assertIn("apply mismatch", result.problem)
        self.assertIsNone(manager.current_state())

    def test_peer_order_change_is_new_context_and_reselects_from_new_order(self):
        manager = WireGuardPeerManager()
        first = manager.reconcile(
            "wg",
            config(peers=(A, B)),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(),
        )
        self.assertEqual(first.selected_peer_id, "a")

        second = manager.reconcile(
            "wg",
            config(peers=(B, A)),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"b": [reply()]}),
            ownership=Ownership(),
        )
        self.assertEqual(second.selected_peer_id, "b")
        self.assertNotEqual(second.generation, first.generation)

    def test_duplicate_peer_identity_is_rejected_before_probe_or_mutation(self):
        duplicate = ManagedWireGuardPeerConfig(
            peer_id="a",
            public_key="other-key",
            endpoint_address=IPv4Address("198.51.100.11"),
            endpoint_port=51820,
            probe_target=IPv4Address("10.201.0.9"),
        )
        probe = Probe({"a": [reply()]})
        ownership = Ownership()
        with self.assertRaisesRegex(ValueError, "peer IDs must be unique"):
            WireGuardPeerManager().reconcile(
                "wg",
                config(peers=(A, duplicate)),
                base_generation="base-a",
                path_route=ROUTE,
                probe=probe,
                ownership=ownership,
            )
        self.assertEqual(probe.calls, [])
        self.assertEqual(ownership.calls, [])

    def test_base_or_interface_generation_change_changes_peer_generation(self):
        manager = WireGuardPeerManager()
        first = manager.reconcile(
            "wg",
            config(),
            base_generation="base-a",
            path_route=ROUTE,
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(),
        )
        second = manager.reconcile(
            "wg",
            config(),
            base_generation="base-b",
            path_route=RoutePriorityPathRoute(
                PATH,
                InterfaceIdentity("wg0", 18),
            ),
            probe=Probe({"a": [reply()]}),
            ownership=Ownership(),
        )
        self.assertNotEqual(second.generation, first.generation)
        self.assertEqual(second.interface_ifindex, 18)


if __name__ == "__main__":
    unittest.main()
