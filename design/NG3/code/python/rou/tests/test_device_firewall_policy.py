from __future__ import annotations

import unittest
from ipaddress import IPv4Network

from rou.device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
)


class DeviceFirewallPolicyIntentTests(unittest.TestCase):
    def test_omitted_policy_is_distinct_from_explicit_policy(self):
        omitted = DeviceFirewallPolicyIntent(
            device_id="wg-main",
            rules=None,
        )
        explicit = DeviceFirewallPolicyIntent(
            device_id="wg-main",
            rules=(
                DeviceFirewallRuleIntent(
                    direction=DeviceFirewallDirection.OUT,
                    action=DeviceFirewallAction.DENY,
                ),
            ),
        )
        self.assertIsNone(omitted.rules)
        self.assertEqual(len(explicit.rules or ()), 1)

    def test_explicit_policy_preserves_declared_rule_order(self):
        first = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.DENY,
            destination_ipv4_cidr=IPv4Network("10.0.0.0/8"),
        )
        second = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.ALLOW,
            destination_ipv4_cidr=IPv4Network("10.1.0.0/16"),
        )
        policy = DeviceFirewallPolicyIntent(
            device_id="wg-main",
            rules=(first, second),
        )
        self.assertEqual(policy.rules, (first, second))

    def test_empty_explicit_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-empty tuple"):
            DeviceFirewallPolicyIntent(
                device_id="wg-main",
                rules=(),
            )

    def test_ports_are_bounded_without_selecting_external_grammar(self):
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.IN,
            action=DeviceFirewallAction.REJECT,
            protocol="tcp",
            source_ports=1,
            destination_ports=65535,
        )
        self.assertEqual(rule.source_ports, 1)
        self.assertEqual(rule.destination_ports, 65535)

        for invalid in (0, 65536, "443"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    DeviceFirewallRuleIntent(
                        direction=DeviceFirewallDirection.IN,
                        action=DeviceFirewallAction.DENY,
                        source_ports=invalid,  # type: ignore[arg-type]
                    )

    def test_ipv4_selectors_are_typed_internal_semantics(self):
        source = IPv4Network("192.0.2.0/24")
        destination = IPv4Network("198.51.100.10/32")
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.IN,
            action=DeviceFirewallAction.ALLOW,
            source_ipv4_cidr=source,
            destination_ipv4_cidr=destination,
            comment="operator note",
        )
        self.assertEqual(rule.source_ipv4_cidr, source)
        self.assertEqual(rule.destination_ipv4_cidr, destination)

    def test_protocol_vocabulary_is_not_selected_here(self):
        rule = DeviceFirewallRuleIntent(
            direction=DeviceFirewallDirection.OUT,
            action=DeviceFirewallAction.DENY,
            protocol="future-protocol-token",
        )
        self.assertEqual(rule.protocol, "future-protocol-token")


if __name__ == "__main__":
    unittest.main()
