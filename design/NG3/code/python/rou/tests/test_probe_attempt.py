from __future__ import annotations

from ipaddress import IPv4Address
from types import SimpleNamespace
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.probe_attempt import (
    ProbeAttemptError,
    execute_probe_attempt_once,
)
from rou.probe_policy import AvailabilityProbeIntent
from rou.probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
)
from rou.probe_runtime import (
    AvailabilityProbeRuntime,
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.availability_confirmation import AvailabilityOutcome


PATH = LogicalPathId("device", 0, 0)
EP = InterfaceIdentity("vpn0", 10)
TARGET = IPv4Address("198.51.100.7")
TARGET2 = IPv4Address("203.0.113.9")
OWNER = ProbePolicyOwner("corp", PATH)


class FakeDriver:
    def __init__(self, observation, before_return=None):
        self.observation = observation
        self.before_return = before_return
        self.calls = []

    def check(self, context):
        self.calls.append(context)
        if self.before_return is not None:
            self.before_return()
        return self.observation


def intent(target=TARGET):
    return AvailabilityProbeIntent(OWNER, target)


def runtime():
    value = AvailabilityProbeRuntime()
    value.configure(
        (intent(),),
        (RoutePriorityPathRoute(PATH, EP),),
    )
    return value


def readiness(*, confirmed=True, contexts=None, interfaces=(EP,)):
    if contexts is None:
        contexts = frozenset(
            {
                ProbeExecutionContextKey(
                    OWNER,
                    intent().mechanism,
                    TARGET,
                    EP,
                )
            }
        )
    return ProbeExecutionPrecondition(
        routing=SimpleNamespace(confirmed=confirmed),
        local=SimpleNamespace(desired_confirmed=True),
        interfaces_stable_snapshot=interfaces,
        contexts=contexts,
    )


class ProbeAttemptTests(unittest.TestCase):
    def test_confirmed_attempt_returns_current_positive_evidence(self):
        value = runtime()
        driver = FakeDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
        )
        result = execute_probe_attempt_once(
            value,
            OWNER,
            readiness(),
            driver,
        )
        self.assertEqual(result.outcome, AvailabilityOutcome.POSITIVE)
        self.assertEqual(len(driver.calls), 1)

    def test_unconfirmed_precondition_blocks_driver_io(self):
        value = runtime()
        driver = FakeDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
        )
        with self.assertRaisesRegex(
            ProbeAttemptError,
            "not confirmed",
        ):
            execute_probe_attempt_once(
                value,
                OWNER,
                readiness(confirmed=False),
                driver,
            )
        self.assertEqual(driver.calls, [])

    def test_owner_must_belong_to_confirmed_precondition(self):
        value = runtime()
        driver = FakeDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
        )
        with self.assertRaisesRegex(
            ProbeAttemptError,
            "absent",
        ):
            execute_probe_attempt_once(
                value,
                OWNER,
                readiness(contexts=frozenset()),
                driver,
            )
        self.assertEqual(driver.calls, [])

    def test_changed_target_cannot_reuse_old_readiness(self):
        value = runtime()
        old_readiness = readiness()
        value.configure(
            (intent(TARGET2),),
            (RoutePriorityPathRoute(PATH, EP),),
        )
        driver = FakeDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
        )
        with self.assertRaisesRegex(
            ProbeAttemptError,
            "context differs",
        ):
            execute_probe_attempt_once(
                value,
                OWNER,
                old_readiness,
                driver,
            )
        self.assertEqual(driver.calls, [])

    def test_context_endpoint_must_belong_to_readiness_snapshot(self):
        value = runtime()
        driver = FakeDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)
        )
        with self.assertRaisesRegex(
            ProbeAttemptError,
            "endpoint is absent",
        ):
            execute_probe_attempt_once(
                value,
                OWNER,
                readiness(interfaces=(InterfaceIdentity("vpn1", 20),)),
                driver,
            )
        self.assertEqual(driver.calls, [])

    def test_reconfiguration_during_driver_execution_rejects_late_result(self):
        value = runtime()

        def reconfigure():
            value.configure(
                (intent(TARGET2),),
                (RoutePriorityPathRoute(PATH, EP),),
            )

        driver = FakeDriver(
            ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY),
            before_return=reconfigure,
        )
        result = execute_probe_attempt_once(
            value,
            OWNER,
            readiness(),
            driver,
        )
        self.assertIsNone(result)
        self.assertEqual(len(driver.calls), 1)


if __name__ == "__main__":
    unittest.main()
