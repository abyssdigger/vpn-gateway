from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import (
    CommandExecutionError,
    CommandResult,
    KernelApplyError,
    NamespaceBackend,
    execute_kernel_mutation_plan,
)
from rou.kernel_mutation import KernelMutation, KernelMutationPlan


class FakeHostBackend:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append((argv, input_text, check))
        rc = 1 if self.fail_on is not None and self.fail_on in argv else 0
        result = CommandResult(argv, rc, "ok\n" if rc == 0 else "", "boom\n" if rc else "")
        if check and rc:
            raise CommandExecutionError(result)
        return result


class CommandBackendTests(unittest.TestCase):
    def test_namespace_backend_prefixes_without_shell(self):
        host = FakeHostBackend()
        ns = NamespaceBackend("rou0", host)
        result = ns.run(("ip", "route", "show"))
        self.assertEqual(
            result.argv,
            ("ip", "netns", "exec", "rou0", "ip", "route", "show"),
        )
        self.assertEqual(
            host.calls[0][0],
            ("ip", "netns", "exec", "rou0", "ip", "route", "show"),
        )

    def test_executor_preserves_order(self):
        host = FakeHostBackend()
        ns = NamespaceBackend("rou0", host)
        plan = KernelMutationPlan(
            (
                KernelMutation(("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"), "barrier-close"),
                KernelMutation(("ip", "route", "flush", "table", "1"), "route-clear"),
            )
        )
        execute_kernel_mutation_plan(plan, ns)
        self.assertEqual(
            [call[0][-1] for call in host.calls],
            ["net.ipv4.ip_forward=0", "1"],
        )

    def test_executor_stops_on_first_failure_and_never_runs_later_command(self):
        host = FakeHostBackend(fail_on="flush")
        ns = NamespaceBackend("rou0", host)
        plan = KernelMutationPlan(
            (
                KernelMutation(("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"), "barrier-close"),
                KernelMutation(("ip", "route", "flush", "table", "1"), "route-clear"),
                KernelMutation(("ip", "route", "add", "table", "1", "blackhole", "default"), "route-install"),
            )
        )
        with self.assertRaisesRegex(KernelApplyError, "route-clear"):
            execute_kernel_mutation_plan(plan, ns)

        self.assertEqual(len(host.calls), 2)

    def test_namespace_must_be_nonempty(self):
        with self.assertRaisesRegex(ValueError, "namespace"):
            NamespaceBackend("", FakeHostBackend())


if __name__ == "__main__":
    unittest.main()
