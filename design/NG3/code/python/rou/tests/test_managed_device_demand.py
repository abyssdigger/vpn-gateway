from __future__ import annotations

import unittest

from rou.binding import LogicalPathId, PathBinding
from rou.interface_identity import InterfaceIdentity
from rou.managed_device_demand import project_final, project_regular
from rou.managed_device_manager import (
    ManagedDeviceDesiredState,
    ManagedDeviceManager,
    converge_managed_device_presence,
)
from rou.managed_wireguard_adapter import ManagedWireGuardObservation, ManagedWireGuardState
from rou.release1_config import (
    CurrentConfigError,
    Release1ConfigError,
    parse_current_config,
    parse_release1_config,
)


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


def profile(profile_id, order, warm=None, network="10.77.0.0/24"):
    return f"""
[profile.{profile_id}]
enabled = true
direction = "outbound"
destinations = ["{network}"]
device_order = [{", ".join(f'"{d}"' for d in order)}]
""" + (f"warm_paths = {warm}\n" if warm is not None else "")


DEVICES = (
    managed("a", 1) + managed("b", 2) + managed("r", 3)
    + """
[device.ext]
enabled = true
expected_interfaces = ["ext*/3"]
use_outbound_nat = true
[device.disabled]
enabled = false
"""
)


def config(order, warm=None):
    return parse_current_config(DEVICES + profile("corp", order, warm))


def presence(device_id, slot=0):
    return PathBinding(
        LogicalPathId(device_id, 0, slot),
        InterfaceIdentity(f"{device_id}{slot}", slot + 1),
    )


class WarmPathConfigTests(unittest.TestCase):
    def test_current_only_grammar_and_capacity(self):
        for raw, value, target in (
            (None, "all", 4), ('"all"', "all", 4), ("0", 0, 0), ("2", 2, 2)
        ):
            with self.subTest(raw=raw):
                parsed = config(("a", "ext", "r:reserve", "disabled"), raw)
                self.assertEqual(parsed.warm_paths["corp"], value)
                self.assertEqual(parsed.warm_target("corp"), target)
        for raw in ("5", "-1", "true", "1.0", '"2"', '"ALL"', "[]"):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(CurrentConfigError, "warm_paths"):
                    config(("a", "ext", "r:reserve", "disabled"), raw)
        external = """
[device.ext]
enabled = true
expected_interfaces = ["ext0"]
use_outbound_nat = true
"""
        with self.assertRaisesRegex(Release1ConfigError, "warm_paths"):
            parse_release1_config(external + profile("corp", ("ext",), "1"))

    def test_disabled_profile_is_shallow_and_reserve_only_all_is_zero(self):
        parsed = parse_current_config(
            DEVICES + '[profile.off]\nenabled = false\nwarm_paths = true\n'
            + profile("corp", ("r:reserve",))
        )
        self.assertNotIn("off", parsed.warm_paths)
        self.assertEqual(parsed.warm_target("corp"), 0)
        self.assertEqual(project_final(parsed, ()).desired_device_ids, frozenset())


class ManagedDeviceDemandTests(unittest.TestCase):
    def test_numeric_target_does_not_wake_higher_priority_device(self):
        cfg = config(("a", "b"), "1")
        self.assertEqual(
            project_regular(cfg, (presence("b"),)).desired_device_ids, {"b"}
        )

    def test_external_presence_prevents_unnecessary_managed_demand(self):
        cfg = config(("a", "ext", "b"), "2")
        result = project_regular(cfg, (presence("ext", 0), presence("ext", 1)))
        self.assertEqual(result.desired_device_ids, set())
        self.assertEqual(result.profiles[0].regular_deficit, 0)

    def test_minimal_baseline_demand_retains_present_paths(self):
        cfg = config(("a", "b", "ext"), "2")
        self.assertEqual(
            project_regular(cfg, ()).desired_device_ids, {"a", "b"}
        )
        self.assertEqual(
            project_regular(cfg, (presence("b"), presence("ext"))).desired_device_ids,
            {"b"},
        )
        self.assertEqual(
            project_regular(cfg, (presence("a"), presence("b"), presence("ext"))).desired_device_ids,
            {"a"},
        )

    def test_all_and_zero(self):
        for raw, expected in ((None, {"a", "b"}), ("0", set())):
            with self.subTest(raw=raw):
                cfg = config(("a", "b", "ext", "r:reserve"), raw)
                result = project_regular(cfg, (presence("ext"),))
                self.assertEqual(result.desired_device_ids, expected)
                if raw == "0":
                    self.assertEqual(project_final(cfg, ()).desired_device_ids, set())

    def test_reserve_exception_does_not_hide_regular_deficit(self):
        cfg = config(("a", "r:reserve"), "1")
        self.assertEqual(project_regular(cfg, ()).desired_device_ids, {"a"})
        self.assertEqual(project_final(cfg, ()).desired_device_ids, {"a", "r"})
        reserve_present = project_final(cfg, (presence("r"),))
        self.assertEqual(reserve_present.profiles[0].regular_deficit, 1)
        self.assertEqual(reserve_present.desired_device_ids, {"a", "r"})
        recovered = project_final(cfg, (presence("a"), presence("r")))
        self.assertEqual(recovered.profiles[0].regular_deficit, 0)
        self.assertEqual(recovered.desired_device_ids, {"a"})

    def test_shared_device_aggregates_profile_local_roles(self):
        cfg = parse_current_config(
            DEVICES + profile("corp", ("a", "r:reserve"), "1")
            + profile("other", ("r",), "1", "10.78.0.0/24")
        )
        result = project_final(cfg, (presence("a"), presence("r")))
        self.assertEqual(result.desired_device_ids, {"a", "r"})
        self.assertEqual(result.profiles[0].reserve_device_ids, ())
        self.assertEqual(result.profiles[1].ordinary_device_ids, ("r",))

    def test_reserve_external_support_is_not_actuated(self):
        cfg = config(("a", "ext:reserve", "r:reserve"), "1")
        result = project_final(cfg, (presence("ext"),))
        self.assertEqual(result.profiles[0].regular_deficit, 1)
        self.assertEqual(result.desired_device_ids, {"a"})


