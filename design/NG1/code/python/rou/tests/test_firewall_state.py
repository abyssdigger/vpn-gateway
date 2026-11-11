import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import ActiveConfig, Availability, Device, Direction, Profile
from rou.firewall_state import compile_filter_state


class FirewallStateTests(unittest.TestCase):
    def test_filter_is_default_drop_and_scoped_to_bound_interfaces(self):
        config = ActiveConfig(
            devices={"oc": Device("oc", True)},
            profiles={
                "corp": Profile(
                    "corp",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc",),
                )
            },
        )
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns00", 10),
                    Availability.UNKNOWN,
                ),
            ),
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns01", 11),
                    Availability.UNKNOWN,
                ),
            ),
        )

        state = compile_filter_state(config, bindings)

        self.assertIn(":FORWARD DROP [0:0]", state.restore_text)
        self.assertIn(
            "-A FORWARD -m conntrack --ctstate INVALID -j DROP",
            state.restore_text,
        )
        self.assertIn(
            "-A FORWARD -i host0 -o vpns00 -m conntrack "
            "--ctstate ESTABLISHED,RELATED -j ACCEPT",
            state.restore_text,
        )
        self.assertIn(
            "-A FORWARD -i host0 -o vpns00 -d 10.0.0.0/8 "
            "-m conntrack --ctstate NEW -j ACCEPT",
            state.restore_text,
        )
        self.assertIn(
            "-A FORWARD -i vpns00 -o host0 -s 10.0.0.0/8 "
            "-m conntrack --ctstate NEW -j DROP",
            state.restore_text,
        )
        self.assertNotIn("vpns01", state.restore_text)

    def test_specific_drop_precedes_broad_accept_after_interface_expansion(self):
        config = ActiveConfig(
            devices={"oc": Device("oc", True)},
            profiles={
                "specific": Profile(
                    "specific",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.20.0.0/16"),),
                    ("oc",),
                ),
                "broad": Profile(
                    "broad",
                    True,
                    Direction.BIDIRECTIONAL,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc",),
                ),
            },
        )
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns00", 10),
                    Availability.UNKNOWN,
                ),
            ),
            (),
        )

        lines = compile_filter_state(config, bindings).restore_text.splitlines()
        specific = lines.index(
            "-A FORWARD -i vpns00 -o host0 -s 10.20.0.0/16 "
            "-m conntrack --ctstate NEW -j DROP"
        )
        broad = lines.index(
            "-A FORWARD -i vpns00 -o host0 -s 10.0.0.0/8 "
            "-m conntrack --ctstate NEW -j ACCEPT"
        )
        self.assertLess(specific, broad)

    def test_no_bound_interfaces_means_no_forward_accept(self):
        config = ActiveConfig(
            devices={"oc": Device("oc", True)},
            profiles={
                "corp": Profile(
                    "corp",
                    True,
                    Direction.BIDIRECTIONAL,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc",),
                )
            },
        )
        state = compile_filter_state(
            config,
            DeviceBindingSnapshot((), ()),
        )
        self.assertNotIn("-j ACCEPT", state.restore_text)
        self.assertIn(":FORWARD DROP [0:0]", state.restore_text)


if __name__ == "__main__":
    unittest.main()
