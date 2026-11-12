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
from rou.nft_policy import (
    _numeric_interface_refs_from_json,
    NftObservedState,
    NftRulesetInventory,
    compile_nft_filter_state,
    compile_nft_nat_state,
    verify_nft_observation,
    verify_nft_ruleset_ownership,
    verify_nft_table,
)


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

    def test_json_generation_markers_preserve_identity_despite_symbolic_meta(self):
        sample = (
            '{"nftables":['
            '{"rule":{"comment":"vpng-ifref:iif:2","expr":['
            '{"match":{"op":"==","left":{"meta":{"key":"iif"}},"right":"vpn0"}}'
            ']}},'
            '{"rule":{"comment":"vpng-ifref:oif:7","expr":['
            '{"match":{"op":"==","left":{"meta":{"key":"oif"}},"right":"vpn1"}}'
            ']}}]}'
        )
        self.assertEqual(
            _numeric_interface_refs_from_json(sample),
            (("iif", 2), ("oif", 7)),
        )

    def test_verifier_rejects_stale_numeric_generation_even_if_text_matches(self):
        desired = compile_nft_filter_state(
            config(),
            self.bindings(20),
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        stale_refs = tuple(
            (kind, 10 if value == 20 else value)
            for kind, value in desired.numeric_interface_refs
        )

        result = verify_nft_observation(
            desired,
            NftObservedState(
                canonical=desired.canonical,
                numeric_interface_refs=stale_refs,
            ),
        )

        self.assertFalse(result.ok)
        self.assertIn("numeric-interface-refs", result.actual)

    def test_desired_state_records_exact_numeric_interface_ref_multiset(self):
        desired = compile_nft_filter_state(
            config(),
            self.bindings(10),
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        self.assertTrue(desired.numeric_interface_refs)
        self.assertTrue(
            all(
                value == 10
                for _kind, value in desired.numeric_interface_refs
            )
        )

    def test_absent_owned_table_is_mismatch_not_backend_error(self):
        desired = compile_nft_filter_state(
            config(),
            self.bindings(),
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        result = verify_nft_observation(desired, None)
        self.assertFalse(result.ok)
        self.assertEqual(result.actual, "<absent>")

    def test_foreign_nft_table_breaks_exclusive_ownership(self):
        result = verify_nft_ruleset_ownership(
            NftRulesetInventory(
                (
                    ("ip", "vpng_filter"),
                    ("ip", "vpng_nat"),
                    ("inet", "foreign"),
                )
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(
            result.foreign_tables,
            (("inet", "foreign"),),
        )


if __name__ == "__main__":
    unittest.main()
