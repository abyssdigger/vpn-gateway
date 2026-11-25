from __future__ import annotations

import unittest

from rou.binding import LogicalPathId, PathBinding
from rou.interface_identity import InterfaceIdentity
from rou.managed_device_demand import project_final, project_regular
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


if __name__ == "__main__":
    unittest.main()
