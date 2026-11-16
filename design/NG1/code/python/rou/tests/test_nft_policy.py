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
from rou.nft_policy import compile_nft_filter_state, compile_nft_nat_state


def config():
    return ActiveConfig(
        devices={
            "oc": Device(
                "oc",
                True,
                nat=NatMode.MASQUERADE,
                publications=(
                    Publication(
                        TransportProtocol.TCP,
                        PortRange(44443, 44443),
                        PortRange(44443, 44443),
                    ),
                ),
                traffic_envelope=TrafficEnvelope(
                    default_action=EnvelopeAction.DROP,
                    rules=(
                        TrafficEnvelopeRule(
                            direction=EnvelopeDirection.FROM_DEVICE,
                            action=EnvelopeAction.ALLOW,
                            source=ipaddress.IPv4Network("10.0.0.0/8"),
                            protocol=EnvelopeProtocol.TCP,
                            destination_ports=(PortRange(22, 22),),
                        ),
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


class NftPolicyTests(unittest.TestCase):
    def bindings(self, ifindex=10):
        return DeviceBindingSnapshot(
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns00", ifindex),
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

    def test_filter_uses_numeric_generation_identity_for_dynamic_device(self):
        state = compile_nft_filter_state(
            config(),
            self.bindings(),
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        text = state.definition

        self.assertIn('iifname "host0" oif 10', text)
        self.assertIn('iif 10 oifname "host0"', text)
        self.assertNotIn("vpns00", text)
        self.assertNotIn("vpns01", text)
        self.assertIn("policy drop;", text)
        self.assertIn(
            'ip daddr 192.0.2.2 iifname "host0" tcp dport 44443 '
            "ct state new accept",
            text,
        )
        self.assertIn(
            "ip saddr 10.0.0.0/8 tcp dport 22 return",
            text,
        )

    def test_same_name_new_ifindex_changes_materialized_identity(self):
        old = compile_nft_filter_state(
            config(),
            self.bindings(10),
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        new = compile_nft_filter_state(
            config(),
            self.bindings(20),
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        self.assertIn("oif 10", old.definition)
        self.assertNotIn("oif 20", old.definition)
        self.assertIn("oif 20", new.definition)
        self.assertNotEqual(old.canonical, new.canonical)

    def test_nat_is_numeric_ifindex_and_prefix_scoped(self):
        state = compile_nft_nat_state(config(), self.bindings())
        self.assertIn(
            "ip daddr 10.0.0.0/8 oif 10 masquerade",
            state.definition,
        )
        self.assertNotIn("vpns00", state.definition)
        self.assertNotIn("vpns01", state.definition)


if __name__ == "__main__":
    unittest.main()
