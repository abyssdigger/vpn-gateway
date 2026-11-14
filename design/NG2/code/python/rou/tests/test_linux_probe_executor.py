from ipaddress import IPv4Address
import json
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_driver import CommandResult
from rou.linux_local_process import LinuxLocalProcessConfig
from rou.linux_probe_executor import (
    LinuxIcmpProbeExecutor,
    LinuxIcmpProbeExecutorConfig,
    ProbeAttemptOutcome,
)
from rou.probe_rules import AvailabilityProbeRequest


class FakeRunner:
    def __init__(self, identity: InterfaceIdentity):
        self.identity = identity
        self.calls = []
        self.ping_rc = 0
        self.ping_stderr = ""
        self.group_range = "1 0"

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append(argv)
        if argv[:6] == (
            "ip", "-j", "link", "show", "dev", self.identity.ifname
        ):
            return CommandResult(
                0,
                json.dumps(
                    [{"ifname": self.identity.ifname, "ifindex": self.identity.ifindex}]
                ),
                "",
            )
        if argv[:4] == ("sysctl", "-q", "-w",):
            self.group_range = argv[-1].split("=", 1)[1]
            return CommandResult(0, "", "")
        if argv == ("sysctl", "-n", "net.ipv4.ping_group_range"):
            return CommandResult(0, self.group_range + "\n", "")
        if argv[0] == "setpriv":
            return CommandResult(self.ping_rc, "", self.ping_stderr)
        raise AssertionError(f"unexpected command {argv!r}")


class LinuxIcmpProbeExecutorTests(unittest.TestCase):
    def setUp(self):
        self.identity = InterfaceIdentity("vpns00", 10)
        self.runner = FakeRunner(self.identity)
        self.executor = LinuxIcmpProbeExecutor(
            self.runner,
            LinuxIcmpProbeExecutorConfig(
                local_process=LinuxLocalProcessConfig(
                    uid=65534,
                    ct_mark=0x24,
                ),
                gid=65534,
                ping_path="/usr/bin/ping",
            ),
        )
        self.request = AvailabilityProbeRequest(
            "probe",
            self.identity,
            IPv4Address("203.0.113.24"),
        )

    def test_reply_uses_exact_generation_and_capability_free_bound_command(self):
        result = self.executor.execute(self.request, timeout_seconds=2)

        self.assertIs(result.outcome, ProbeAttemptOutcome.REPLY)
        ping = self.runner.calls[-1]
        self.assertEqual(ping[0], "setpriv")
        self.assertIn("--reuid=65534", ping)
        self.assertIn("--regid=65534", ping)
        self.assertIn("--bounding-set=-all", ping)
        self.assertIn("--no-new-privs", ping)
        self.assertEqual(ping[-4:], ("2", "-I", "vpns00", "203.0.113.24"))
        self.assertEqual(self.runner.group_range, "65534 65534")

    def test_ping_no_reply_is_probe_outcome_not_executor_error(self):
        self.runner.ping_rc = 1

        result = self.executor.execute(self.request, timeout_seconds=1)

        self.assertIs(result.outcome, ProbeAttemptOutcome.NO_REPLY)
        self.assertIsNone(result.diagnostic)

    def test_ping_execution_error_is_not_remote_no_reply(self):
        self.runner.ping_rc = 2
        self.runner.ping_stderr = "local failure"

        result = self.executor.execute(self.request, timeout_seconds=1)

        self.assertIs(result.outcome, ProbeAttemptOutcome.ERROR)
        self.assertIn("rc=2", result.diagnostic)

    def test_generation_mismatch_does_not_execute_ping(self):
        stale = AvailabilityProbeRequest(
            "probe",
            InterfaceIdentity("vpns00", 11),
            IPv4Address("203.0.113.24"),
        )

        result = self.executor.execute(stale, timeout_seconds=1)

        self.assertIs(result.outcome, ProbeAttemptOutcome.ERROR)
        self.assertFalse(any(call[0] == "setpriv" for call in self.runner.calls))

    def test_timeout_must_be_explicit_positive_integer(self):
        with self.assertRaises(ValueError):
            self.executor.execute(self.request, timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