class FakePresenceLifecycle:
    def __init__(self):
        self.paths = {}
        self.fail = set()
        self.actions = []

    def desired_generation(self, device_id, desired):
        return "gen-" + device_id

    def converge_present(self, device_id, desired):
        self.actions.append(("present", device_id))
        if device_id in self.fail:
            raise RuntimeError("failed " + device_id)
        endpoint = InterfaceIdentity(desired.interface, len(self.actions) + 20)
        self.paths[device_id] = PathBinding(LogicalPathId(device_id, 0, 0), endpoint)
        return ManagedWireGuardObservation(
            device_id, ManagedWireGuardState.PRESENT, endpoint, "gen-" + device_id
        )

    def observe(self, device_id):
        path = self.paths.get(device_id)
        return ManagedWireGuardObservation(
            device_id,
            ManagedWireGuardState.PRESENT if path else ManagedWireGuardState.ABSENT,
            path.endpoint if path else None,
        )

    def converge_absent(self, device_id):
        self.actions.append(("absent", device_id))
        self.paths.pop(device_id, None)
        return self.observe(device_id)

    def fresh(self):
        return tuple(self.paths.values())


class BoundedConvergenceTests(unittest.TestCase):
    def test_failed_ordinary_tries_next_before_reserve(self):
        cfg = config(("a", "b", "r:reserve"), "1")
        lifecycle = FakePresenceLifecycle()
        lifecycle.fail.add("a")
        result = converge_managed_device_presence(
            cfg, ManagedDeviceManager(lifecycle), lifecycle.fresh
        )
        self.assertEqual(lifecycle.actions, [("present", "a"), ("present", "b")])
        self.assertEqual(result.projection.desired_device_ids, {"b"})
        self.assertEqual(tuple(x.device_id for x in result.attempt_problems), ("a",))

    def test_reserve_recovery_requires_explicit_dependency_release(self):
        cfg = config(("a", "r:reserve"), "1")
        lifecycle = FakePresenceLifecycle()
        lifecycle.fail.add("a")
        manager = ManagedDeviceManager(lifecycle)
        failed = converge_managed_device_presence(cfg, manager, lifecycle.fresh)
        self.assertEqual(lifecycle.actions, [("present", "a"), ("present", "r")])
        self.assertEqual(failed.projection.desired_device_ids, {"a", "r"})
        self.assertEqual(failed.projection.profiles[0].regular_deficit, 1)
        lifecycle.fail.clear()
        lifecycle.actions.clear()
        recovered = converge_managed_device_presence(cfg, manager, lifecycle.fresh)
        self.assertEqual(lifecycle.actions, [("present", "a")])
        self.assertEqual(recovered.projection.desired_device_ids, {"a"})
        waiting = next(x for x in recovered.realizations if x.device_id == "r")
        self.assertTrue(waiting.waiting_for_dependencies)
        self.assertIn("r", lifecycle.paths)
        released = manager.reconcile_undemanded(
            cfg, desired_device_ids=frozenset({"a"}),
            dependency_free_device_ids=frozenset({"r"}),
        )
        self.assertIs(next(x for x in released if x.device_id == "r").confirmed_state,
                      ManagedWireGuardState.ABSENT)
        self.assertEqual(lifecycle.actions[-1], ("absent", "r"))

    def test_failed_start_with_matching_endpoint_does_not_hide_deficit(self):
        cfg = config(("a", "r:reserve"), "1")
        lifecycle = FakePresenceLifecycle()
        lifecycle.paths["a"] = presence("a")
        lifecycle.fail.add("a")
        result = converge_managed_device_presence(
            cfg, ManagedDeviceManager(lifecycle), lifecycle.fresh
        )
        self.assertEqual(result.projection.profiles[0].regular_deficit, 1)
        self.assertEqual(result.projection.desired_device_ids, {"a", "r"})
        self.assertNotIn(lifecycle.paths["a"].endpoint, result.confirmed_interfaces)

    def test_shared_demand_preserves_reserve_owned_by_another_profile(self):
        cfg = parse_current_config(
            DEVICES + profile("corp", ("a", "r:reserve"), "1")
            + profile("other", ("r",), "1", "10.78.0.0/24")
        )
        lifecycle = FakePresenceLifecycle()
        result = converge_managed_device_presence(
            cfg, ManagedDeviceManager(lifecycle), lifecycle.fresh
        )
        self.assertEqual(result.projection.desired_device_ids, {"a", "r"})
        self.assertEqual(lifecycle.actions, [("present", "a"), ("present", "r")])
        self.assertTrue(all(
            x.desired_state is ManagedDeviceDesiredState.PRESENT
            for x in result.realizations if x.device_id in {"a", "r"}
        ))


if __name__ == "__main__":
    unittest.main()
