import unittest
from ipaddress import IPv4Network

from rou.interface_identity import InterfaceIdentity
from rou.linux_stack_return_affinity import (
    LinuxStackReturnAffinityBackend,
    STACK_RETURN_TABLE,
    render_stack_return_affinity_nft,
)
from rou.stack_return_affinity import (
    StackReturnAffinityDesired,
    StackReturnClassifierSpec,
    StackReturnRuleSpec,
)


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)


class Runner:
    def __init__(self):
        self.calls = []
        self.scripts = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        return ""

    def run_script(self, argv, script):
        self.calls.append(tuple(argv))
        self.scripts.append(script)
        return ""


def desired():
    return StackReturnAffinityDesired(
        host_boundary=HOST,
        classifiers=(
            StackReturnClassifierSpec(
                profile_id="p",
                ingress=VPN,
                remote_prefix=IPv4Network("10.0.0.0/16"),
                mark=0x10000000,
            ),
        ),
        rules=(
            StackReturnRuleSpec(
                profile_id="p",
                mark=0x10000000,
                table=0x80000000,
                priority=0x1800,
            ),
        ),
    )


class LinuxStackReturnAffinityTests(unittest.TestCase):
    def test_nft_renderer_marks_ingress_new_and_restores_on_host_boundary(self):
        script = render_stack_return_affinity_nft(desired())
        self.assertIn(f"table ip {STACK_RETURN_TABLE}", script)
        self.assertIn(
            "meta iif 20 ip saddr 10.0.0.0/16 ct state new "
            "ct mark set 0x10000000 meta mark set ct mark",
            script,
        )
        self.assertIn(
            "meta iif 10 ct mark 0x10000000 meta mark set ct mark",
            script,
        )

    def test_backend_creates_nft_and_exact_rpdb_rule(self):
        runner = Runner()
        backend = LinuxStackReturnAffinityBackend(runner, "stack")
        state = desired()
        backend.create_nft(state)
        backend.add_rule(state.rules[0])
        self.assertEqual(
            runner.calls[0],
            ("ip", "netns", "exec", "stack", "nft", "-f", "-"),
        )
        self.assertEqual(
            runner.calls[1],
            (
                "ip", "netns", "exec", "stack",
                "ip", "-4", "rule", "add",
                "priority", "6144",
                "fwmark", "0x10000000",
                "lookup", "2147483648",
            ),
        )

    def test_delete_is_exact_owner_scope(self):
        runner = Runner()
        backend = LinuxStackReturnAffinityBackend(runner, "stack")
        state = desired()
        backend.delete_rule(state.rules[0])
        backend.delete_nft()
        self.assertEqual(
            runner.calls[-1],
            (
                "ip", "netns", "exec", "stack",
                "nft", "delete", "table", "ip", STACK_RETURN_TABLE,
            ),
        )

    def test_empty_owner_is_not_materialized(self):
        runner = Runner()
        backend = LinuxStackReturnAffinityBackend(runner, "stack")
        backend.create_nft(
            StackReturnAffinityDesired(
                host_boundary=HOST,
                classifiers=(),
                rules=(),
            )
        )
        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
