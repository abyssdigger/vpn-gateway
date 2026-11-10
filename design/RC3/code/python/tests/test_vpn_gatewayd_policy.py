#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def binding(interface, network, index, rank=None):
    return vpng.BindingSpec(
        vpng.InterfaceSelector.parse(interface),
        IPv4Network(network),
        index,
        rank,
    )


def profile(profile_id, *, routes, bindings, allowed_sources=()):
    return vpng.VpnProfileConfig(
        profile_id=profile_id,
        routes=tuple(IPv4Network(x) for x in routes),
        bindings=tuple(bindings),
        allowed_sources=tuple(IPv4Network(x) for x in allowed_sources),
    )


def config():
    primary = profile(
        "primary",
        routes=("10.0.0.0/8",),
        bindings=(
            binding("wg0", "172.20.126.0/29", 0, 0),
            binding("vpns+", "172.20.130.0/29", 1, None),
        ),
        allowed_sources=("10.200.201.0/24",),
    )
    backup = profile(
        "backup",
        routes=("192.168.0.0/16",),
        bindings=(binding("tun0", "172.20.140.0/29", 0, 0),),
    )
    return vpng.GatewayConfig(
        enabled=True,
        reconcile_interval=10.0,
        common_allowed_sources=(IPv4Network("10.200.200.8/32"),),
        profiles=MappingProxyType({"primary": primary, "backup": backup}),
    )


def interface_state():
    cfg = config()
    records = (
        vpng.InterfaceRecord(
            "wg0", 6, frozenset({IPv4Address("172.20.126.2")})
        ),
        vpng.InterfaceRecord(
            "vpns7", 7, frozenset({IPv4Address("172.20.130.1")})
        ),
    )
    return MappingProxyType(
        {
            profile_id: vpng.resolve_profile_interface_state(
                profile.bindings,
                records,
            )
            for profile_id, profile in cfg.profiles.items()
        }
    )


class FullPolicyTests(unittest.TestCase):
    def test_full_policy_uses_only_exact_active_names_for_allow_and_nat(self):
        desired = vpng.desired_full_policy(config(), interface_state())

        primary_input = desired.filter.chain("VPNG-PRIMARY-INPUT").rules
        self.assertTrue(any("-i wg0" in rule for rule in primary_input))
        self.assertTrue(any("-i vpns7" in rule for rule in primary_input))
        self.assertFalse(any("-i vpns+" in rule for rule in primary_input))

        primary_forward = desired.filter.chain("VPNG-PRIMARY-FORWARD").rules
        accepts = tuple(rule for rule in primary_forward if "-j ACCEPT" in rule)
        self.assertTrue(any("-o wg0" in rule for rule in accepts))
        self.assertTrue(any("-o vpns7" in rule for rule in accepts))
        self.assertFalse(any("vpns+" in rule for rule in accepts))

        primary_nat = desired.nat.chain("VPNG-PRIMARY-NAT").rules
        self.assertEqual(
            primary_nat,
            (
                "-A VPNG-PRIMARY-NAT -o wg0 "
                "-m addrtype ! --src-type LOCAL -j MASQUERADE",
                "-A VPNG-PRIMARY-NAT -o vpns7 "
                "-m addrtype ! --src-type LOCAL -j MASQUERADE",
                "-A VPNG-PRIMARY-NAT -j RETURN",
            ),
        )

    def test_exact_blocks_precede_selector_guards(self):
        desired = vpng.desired_full_policy(config(), interface_state())
        ingress = desired.filter.chain("VPNG-INGRESS").rules

        exact_accept = next(
            i for i, rule in enumerate(ingress)
            if "-i vpns7" in rule and "-j ACCEPT" in rule
        )
        prefix_guard = next(
            i for i, rule in enumerate(ingress)
            if "-i vpns+" in rule and "-j REJECT" in rule
        )
        self.assertLess(exact_accept, prefix_guard)

    def test_reserved_chain_contains_all_unique_binding_networks(self):
        desired = vpng.desired_full_policy(config(), interface_state())
        rules = desired.filter.chain("VPNG-RESERVED").rules
        self.assertTrue(any("-d 172.20.126.0/29 " in r for r in rules))
        self.assertTrue(any("-d 172.20.130.0/29 " in r for r in rules))
        self.assertTrue(any("-d 172.20.140.0/29 " in r for r in rules))

    def test_isolation_filter_has_guards_but_no_binding_accepts(self):
        desired = vpng.desired_isolation_filter(config())
        ingress = desired.chain("VPNG-INGRESS").rules
        self.assertTrue(any("-i wg0" in r and "-j REJECT" in r for r in ingress))
        self.assertTrue(any("-i vpns+" in r and "-j REJECT" in r for r in ingress))
        self.assertFalse(any("-j ACCEPT" in r for r in ingress))

    def test_profile_forward_has_terminal_destination_reject(self):
        desired = vpng.desired_full_policy(config(), interface_state())
        rules = desired.filter.chain("VPNG-PRIMARY-FORWARD").rules
        reject_index = next(
            i for i, r in enumerate(rules)
            if "-d 10.0.0.0/8 -j REJECT" in r
        )
        accept_indexes = [
            i for i, r in enumerate(rules)
            if "-d 10.0.0.0/8" in r and "-j ACCEPT" in r
        ]
        self.assertTrue(accept_indexes)
        self.assertTrue(all(i < reject_index for i in accept_indexes))

    def test_common_and_profile_sources_are_both_allowed(self):
        desired = vpng.desired_full_policy(config(), interface_state())
        rules = desired.filter.chain("VPNG-PRIMARY-FORWARD").rules
        self.assertTrue(any("-s 10.200.200.8/32 " in r for r in rules))
        self.assertTrue(any("-s 10.200.201.0/24 " in r for r in rules))


if __name__ == "__main__":
    unittest.main()
