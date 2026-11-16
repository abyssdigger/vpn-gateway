from __future__ import annotations

import unittest
from ipaddress import IPv4Address

from rou.interface_identity import InterfaceIdentity
from rou.linux_local_publication import LinuxLocalPublicationBackend
from rou.local_publication_mutation import (
    LocalPublicationDeleteRef,
    LocalPublicationMutationStep,
)
from rou.local_publication_policy import (
    LocalPublicationHook,
    LocalPublicationRuleSpec,
    PublicationProtocol,
)


HOST = InterfaceIdentity("host0", 10)
ADDR = IPv4Address("198.51.100.47")


class FakeRunner:
    def __init__(self):
        self.commands = []
        self.scripts = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        return ""

    def run_script(self, argv, script):
        self.commands.append(tuple(argv))
        self.scripts.append(script)
        return ""


class LinuxLocalPublicationBackendTests(unittest.TestCase):
    def test_add_pair_is_one_transaction_output_then_input(self):
        runner = FakeRunner()
        backend = LinuxLocalPublicationBackend(runner, "managed")
        output = LocalPublicationRuleSpec(
            LocalPublicationHook.OUTPUT,
            PublicationProtocol.TCP,
            HOST,
            ADDR,
            44443,
        )
        input_rule = LocalPublicationRuleSpec(
            LocalPublicationHook.INPUT,
            PublicationProtocol.TCP,
            HOST,
            ADDR,
            44443,
        )
        backend.apply_local_publication_step(
            LocalPublicationMutationStep(
                delete_rules=(),
                add_rules=(output, input_rule),
            )
        )
        self.assertEqual(len(runner.scripts), 1)
        self.assertEqual(
            runner.scripts[0],
            'add rule ip vpn_gate stack_output meta oif 10 '
            'ip saddr 198.51.100.47 tcp sport 44443 accept '
            'comment "vpn-gate:ng3:local-publication-v1"\n'
            'add rule ip vpn_gate stack_input meta iif 10 '
            'ip daddr 198.51.100.47 tcp dport 44443 accept '
            'comment "vpn-gate:ng3:local-publication-v1"\n',
        )

    def test_delete_pair_keeps_chain_identity_with_handle(self):
        runner = FakeRunner()
        backend = LinuxLocalPublicationBackend(runner, "managed")
        backend.apply_local_publication_step(
            LocalPublicationMutationStep(
                delete_rules=(
                    LocalPublicationDeleteRef(
                        LocalPublicationHook.INPUT,
                        41,
                    ),
                    LocalPublicationDeleteRef(
                        LocalPublicationHook.OUTPUT,
                        42,
                    ),
                ),
                add_rules=(),
            )
        )
        self.assertEqual(
            runner.scripts[0],
            "delete rule ip vpn_gate stack_input handle 41\n"
            "delete rule ip vpn_gate stack_output handle 42\n",
        )

    def test_udp_rule_uses_udp_exact_port_shape(self):
        runner = FakeRunner()
        backend = LinuxLocalPublicationBackend(runner, "managed")
        backend.apply_local_publication_step(
            LocalPublicationMutationStep(
                delete_rules=(),
                add_rules=(
                    LocalPublicationRuleSpec(
                        LocalPublicationHook.INPUT,
                        PublicationProtocol.UDP,
                        HOST,
                        ADDR,
                        443,
                    ),
                ),
            )
        )
        self.assertIn(
            "ip daddr 198.51.100.47 udp dport 443 accept",
            runner.scripts[0],
        )


if __name__ == "__main__":
    unittest.main()
