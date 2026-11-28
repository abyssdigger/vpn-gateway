"""Focused #40 runtime admission evidence; no reclaim activation."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from ipaddress import IPv4Address
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from rou.accepted_effective_state import AcceptedEffectiveState, observe_pre_reclaim
from rou.alpha_runtime import (
    AlphaPostReleaseResult, AlphaPreparedPolicy, ManagedDeviceReleaseOutcome,
    complete_alpha_normal_reconciliation, observe_alpha_pre_reclaim,
    publish_alpha_accepted_effective,
)
from rou.binding import LogicalPathId, PathBinding, project_device_bindings
from rou.confirmed_current_use import CurrentUseState
from rou.interface_identity import InterfaceIdentity
from rou.managed_device_manager import ManagedDeviceManager
from rou.managed_wireguard_adapter import ManagedWireGuardObservation, ManagedWireGuardState
from rou.payload_profile import PayloadProfileRequest
from rou.wireguard_peer_manager import WireGuardGroupOwnershipRecord, WireGuardPeerRealization


CONFIG = """
[device.ext]
enabled = true
expected_interfaces = ["ext*/2"]
use_outbound_nat = true
[device.a]
enabled = true
use_outbound_nat = true
[device.a.managed_vpn]
kind = "wireguard"
interface = "wg1"
address = "10.200.0.1/32"
private_key_file = "/secret/a.key"
[[device.a.managed_vpn.peers]]
id = "peer"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.1:51820"
probe_target = "10.201.0.1"
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.77.0.0/24"]
device_order = ["ext", "a"]
warm_paths = 1
[profile.other]
enabled = true
direction = "outbound"
destinations = ["10.78.0.0/24"]
device_order = ["ext"]
warm_paths = 1
[profile.z]
enabled = true
direction = "outbound"
destinations = ["10.79.0.0/24"]
device_order = ["ext", "a:reserve"]
warm_paths = 1
"""


def binding(device, name, index):
    return PathBinding(LogicalPathId(device, 0, 0), InterfaceIdentity(name, index))


EXT = binding("ext", "ext0", 10)
A = binding("a", "wg1", 11)
PRESENT = ManagedWireGuardObservation("a", ManagedWireGuardState.PRESENT,
                                     A.endpoint, "base-a")
ABSENT = ManagedWireGuardObservation("a", ManagedWireGuardState.ABSENT)


def request(cfg, p, *bindings):
    intent = cfg.structural.profiles[p]
    return PayloadProfileRequest(p, intent.direction, intent.destinations,
                                 tuple(b.path_id for b in bindings))


def peer():
    return WireGuardPeerRealization(
        "a", "base-a", "wg1", 11,
        (WireGuardGroupOwnershipRecord("corp", "peer"),
         WireGuardGroupOwnershipRecord("z", "peer")),
        "wg-a",
    )


def states(evidence):
    return {r.profile_id: r.state for r in evidence.current_use}


def availability(profiles, confirmed=True, priority=True):
    return SimpleNamespace(
        confirmed=confirmed, priority=SimpleNamespace(confirmed=priority),
        observation=SimpleNamespace(projection=SimpleNamespace(effective_profiles=profiles)),
    )


class AcceptedEffectiveStateTests(unittest.TestCase):
    def setUp(self):
        self.prepared = AlphaPreparedPolicy.from_text(
            CONFIG, local_address=IPv4Address("198.19.255.2"))
        self.cfg = self.prepared.current_config
        self.profiles = (
            request(self.cfg, "corp", A, EXT),
            request(self.cfg, "other", EXT),
            request(self.cfg, "z", A, EXT),
        )
        self.accepted = AcceptedEffectiveState(self.profiles, (A, EXT), (peer(),))
        self.lifecycle = Mock()
        self.lifecycle.observe.return_value = replace(PRESENT, confirmed_generation=None)
        self.lifecycle.desired_generation.return_value = "base-a"
        self.lifecycle.confirm_present.return_value = PRESENT
        self.manager = ManagedDeviceManager(self.lifecycle)

    def evidence(self, previous=None, bindings=(A, EXT)):
        return observe_pre_reclaim(self.cfg, previous, self.manager, lambda: bindings)

    def assert_read_only(self):
        self.lifecycle.converge_present.assert_not_called()
        self.lifecycle.converge_absent.assert_not_called()
        self.lifecycle.retire_exact.assert_not_called()
        self.assertEqual(self.manager._known_managed_ids, set())

    def test_surplus_managed_current_use_and_reserve_none(self):
        r = self.evidence(self.accepted)
        self.assertNotIn("a", r.demand.desired_device_ids)
        corp = next(x for x in r.demand.profiles if x.profile_id == "corp")
        self.assertEqual(corp.regular_present, 2)
        self.assertEqual(corp.external_ordinary_present, 1)
        self.assertEqual(corp.managed_ordinary_contributions[0].fresh_path_count, 1)
        self.assertEqual(states(r), {
            "corp": CurrentUseState.CONFIRMED,
            "other": CurrentUseState.CONFIRMED,
            "z": CurrentUseState.NONE,
        })
        self.assertEqual(r.managed_base_observations, (PRESENT,))
        self.assertEqual(r.expected_base_generations, (("a", "base-a"),))
        self.assert_read_only()

    def test_external_replacement_is_capacity_not_previous_use(self):
        for fresh in (binding("ext", "ext0", 99), binding("ext", "ext1", 10)):
            r = self.evidence(self.accepted, (A, fresh))
            other = next(x for x in r.demand.profiles if x.profile_id == "other")
            self.assertEqual(other.regular_present, 1)
            self.assertIs(states(r)["other"], CurrentUseState.UNKNOWN)
            self.assertIn(fresh, r.bindings)
        self.assert_read_only()

    def test_managed_replacement_or_generation_mismatch_is_local(self):
        new = binding("a", "wg1", 99)
        r = self.evidence(self.accepted, (new, EXT))
        self.assertIs(states(r)["corp"], CurrentUseState.UNKNOWN)
        self.assertIs(states(r)["other"], CurrentUseState.CONFIRMED)
        self.assertEqual(r.unconfirmed_devices, ("a",))
        self.assertEqual(r.managed_base_observations, ())
        self.lifecycle.desired_generation.return_value = "base-new"
        self.lifecycle.confirm_present.return_value = replace(PRESENT, confirmed_generation="base-new")
        r = self.evidence(self.accepted)
        self.assertIs(states(r)["corp"], CurrentUseState.UNKNOWN)
        self.assertIs(states(r)["other"], CurrentUseState.CONFIRMED)
        self.assert_read_only()

    def test_confirmation_failure_and_absence_are_distinct(self):
        self.lifecycle.confirm_present.side_effect = RuntimeError("mismatch")
        r = self.evidence(self.accepted)
        self.assertEqual(r.unconfirmed_devices, ("a",))
        self.assertEqual(r.managed_base_observations, ())
        self.assertIs(states(r)["corp"], CurrentUseState.UNKNOWN)
        self.assertIs(states(r)["other"], CurrentUseState.CONFIRMED)
        self.lifecycle.reset_mock()
        self.lifecycle.observe.return_value = ABSENT
        r = self.evidence(self.accepted, (EXT,))
        self.assertEqual(r.managed_base_observations, (ABSENT,))
        self.assertEqual(r.unconfirmed_devices, ())
        self.lifecycle.confirm_present.assert_not_called()
        self.lifecycle.desired_generation.assert_not_called()
        self.assertIs(states(r)["corp"], CurrentUseState.UNKNOWN)
        self.assert_read_only()

    def test_raw_binding_with_owned_absence_is_not_confirmed_absence(self):
        self.lifecycle.observe.return_value = ABSENT
        r = self.evidence(self.accepted)
        self.assertEqual(r.unconfirmed_devices, ("a",))
        self.assertEqual(r.managed_base_observations, ())
        self.assertIn(A, r.bindings)
        self.assertIs(states(r)["corp"], CurrentUseState.UNKNOWN)
        self.assertIs(states(r)["other"], CurrentUseState.CONFIRMED)
        self.assert_read_only()

    def test_observe_and_confirm_identity_must_match(self):
        self.lifecycle.confirm_present.return_value = replace(
            PRESENT, interface=InterfaceIdentity("wg1", 99))
        r = self.evidence(self.accepted)
        self.assertEqual(r.unconfirmed_devices, ("a",))
        self.assertIs(states(r)["corp"], CurrentUseState.UNKNOWN)
        self.assertIs(states(r)["other"], CurrentUseState.CONFIRMED)
        self.assert_read_only()

    def test_missing_d002_or_no_prior_generation(self):
        for prior in (replace(self.accepted, wireguard_peer_realizations=()),
                      replace(self.accepted, wireguard_peer_realizations=(
                          replace(peer(), generation=None, group_owners=(), problem="unconfirmed"),))):
            r = self.evidence(prior)
            self.assertIs(states(r)["corp"], CurrentUseState.UNKNOWN)
            self.assertIs(states(r)["other"], CurrentUseState.CONFIRMED)
        self.assertEqual(set(states(self.evidence()).values()), {CurrentUseState.UNKNOWN})
        self.assert_read_only()

    def test_failed_observation_is_not_empty_confirmed_inventory(self):
        r = observe_pre_reclaim(self.cfg, self.accepted, self.manager,
                               Mock(side_effect=RuntimeError("observe failed")))
        self.assertIsNone(r.demand)
        self.assertEqual(r.observation_problem, "RuntimeError")
        self.assertEqual(set(states(r).values()), {CurrentUseState.UNKNOWN})
        self.lifecycle.observe.assert_not_called()

    def test_alpha_observation_is_unfiltered_and_binding_state_is_not_committed(self):
        prepared = self.prepared
        # Model an already selected normal eligibility set that excludes a.
        prepared.confirmed_managed_interfaces = frozenset()
        full = (A.endpoint, EXT.endpoint)
        old_state = prepared.binding_state
        projection = project_device_bindings(
            prepared.config.structural.device_binding_intents, old_state, full)
        with patch("rou.alpha_runtime.LinuxVpnPathAdapter") as adapter:
            adapter.return_value.observe_interfaces.return_value.interfaces = full
            r = observe_alpha_pre_reclaim(
                prepared, SimpleNamespace(namespace="ns"), Mock(), self.manager, self.accepted)
        self.assertEqual(set(r.bindings), set(projection.bindings))
        self.assertIn(A, r.bindings)
        self.assertNotIn("a", r.demand.desired_device_ids)
        self.assertIs(prepared.binding_state, old_state)
        self.assertEqual(prepared.confirmed_managed_interfaces, frozenset())
        self.assert_read_only()

    def publish(self, profiles, *, payload=True, confirmed=True, priority=True,
                wireguard_error=None, wireguard=True):
        publish_alpha_accepted_effective(
            self.prepared, payload_confirmed=payload,
            availability=availability(profiles, confirmed, priority),
            wireguard=SimpleNamespace(realizations=(peer(),)) if wireguard else None,
            wireguard_error=wireguard_error,
        )

    def test_invalidation_and_successful_replacement(self):
        p = self.prepared
        p.last_bindings = (A, EXT)
        self.publish(self.profiles)
        g = p.accepted_effective_state
        self.assertEqual(g, self.accepted)
        with self.assertRaises(FrozenInstanceError):
            g.profiles = ()
        self.assertIs(p.begin_effective_transition(), g)
        self.assertIsNone(p.accepted_effective_state)
        # Tentative scratch can be rebuilt without becoming current evidence.
        p.last_profiles = (request(self.cfg, "corp", EXT),)
        p.last_bindings = (EXT,)
        self.publish(p.last_profiles, payload=False)
        self.assertIsNone(p.accepted_effective_state)
        self.assertIsNone(p.begin_effective_transition())
        self.assertEqual(set(states(self.evidence(p.accepted_effective_state)).values()),
                         {CurrentUseState.UNKNOWN})
        g2 = (request(self.cfg, "corp", EXT), request(self.cfg, "other", EXT),
              request(self.cfg, "z", EXT))
        self.publish(g2)
        self.assertEqual(p.accepted_effective_state.profiles, g2)
        self.assertEqual(p.accepted_effective_state.bindings, (EXT,))
        self.assertNotEqual(p.accepted_effective_state, g)

    def test_partial_confirmation_cannot_publish(self):
        p = self.prepared
        p.last_bindings = (A, EXT)
        for kwargs in ({"payload": False}, {"confirmed": False}, {"priority": False},
                       {"wireguard_error": "D.002 failed"}, {"wireguard": False}):
            self.publish(self.profiles)
            self.assertIsNotNone(p.begin_effective_transition())
            self.publish(self.profiles, **kwargs)
            self.assertIsNone(p.accepted_effective_state)

    def test_final_recovered_state_not_pre_release_scratch(self):
        p = self.prepared
        p.last_bindings = (A, EXT)
        self.publish(self.profiles)
        p.begin_effective_transition()
        p.last_profiles = self.profiles
        p.pre_reclaim_evidence = self.evidence(self.accepted)
        recovered_profiles = tuple(
            request(self.cfg, key, EXT) for key in ("corp", "other", "z"))
        initial_payload = SimpleNamespace(ready=True)
        initial_availability = availability(self.profiles)
        initial_wg = SimpleNamespace(realizations=(peer(),))
        convergence = SimpleNamespace(realizations=("initial",))
        ownership = Mock()
        domain, runner, coordinator, probe_driver = Mock(), Mock(), Mock(), Mock()

        def recover(*args):
            self.assertIsNone(p.accepted_effective_state)
            p.last_bindings = (EXT,)
            return AlphaPostReleaseResult(
                ("recovered",), SimpleNamespace(ready=True),
                availability(recovered_profiles),
                SimpleNamespace(realizations=()), None,
            )

        with patch("rou.alpha_runtime.release_alpha_undemanded_devices",
                   return_value=ManagedDeviceReleaseOutcome(("released",), True)) as release, \
             patch("rou.alpha_runtime.reconcile_alpha_after_managed_release",
                   side_effect=recover) as recovery:
            final = complete_alpha_normal_reconciliation(
                p, domain, runner, self.manager, convergence, coordinator,
                probe_driver, ownership, initial_payload, initial_availability,
                initial_wg, None)
        release.assert_called_once_with(
            p, domain, runner, self.manager, convergence, ownership,
            dependencies_confirmed=True)
        recovery.assert_called_once()
        self.assertEqual(final.realizations, ("recovered",))
        self.assertEqual(p.accepted_effective_state.profiles, recovered_profiles)
        self.assertEqual(p.accepted_effective_state.bindings, (EXT,))
        self.assertEqual(p.accepted_effective_state.wireguard_peer_realizations, ())
        self.assertNotEqual(p.accepted_effective_state.profiles, p.last_profiles)

    def test_failed_post_release_recovery_does_not_admit_old_generation(self):
        p = self.prepared
        p.last_bindings = (A, EXT)
        self.publish(self.profiles)
        p.begin_effective_transition()
        failed = AlphaPostReleaseResult(
            (), SimpleNamespace(ready=False), None, None, "recovery failed")
        with patch("rou.alpha_runtime.release_alpha_undemanded_devices",
                   return_value=ManagedDeviceReleaseOutcome((), True)), \
             patch("rou.alpha_runtime.reconcile_alpha_after_managed_release",
                   return_value=failed):
            final = complete_alpha_normal_reconciliation(
                p, Mock(), Mock(), self.manager, SimpleNamespace(realizations=()),
                Mock(), Mock(), Mock(), SimpleNamespace(ready=True),
                availability(self.profiles), SimpleNamespace(realizations=(peer(),)), None)
        self.assertIs(final, failed)
        self.assertIsNone(p.accepted_effective_state)


if __name__ == "__main__":
    unittest.main()
