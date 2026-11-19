from __future__ import annotations

from ipaddress import IPv4Address
import unittest

from rou.binding import LogicalPathId
from rou.icmp_probe_driver import (
    IcmpProbeExecutionPolicy,
    LinuxIcmpProbeDriver,
    ProbeCommandError,
    ProbeCommandResult,
)
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_policy import AvailabilityProbeIntent
from rou.probe_runtime import (
    AvailabilityProbeAgent,
    ProbeTechnicalOutcome,
)


PATH = LogicalPathId("device", 0, 0)
EP = InterfaceIdentity("vpn0", 10)
TARGET = IPv4Address("198.51.100.7")


class FakeRunner:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def run(self, argv, *, timeout_seconds):
        self.calls.append((tuple(argv), timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.result


def context():
    agent = AvailabilityProbeAgent()
    return agent.configure(
        AvailabilityProbeIntent(
            ProbePolicyOwner("corp", PATH),
            TARGET,
        ),
        EP,
    )


def driver(runner):
    return LinuxIcmpProbeDriver(
        runner,
        "managed",
        4242,
        IcmpProbeExecutionPolicy(
            reply_timeout_seconds=3,
            process_grace_seconds=2,
        ),
    )


class IcmpProbeDriverTests(unittest.TestCase):
    def test_exp067_command_shape_uses_dedicated_uid_and_numeric_target(self):
        runner = FakeRunner(ProbeCommandResult(0, "ok", ""))
        result = driver(runner).check(context())
        self.assertIs(result.outcome, ProbeTechnicalOutcome.REPLY)
        self.assertEqual(
            runner.calls,
            [
                (
                    (
                        "ip", "netns", "exec", "managed",
                        "setpriv",
                        "--reuid", "4242",
                        "--regid", "4242",
                        "--clear-groups",
                        "ping",
                        "-n",
                        "-I", "vpn0",
                        "-c", "1",
                        "-W", "3",
                        "198.51.100.7",
                    ),
                    5,
                )
            ],
        )

    def test_exit_zero_maps_to_reply(self):
        value = driver(
            FakeRunner(ProbeCommandResult(0, "reply", ""))
        ).check(context())
        self.assertIs(value.outcome, ProbeTechnicalOutcome.REPLY)

    def test_exit_one_maps_to_no_reply(self):
        value = driver(
            FakeRunner(ProbeCommandResult(1, "100% packet loss", ""))
        ).check(context())
        self.assertIs(value.outcome, ProbeTechnicalOutcome.NO_REPLY)

    def test_other_exit_maps_to_local_error(self):
        value = driver(
            FakeRunner(
                ProbeCommandResult(
                    2,
                    "",
                    "ping: connect: Network is unreachable\n",
                )
            )
        ).check(context())
        self.assertIs(
            value.outcome,
            ProbeTechnicalOutcome.LOCAL_ERROR,
        )
        self.assertEqual(
            value.diagnostic,
            "ping: connect: Network is unreachable",
        )

    def test_runner_execution_error_maps_to_local_error(self):
        value = driver(
            FakeRunner(
                error=ProbeCommandError("process deadline exceeded")
            )
        ).check(context())
        self.assertIs(
            value.outcome,
            ProbeTechnicalOutcome.LOCAL_ERROR,
        )
        self.assertEqual(
            value.diagnostic,
            "process deadline exceeded",
        )

    def test_local_error_diagnostic_is_bounded(self):
        value = driver(
            FakeRunner(
                ProbeCommandResult(2, "", "x" * 2000)
            )
        ).check(context())
        self.assertEqual(len(value.diagnostic), 1024)

    def test_execution_policy_rejects_non_positive_deadlines(self):
        for reply, grace in ((0, 1), (1, 0), (-1, 1)):
            with self.subTest(reply=reply, grace=grace):
                with self.assertRaises(ValueError):
                    IcmpProbeExecutionPolicy(
                        reply_timeout_seconds=reply,
                        process_grace_seconds=grace,
                    )


if __name__ == "__main__":
    unittest.main()
