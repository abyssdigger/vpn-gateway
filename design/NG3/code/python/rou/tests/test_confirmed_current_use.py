from __future__ import annotations

from dataclasses import replace
from ipaddress import IPv4Network
import unittest

from rou.binding import LogicalPathId, PathBinding
from rou.confirmed_current_use import (
    ConfirmedCurrentUse, ConfirmedEffectiveUseContext, CurrentUseState,
    project_confirmed_current_use,
)
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.managed_wireguard_adapter import ManagedWireGuardObservation, ManagedWireGuardState
from rou.payload_profile import PayloadProfileRequest
from rou.release1_config import parse_current_config
from rou.wireguard_peer_manager import WireGuardGroupOwnershipRecord, WireGuardPeerRealization


KEY = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="


def managed(device_id, index):
    return f"""
[device.{device_id}]
enabled = true
use_outbound_nat = true
[device.{device_id}.managed_vpn]
kind = "wireguard"
interface = "wg{index}"
address = "10.200.0.{index}/32"
private_key_file = "/secret/{device_id}.key"
[[device.{device_id}.managed_vpn.peers]]
id = "peer"
public_key = "{KEY}"
endpoint = "198.51.100.{index}:51820"
probe_target = "10.201.0.{index}"
"""


DEVICES = managed("a", 1) + managed("r", 2) + """
[device.ext]
enabled = true
expected_interfaces = ["ext*/2"]
use_outbound_nat = true
[device.single]
enabled = true
expected_interfaces = ["single0"]
use_outbound_nat = true
[device.disabled]
enabled = false
[profile.off]
enabled = false
"""


def profile(key, order, network, direction="outbound"):
    return f"""
[profile.{key}]
enabled = true
direction = "{direction}"
destinations = ["{network}"]
device_order = [{", ".join(f'"{d}"' for d in order)}]
"""


def config():
    # The same managed Device is ordinary for one Profile and reserve for another.
    return parse_current_config(
        DEVICES
        + profile("z", ("a:reserve", "ext"), "10.79.0.0/24")
        + profile("corp", ("ext", "a", "r:reserve", "disabled"), "10.77.0.0/24")
        + profile("other", ("a",), "10.78.0.0/24")
    )


def binding(device, name, ifindex, slot=0, selector=0):
    return PathBinding(LogicalPathId(device, selector, slot), InterfaceIdentity(name, ifindex))


EXT = binding("ext", "ext0", 10)
A = binding("a", "wg1", 11)
R = binding("r", "wg2", 12)
SINGLE = binding("single", "single0", 13)


def request(cfg, key, *paths):
    intent = cfg.structural.profiles[key]
    return PayloadProfileRequest(
        key, intent.direction, intent.destinations, tuple(row.path_id for row in paths)
    )


def base(row, generation="base-a"):
    return ManagedWireGuardObservation(
        row.path_id.device_id, ManagedWireGuardState.PRESENT, row.endpoint, generation
    )


def wg(row, groups, generation="wg-a", base_generation="base-a"):
    return WireGuardPeerRealization(
        row.path_id.device_id, base_generation, row.endpoint.ifname, row.endpoint.ifindex,
        tuple(WireGuardGroupOwnershipRecord(key, peer) for key, peer in groups),
        generation,
    )


def context(cfg, **kwargs):
    values = dict(
        profiles=(
            request(cfg, "z", A, EXT), request(cfg, "corp", EXT, A, R),
            request(cfg, "other", A),
        ),
        bindings=(EXT, A, R),
        expected_base_generations={"a": "base-a"},
        managed_base_observations=(base(A),),
        wireguard_peer_realizations=(wg(A, (("corp", "peer"), ("other", "peer"), ("z", "peer"))),),
    )
    values.update(kwargs)
    return ConfirmedEffectiveUseContext(**values)


class ConfirmedCurrentUseTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.ctx = context(self.cfg)

    def result(self, ctx):
        return project_confirmed_current_use(self.cfg, ctx)

    def states(self, ctx):
        return tuple(row.state for row in self.result(ctx))

    def test_missing_context_and_valid_empty_are_distinct(self):
        self.assertEqual(tuple(row.profile_id for row in self.result(None)),
                         ("corp", "other", "z"))
        self.assertEqual(self.states(None), (CurrentUseState.UNKNOWN,) * 3)
        empty = replace(self.ctx, profiles=tuple(
            request(self.cfg, key) for key in ("z", "other", "corp")
        ))
        self.assertEqual(self.states(empty), (CurrentUseState.NONE,) * 3)
        self.assertTrue(all(row.path_id is None and row.endpoint is None
                            for row in self.result(empty)))

    def test_external_first_managed_first_and_managed_reserve(self):
        self.assertEqual(self.result(self.ctx), (
            ConfirmedCurrentUse("corp", CurrentUseState.CONFIRMED, EXT.path_id, EXT.endpoint),
            ConfirmedCurrentUse("other", CurrentUseState.CONFIRMED, A.path_id, A.endpoint,
                                "base-a", "wg-a", "peer"),
            ConfirmedCurrentUse("z", CurrentUseState.NONE),
        ))
        # Effective order may differ from baseline, including a confirmed fallback
        # when every path is problematic. No availability evidence is consulted.
        effective = replace(self.ctx, profiles=(
            request(self.cfg, "corp", A, EXT), self.ctx.profiles[0], self.ctx.profiles[2]
        ))
        self.assertEqual(self.result(effective)[0], ConfirmedCurrentUse(
            "corp", CurrentUseState.CONFIRMED, A.path_id, A.endpoint,
            "base-a", "wg-a", "peer",
        ))
        self.assertEqual(self.result(replace(effective, profiles=tuple(reversed(effective.profiles)))),
                         self.result(effective))

    def test_missing_duplicate_or_mismatched_profile_is_local(self):
        z, corp, other = self.ctx.profiles
        for profiles in (
            (z, other), (z, corp, corp, other),
            (z, replace(corp, direction=Direction.INBOUND), other),
            (z, replace(corp, destinations=(IPv4Network("10.1.0.0/24"),)), other),
        ):
            with self.subTest(profiles=profiles):
                self.assertEqual(self.states(replace(self.ctx, profiles=profiles)), (
                    CurrentUseState.UNKNOWN, CurrentUseState.CONFIRMED, CurrentUseState.NONE,
                ))
        foreign = replace(corp, profile_id="foreign")
        self.assertEqual(self.states(replace(self.ctx, profiles=(*self.ctx.profiles, foreign))),
                         (CurrentUseState.UNKNOWN,) * 3)

    def test_invalid_path_membership_slot_selector_or_duplicate(self):
        z, corp, other = self.ctx.profiles
        for bad in (
            SINGLE, binding("disabled", "disabled0", 40),
            binding("ext", "ext0", 40, slot=2),
            binding("ext", "ext0", 40, selector=1),
            binding("ext", "wrong0", 40, slot=1),
        ):
            with self.subTest(path=bad):
                bindings = tuple(row for row in self.ctx.bindings
                                 if row.endpoint.ifname != bad.endpoint.ifname) + (bad,)
                rows = (z, request(self.cfg, "corp", bad), other)
                self.assertIs(self.result(replace(self.ctx, bindings=bindings, profiles=rows))[0].state,
                              CurrentUseState.UNKNOWN)
        for paths in ((EXT, EXT), (EXT, binding("ext", "ext1", 40, slot=1))):
            with self.subTest(paths=paths):
                self.assertIs(self.result(replace(self.ctx, profiles=(z, request(
                    self.cfg, "corp", *paths), other)))[0].state, CurrentUseState.UNKNOWN)

    def test_exact_duplicate_binding_is_not_arbitrarily_selected(self):
        # A duplicate row is localizable, but every dependent request is invalid.
        result = self.result(replace(self.ctx, bindings=(*self.ctx.bindings, A)))
        self.assertEqual(tuple(row.state for row in result), (CurrentUseState.UNKNOWN,) * 3)
        result = self.result(replace(self.ctx, bindings=(*self.ctx.bindings, R)))
        self.assertEqual(tuple(row.state for row in result), (
            CurrentUseState.UNKNOWN, CurrentUseState.CONFIRMED, CurrentUseState.NONE,
        ))

    def test_global_conflicting_identity_invalidates_every_profile(self):
        for bad in (
            binding("a", "wg1", 100),
            binding("ext", "wg1", 11, slot=1),
            binding("ext", "wg1", 100, slot=1),
            binding("ext", "ext1", 11, slot=1),
            binding("foreign", "unknown0", 90),
        ):
            with self.subTest(row=bad):
                self.assertEqual(self.states(replace(self.ctx, bindings=(*self.ctx.bindings, bad))),
                                 (CurrentUseState.UNKNOWN,) * 3)

    def test_selected_base_gap_invalidates_both_dependent_profiles_only(self):
        for observations, expected in (
            ((), {"a": "base-a"}),
            ((base(A), base(A)), {"a": "base-a"}),
            ((ManagedWireGuardObservation("a", ManagedWireGuardState.ABSENT),), {"a": "base-a"}),
            ((ManagedWireGuardObservation("a", ManagedWireGuardState.PRESENT, A.endpoint),), {"a": "base-a"}),
            ((base(binding("a", "wg1", 99)),), {"a": "base-a"}),
            ((base(A, "stale"),), {"a": "base-a"}),
            ((base(A),), {}), ((base(A),), {"a": ""}),
        ):
            with self.subTest(observations=observations, expected=expected):
                result = self.result(replace(
                    self.ctx, managed_base_observations=observations, expected_base_generations=expected
                ))
                self.assertEqual(tuple(row.state for row in result), (
                    CurrentUseState.CONFIRMED, CurrentUseState.UNKNOWN, CurrentUseState.UNKNOWN,
                ))
                for row in result[1:]:
                    self.assertEqual(row, ConfirmedCurrentUse(row.profile_id, CurrentUseState.UNKNOWN))

    def test_selected_wireguard_gap_including_reserve(self):
        owners = (("other", "peer"), ("z", "peer"))
        for rows in (
            (), (wg(A, owners), wg(A, owners)),
            (replace(wg(A, owners), group_owners=(), generation=None, problem="failed"),),
            (wg(A, owners, generation=""),),
            (wg(A, owners, base_generation="stale"),),
            (wg(binding("a", "wg1", 99), owners),),
            (wg(binding("a", "wrong0", 11), owners),),
            (wg(A, (("corp", "peer"),)),),
            (wg(A, (("other", None), ("z", None))),),
            (wg(A, (("other", "foreign"), ("z", "foreign"))),),
        ):
            with self.subTest(rows=rows):
                self.assertEqual(self.states(replace(self.ctx, wireguard_peer_realizations=rows)), (
                    CurrentUseState.CONFIRMED, CurrentUseState.UNKNOWN, CurrentUseState.UNKNOWN,
                ))

    def test_exact_group_evidence_is_profile_local(self):
        peer = wg(A, (("other", "peer"),))
        self.assertEqual(self.states(replace(self.ctx, wireguard_peer_realizations=(peer,))), (
            CurrentUseState.CONFIRMED, CurrentUseState.CONFIRMED, CurrentUseState.UNKNOWN,
        ))
        groups = {key: value for key, value in self.cfg.wireguard_groups.items() if key != ("other", "a")}
        cfg = replace(self.cfg, wireguard_groups=groups)
        result = project_confirmed_current_use(cfg, self.ctx)
        self.assertEqual(tuple(row.state for row in result), (
            CurrentUseState.CONFIRMED, CurrentUseState.UNKNOWN, CurrentUseState.NONE,
        ))
        changed = replace(self.ctx, wireguard_peer_realizations=(
            wg(A, (("other", "peer"), ("z", "peer")), generation="wg-next"),
        ))
        self.assertEqual(self.result(changed)[1].wireguard_generation, "wg-next")
        self.assertEqual(self.result(self.ctx)[1].wireguard_generation, "wg-a")

    def test_external_reserve_positive_none_requires_binding(self):
        cfg = parse_current_config(DEVICES + profile("corp", ("ext:reserve",), "10.77.0.0/24"))
        ctx = ConfirmedEffectiveUseContext((request(cfg, "corp", EXT),), (EXT,), {}, (), ())
        self.assertEqual(project_confirmed_current_use(cfg, ctx),
                         (ConfirmedCurrentUse("corp", CurrentUseState.NONE),))
        self.assertEqual(project_confirmed_current_use(cfg, replace(ctx, bindings=())),
                         (ConfirmedCurrentUse("corp", CurrentUseState.UNKNOWN),))

    def test_inbound_and_bidirectional_zero_single_multiple(self):
        for direction in ("inbound", "bidirectional"):
            with self.subTest(direction=direction):
                cfg = parse_current_config(DEVICES + profile("corp", ("single",),
                                            "10.77.0.0/24", direction))
                ctx = ConfirmedEffectiveUseContext((request(cfg, "corp", SINGLE),),
                                                    (SINGLE,), {}, (), ())
                self.assertEqual(project_confirmed_current_use(cfg, ctx), (
                    ConfirmedCurrentUse("corp", CurrentUseState.CONFIRMED,
                                        SINGLE.path_id, SINGLE.endpoint),
                ))
                self.assertEqual(project_confirmed_current_use(cfg, replace(ctx, profiles=(
                    request(cfg, "corp"),))), (ConfirmedCurrentUse("corp", CurrentUseState.NONE),))
                self.assertEqual(project_confirmed_current_use(cfg, replace(ctx, profiles=(
                    request(cfg, "corp", SINGLE, SINGLE),))), (
                        ConfirmedCurrentUse("corp", CurrentUseState.UNKNOWN),
                    ))

    def test_context_defensively_copies_inputs(self):
        generations = {"a": "base-a"}
        requests = list(self.ctx.profiles)
        ctx = replace(self.ctx, profiles=requests, expected_base_generations=generations)
        before = self.result(ctx)
        generations["a"] = "stale"
        requests.clear()
        self.assertEqual(self.result(ctx), before)
        with self.assertRaises(TypeError):
            ctx.expected_base_generations["a"] = "changed"
        self.assertEqual(self.ctx.expected_base_generations, {"a": "base-a"})
        self.assertEqual(self.result(self.ctx), before)


if __name__ == "__main__":
    unittest.main()
