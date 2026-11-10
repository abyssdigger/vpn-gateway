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


def profile(
    profile_id: str,
    *,
    interface: str,
    network: str,
    routes: tuple[str, ...],
    allowed_sources: tuple[str, ...] = (),
) -> vpng.VpnProfileConfig:
    return vpng.VpnProfileConfig(
        profile_id=profile_id,
        interface=vpng.InterfaceSelector.parse(interface),
        network=IPv4Network(network),
        routes=tuple(IPv4Network(item) for item in routes),
        allowed_sources=tuple(
            IPv4Network(item) for item in allowed_sources
        ),
    )


def config() -> vpng.GatewayConfig:
    primary = profile(
        "primary",
        interface="vpns+",
        network="172.20.130.0/29",
        routes=("10.0.0.0/8",),
        allowed_sources=("10.200.201.0/24",),
    )
    backup = profile(
        "backup",
        interface="wg0",
        network="172.20.126.0/29",
        routes=("192.168.0.0/16",),
    )
    return vpng.GatewayConfig(
        reconcile_interval=10.0,
        common_allowed_sources=(IPv4Network("10.200.200.8/32"),),
        vpns=MappingProxyType({
            "primary": primary,
            "backup": backup,
        }),
    )


def interface_state():
    primary_record = vpng.InterfaceRecord(
        "vpns7",
        7,
        frozenset({IPv4Address("172.20.130.1")}),
    )
    return MappingProxyType({
        "primary": vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse("vpns+"),
            (primary_record,),
            IPv4Network("172.20.130.0/29"),
        ),
        "backup": vpng.resolve_profile_interface_state(
            vpng.InterfaceSelector.parse("wg0"),
            (),
            IPv4Network("172.20.126.0/29"),
        ),
    })


class FullPolicyTests(unittest.TestCase):
    def test_full_policy_uses_exact_binding_for_allow_and_nat(self):
        desired = vpng.desired_full_policy(config(), interface_state())

        primary_input = desired.filter.chain("VPNG-PRIMARY-INPUT").rules
        self.assertTrue(any("-i vpns7" in rule for rule in primary_input))
        self.assertFalse(any("-i vpns+" in rule for rule in primary_input))
        self.assertFalse(any("--ctstate NEW" in rule for rule in primary_input))

        primary_forward = desired.filter.chain(
            "VPNG-PRIMARY-FORWARD"
        ).rules
        accepts = tuple(
            rule for rule in primary_forward if "-j ACCEPT" in rule
        )
        self.assertTrue(accepts)
        self.assertTrue(all("-o vpns7" in rule for rule in accepts))
        self.assertTrue(all("vpns+" not in rule for rule in accepts))

        primary_nat = desired.nat.chain("VPNG-PRIMARY-NAT").rules
        self.assertEqual(
            primary_nat,
            (
                "-A VPNG-PRIMARY-NAT -o vpns7 "
                "-m addrtype ! --src-type LOCAL -j MASQUERADE",
                "-A VPNG-PRIMARY-NAT -j RETURN",
            ),
        )

    def test_ingress_exact_block_precedes_deny_only_selector_guard(self):
        desired = vpng.desired_full_policy(config(), interface_state())
        ingress = desired.filter.chain("VPNG-INGRESS").rules

        exact_accept = next(
            index
            for index, rule in enumerate(ingress)
            if "-i vpns7" in rule and "-j ACCEPT" in rule
        )
        prefix_guard = next(
            index
            for index, rule in enumerate(ingress)
            if "-i vpns+" in rule and "-j REJECT" in rule
        )
        self.assertLess(exact_accept, prefix_guard)

    def test_unready_profile_has_deny_only_filter_and_empty_nat(self):
        desired = vpng.desired_full_policy(config(), interface_state())

        backup_input = desired.filter.chain("VPNG-BACKUP-INPUT").rules
        self.assertEqual(
            backup_input,
            ("-A VPNG-BACKUP-INPUT -j RETURN",),
        )

        backup_forward = desired.filter.chain(
            "VPNG-BACKUP-FORWARD"
        ).rules
        self.assertFalse(any("-j ACCEPT" in rule for rule in backup_forward))
        self.assertTrue(any("-d 192.168.0.0/16" in rule for rule in backup_forward))

        self.assertEqual(
            desired.nat.chain("VPNG-BACKUP-NAT").rules,
            ("-A VPNG-BACKUP-NAT -j RETURN",),
        )

    def test_selector_guards_are_deny_only(self):
        desired = vpng.desired_full_policy(config(), interface_state())

        input_guard = desired.filter.chain("VPNG-INPUT-GUARD").rules
        ingress = desired.filter.chain("VPNG-INGRESS").rules

        self.assertTrue(
            any("-i vpns+" in rule and "-j REJECT" in rule for rule in input_guard)
        )
        self.assertTrue(
            any("-i vpns+" in rule and "-j REJECT" in rule for rule in ingress)
        )
        self.assertFalse(
            any("-i vpns+" in rule and "-j ACCEPT" in rule for rule in input_guard)
        )
        self.assertFalse(
            any("-i vpns+" in rule and "-j ACCEPT" in rule for rule in ingress)
        )

    def test_incomplete_interface_state_is_rejected(self):
        cfg = config()
        state = interface_state()

        with self.assertRaises(ValueError):
            vpng.desired_full_policy(
                cfg,
                MappingProxyType({"primary": state["primary"]}),
            )


class IsolationPolicyTests(unittest.TestCase):
    def test_isolation_filter_contains_no_binding_specific_accept(self):
        desired = vpng.desired_isolation_filter(config())

        for chain in desired.chains:
            self.assertFalse(any("-j ACCEPT" in rule for rule in chain.rules))

        self.assertEqual(
            desired.chain("VPNG-PRIMARY-INPUT").rules,
            ("-A VPNG-PRIMARY-INPUT -j RETURN",),
        )
        self.assertEqual(
            desired.chain("VPNG-BACKUP-INPUT").rules,
            ("-A VPNG-BACKUP-INPUT -j RETURN",),
        )

    def test_isolation_profile_forward_is_unconditional_deny(self):
        desired = vpng.desired_isolation_filter(config())

        self.assertEqual(
            desired.chain("VPNG-PRIMARY-FORWARD").rules,
            (
                "-A VPNG-PRIMARY-FORWARD -d 10.0.0.0/8 "
                "-j REJECT --reject-with icmp-host-prohibited",
                "-A VPNG-PRIMARY-FORWARD -j RETURN",
            ),
        )

    def test_isolation_ingress_has_only_selector_guards(self):
        desired = vpng.desired_isolation_filter(config())
        ingress = desired.chain("VPNG-INGRESS").rules

        self.assertEqual(
            ingress,
            (
                "-A VPNG-INGRESS -i wg0 "
                "-j REJECT --reject-with icmp-host-prohibited",
                "-A VPNG-INGRESS -i vpns+ "
                "-j REJECT --reject-with icmp-host-prohibited",
                "-A VPNG-INGRESS -j RETURN",
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
