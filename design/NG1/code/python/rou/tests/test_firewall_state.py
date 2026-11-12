import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import (
    ActiveConfig,
    Availability,
    Device,
    Direction,
    EnvelopeAction,
    EnvelopeDirection,
    EnvelopeProtocol,
    NatMode,
    PortRange,
    Profile,
    Publication,
    TrafficEnvelope,
    TrafficEnvelopeRule,
    TransportProtocol,
)
from rou.firewall_state import compile_filter_state


class FirewallStateTests(unittest.TestCase):
    def test_filter_is_default_drop_and_scoped_to_bound_interfaces(self):
        config = ActiveConfig(
            devices={"oc": Device("oc", True, nat=NatMode.NONE)},
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

        self.assertIn(":INPUT DROP [0:0]", state.restore_text)
        self.assertIn(":FORWARD DROP [0:0]", state.restore_text)
        self.assertIn(":OUTPUT DROP [0:0]", state.restore_text)
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
            devices={"oc": Device("oc", True, nat=NatMode.NONE)},
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
            devices={"oc": Device("oc", True, nat=NatMode.NONE)},
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
        self.assertFalse(
            any(
                line.startswith("-A FORWARD") and line.endswith("-j ACCEPT")
                for line in state.restore_text.splitlines()
            )
        )
        self.assertIn(":FORWARD DROP [0:0]", state.restore_text)

    def test_envelope_jump_precedes_state_accept_and_allow_returns(self):
        envelope = TrafficEnvelope(
            default_action=EnvelopeAction.ALLOW,
            rules=(
                TrafficEnvelopeRule(
                    direction=EnvelopeDirection.FROM_DEVICE,
                    action=EnvelopeAction.DROP,
                    source=ipaddress.IPv4Network("10.20.0.0/16"),
                    protocol=EnvelopeProtocol.TCP,
                    destination_ports=(PortRange(8007, 8007),),
                ),
                TrafficEnvelopeRule(
                    direction=EnvelopeDirection.FROM_DEVICE,
                    action=EnvelopeAction.ALLOW,
                    source=ipaddress.IPv4Network("10.0.0.0/8"),
                ),
            ),
        )
        config = ActiveConfig(
            devices={
                "oc": Device(
                    "oc",
                    True,
                    nat=NatMode.NONE,
                    traffic_envelope=envelope,
                )
            },
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
        jump = lines.index(
            "-A FORWARD -i vpns00 -o host0 -j VPNG-E1-F"
        )
        established = lines.index(
            "-A FORWARD -i vpns00 -o host0 -m conntrack "
            "--ctstate ESTABLISHED,RELATED -j ACCEPT"
        )
        self.assertLess(jump, established)

        drop = lines.index(
            "-A VPNG-E1-F -s 10.20.0.0/16 -p tcp -m tcp "
            "--dport 8007 -j DROP"
        )
        allow = lines.index(
            "-A VPNG-E1-F -s 10.0.0.0/8 -j RETURN"
        )
        terminal = lines.index("-A VPNG-E1-F -j RETURN")
        self.assertLess(drop, allow)
        self.assertLess(allow, terminal)
        self.assertNotIn("-A VPNG-E1-F -j ACCEPT", lines)

    def test_envelope_default_drop_is_materialized_for_both_directions(self):
        config = ActiveConfig(
            devices={
                "oc": Device(
                    "oc",
                    True,
                    nat=NatMode.NONE,
                    traffic_envelope=TrafficEnvelope(
                        default_action=EnvelopeAction.DROP,
                    ),
                )
            },
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
        self.assertIn("-A VPNG-E1-F -j DROP", state.restore_text)
        self.assertIn("-A VPNG-E1-T -j DROP", state.restore_text)

    def test_envelope_port_lists_expand_without_multiport_limit(self):
        rule = TrafficEnvelopeRule(
            direction=EnvelopeDirection.TO_DEVICE,
            action=EnvelopeAction.DROP,
            protocol=EnvelopeProtocol.UDP,
            source_ports=(PortRange(1000, 1001), PortRange(2000, 2000)),
            destination_ports=(PortRange(53, 53), PortRange(5353, 5355)),
        )
        config = ActiveConfig(
            devices={
                "oc": Device(
                    "oc",
                    True,
                    nat=NatMode.NONE,
                    traffic_envelope=TrafficEnvelope(
                        default_action=EnvelopeAction.ALLOW,
                        rules=(rule,),
                    ),
                )
            },
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
        text = compile_filter_state(
            config,
            DeviceBindingSnapshot((), ()),
        ).restore_text
        generated = [
            line
            for line in text.splitlines()
            if line.startswith("-A VPNG-E1-T -p udp")
            and line.endswith("-j DROP")
        ]
        self.assertEqual(len(generated), 4)
        self.assertTrue(all("-m udp" in line for line in generated))


    def test_input_is_default_drop_and_publication_is_host0_local_only(self):
        config = ActiveConfig(
            devices={
                "oc": Device(
                    "oc",
                    True,
                    nat=NatMode.NONE,
                    publications=(
                        Publication(
                            TransportProtocol.TCP,
                            PortRange(44443, 44443),
                            PortRange(44443, 44443),
                        ),
                        Publication(
                            TransportProtocol.UDP,
                            PortRange(4700, 4702),
                            PortRange(55200, 55202),
                        ),
                    ),
                )
            },
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
        state = compile_filter_state(
            config,
            DeviceBindingSnapshot((), ()),
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        lines = state.restore_text.splitlines()

        self.assertIn(":INPUT DROP [0:0]", lines)
        self.assertIn("-A INPUT -i lo -j ACCEPT", lines)
        self.assertIn(
            "-A INPUT -i host0 -m conntrack --ctstate "
            "ESTABLISHED,RELATED -j ACCEPT",
            lines,
        )
        self.assertIn(
            "-A INPUT -i host0 -d 192.0.2.2/32 -p tcp -m tcp "
            "--dport 44443 -m conntrack --ctstate NEW -j ACCEPT",
            lines,
        )
        self.assertIn(
            "-A INPUT -i host0 -d 192.0.2.2/32 -p udp -m udp "
            "--dport 55200:55202 -m conntrack --ctstate NEW -j ACCEPT",
            lines,
        )
        self.assertFalse(
            any(
                line.startswith("-A INPUT -i vpns")
                and line.endswith("-j ACCEPT")
                for line in lines
            )
        )

    def test_active_publication_requires_explicit_local_address(self):
        config = ActiveConfig(
            devices={
                "oc": Device(
                    "oc",
                    True,
                    nat=NatMode.NONE,
                    publications=(
                        Publication(
                            TransportProtocol.TCP,
                            PortRange(44443, 44443),
                            PortRange(44443, 44443),
                        ),
                    ),
                )
            },
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
        with self.assertRaisesRegex(ValueError, "publication address"):
            compile_filter_state(
                config,
                DeviceBindingSnapshot((), ()),
            )

    def test_output_is_default_drop_and_only_host0_is_local_underlay(self):
        state = compile_filter_state(
            ActiveConfig({}, {}),
            DeviceBindingSnapshot((), ()),
        )
        lines = state.restore_text.splitlines()

        self.assertIn(":OUTPUT DROP [0:0]", lines)
        self.assertIn("-A OUTPUT -o lo -j ACCEPT", lines)
        self.assertIn(
            "-A OUTPUT -o host0 -m conntrack --ctstate "
            "ESTABLISHED,RELATED -j ACCEPT",
            lines,
        )
        self.assertIn(
            "-A OUTPUT -o host0 -m conntrack --ctstate NEW -j ACCEPT",
            lines,
        )
        self.assertFalse(
            any(
                line.startswith("-A OUTPUT -o vpns")
                and line.endswith("-j ACCEPT")
                for line in lines
            )
        )

    def test_established_pairs_exist_only_for_bound_interface_and_host0(self):
        config = ActiveConfig(
            devices={
                "oc": Device("oc", True, nat=NatMode.NONE),
                "wg": Device("wg", True, nat=NatMode.NONE),
            },
            profiles={
                "corp": Profile(
                    "corp",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc", "wg"),
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
                BoundInterface(
                    "wg",
                    0,
                    InterfaceIdentity("wg0", 20),
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
        lines = compile_filter_state(config, bindings).restore_text.splitlines()
        state_accepts = [
            line
            for line in lines
            if "--ctstate ESTABLISHED,RELATED -j ACCEPT" in line
            and line.startswith("-A FORWARD")
        ]

        self.assertEqual(
            set(state_accepts),
            {
                "-A FORWARD -i host0 -o vpns00 -m conntrack "
                "--ctstate ESTABLISHED,RELATED -j ACCEPT",
                "-A FORWARD -i vpns00 -o host0 -m conntrack "
                "--ctstate ESTABLISHED,RELATED -j ACCEPT",
                "-A FORWARD -i host0 -o wg0 -m conntrack "
                "--ctstate ESTABLISHED,RELATED -j ACCEPT",
                "-A FORWARD -i wg0 -o host0 -m conntrack "
                "--ctstate ESTABLISHED,RELATED -j ACCEPT",
            },
        )
        self.assertTrue(all("vpns01" not in line for line in state_accepts))
        self.assertFalse(
            any(
                "-i vpns00 -o wg0" in line or "-i wg0 -o vpns00" in line
                for line in state_accepts
            )
        )


if __name__ == "__main__":
    unittest.main()
