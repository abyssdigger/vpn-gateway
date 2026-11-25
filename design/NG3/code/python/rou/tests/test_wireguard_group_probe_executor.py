from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
from types import SimpleNamespace
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import WireGuardGroupProbeOwner
from rou.probe_policy import AvailabilityProbeMechanism
from rou.probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
)
from rou.probe_runtime import (
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from rou.release1_config import (
    AvailabilityCheckConfig,
    ManagedWireGuardGroupConfig,
    WireGuardPeerMembershipConfig,
)
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_group_probe_executor import WireGuardGroupProbeExecutor


PATH = LogicalPathId("wg", 0, 0)
EP = InterfaceIdentity("wg0", 17)
ROUTE = RoutePriorityPathRoute(PATH, EP)
OWNER = WireGuardGroupProbeOwner("corp", "wg")
TARGET = IPv4Address("10.77.0.1")


def group(*, target=TARGET):
    return ManagedWireGuardGroupConfig(
        profile_id="corp",
        device_id="wg",
        prefixes=(IPv4Network("10.77.0.0/24"),),
        peer_memberships=(WireGuardPeerMembershipConfig("edge-a"),),
        availability_check=AvailabilityCheckConfig("icmp", target),
    )


def precondition(*, contexts, confirmed=True):
    return ProbeExecutionPrecondition(
        routing=SimpleNamespace(confirmed=confirmed),
        local=SimpleNamespace(desired_confirmed=confirmed),
        interfaces_stable_snapshot=(EP,),
        contexts=frozenset(contexts),
    )


class Driver:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or ProbeTechnicalObservation(
            ProbeTechnicalOutcome.REPLY
        )

    def execute(self, context):
        self.calls.append(context)
        return self.result


class WireGuardGroupProbeExecutorTests(unittest.TestCase):
    def test_exact_group_context_executes_shared_physical_driver(self):
        key = ProbeExecutionContextKey(
            OWNER,
            AvailabilityProbeMechanism.ICMP,
            TARGET,
            EP,
        )
        driver = Driver()
        executor = WireGuardGroupProbeExecutor(
            precondition=precondition(contexts={key}),
            driver=driver,
        )

        result = executor.check(OWNER, group(), ROUTE)

        self.assertIs(result.outcome, ProbeTechnicalOutcome.REPLY)
        self.assertEqual(len(driver.calls), 1)
        self.assertEqual(driver.calls[0].endpoint, EP)
        self.assertEqual(driver.calls[0].target, TARGET)

    def test_missing_exact_group_context_blocks_physical_io(self):
        driver = Driver()
        executor = WireGuardGroupProbeExecutor(
            precondition=precondition(contexts=set()),
            driver=driver,
        )
        with self.assertRaisesRegex(RuntimeError, "differs"):
            executor.check(OWNER, group(), ROUTE)
        self.assertEqual(driver.calls, [])

    def test_owner_or_device_mismatch_is_rejected_before_io(self):
        key = ProbeExecutionContextKey(
            OWNER,
            AvailabilityProbeMechanism.ICMP,
            TARGET,
            EP,
        )
        driver = Driver()
        executor = WireGuardGroupProbeExecutor(
            precondition=precondition(contexts={key}),
            driver=driver,
        )
        with self.assertRaisesRegex(ValueError, "differs from requested"):
            executor.check(
                WireGuardGroupProbeOwner("other", "wg"),
                group(),
                ROUTE,
            )
        with self.assertRaisesRegex(ValueError, "current path Device"):
            executor.check(
                WireGuardGroupProbeOwner("corp", "other"),
                ManagedWireGuardGroupConfig(
                    profile_id="corp",
                    device_id="other",
                    prefixes=(IPv4Network("10.77.0.0/24"),),
                    peer_memberships=(WireGuardPeerMembershipConfig("edge-a"),),
                    availability_check=AvailabilityCheckConfig("icmp", TARGET),
                ),
                ROUTE,
            )
        self.assertEqual(driver.calls, [])

    def test_unconfirmed_precondition_blocks_physical_io(self):
        key = ProbeExecutionContextKey(
            OWNER,
            AvailabilityProbeMechanism.ICMP,
            TARGET,
            EP,
        )
        driver = Driver()
        executor = WireGuardGroupProbeExecutor(
            precondition=precondition(contexts={key}, confirmed=False),
            driver=driver,
        )
        with self.assertRaisesRegex(RuntimeError, "not confirmed"):
            executor.check(OWNER, group(), ROUTE)
        self.assertEqual(driver.calls, [])

    def test_target_outside_group_prefixes_is_rejected_before_io(self):
        outside = IPv4Address("10.88.0.1")
        key = ProbeExecutionContextKey(
            OWNER,
            AvailabilityProbeMechanism.ICMP,
            outside,
            EP,
        )
        driver = Driver()
        executor = WireGuardGroupProbeExecutor(
            precondition=precondition(contexts={key}),
            driver=driver,
        )
        with self.assertRaisesRegex(ValueError, "outside group prefixes"):
            executor.check(OWNER, group(target=outside), ROUTE)
        self.assertEqual(driver.calls, [])


if __name__ == "__main__":
    unittest.main()
