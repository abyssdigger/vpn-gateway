from __future__ import annotations

from ipaddress import IPv4Address
from types import SimpleNamespace
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import WireGuardPeerProbeOwner
from rou.probe_policy import AvailabilityProbeMechanism
from rou.probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
)
from rou.probe_runtime import (
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from rou.release1_config import ManagedWireGuardPeerConfig
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_peer_probe_executor import WireGuardPeerProbeExecutor


OWNER = WireGuardPeerProbeOwner("wg", "edge-a")
PATH = LogicalPathId("wg", 0, 0)
EP = InterfaceIdentity("wg0", 17)
ROUTE = RoutePriorityPathRoute(PATH, EP)
TARGET = IPv4Address("10.201.0.1")
PEER = ManagedWireGuardPeerConfig(
    peer_id="edge-a",
    public_key="peer-key",
    endpoint_address=IPv4Address("198.51.100.10"),
    endpoint_port=51820,
    probe_target=TARGET,
)


class Driver:
    def __init__(self, result=None):
        self.result = result or ProbeTechnicalObservation(
            ProbeTechnicalOutcome.REPLY
        )
        self.calls = []

    def execute(self, context):
        self.calls.append(context)
        return self.result


def readiness(*, confirmed=True, contexts=None, interfaces=(EP,)):
    if contexts is None:
        contexts = frozenset(
            {
                ProbeExecutionContextKey(
                    OWNER,
                    AvailabilityProbeMechanism.ICMP,
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


class WireGuardPeerProbeExecutorTests(unittest.TestCase):
    def test_exact_peer_context_executes_shared_physical_driver(self):
        driver = Driver()
        result = WireGuardPeerProbeExecutor(
            readiness(),
            driver,
        ).check(OWNER, PEER, ROUTE)

        self.assertIs(result.outcome, ProbeTechnicalOutcome.REPLY)
        self.assertEqual(len(driver.calls), 1)
        physical = driver.calls[0]
        self.assertEqual(physical.endpoint, EP)
        self.assertEqual(physical.target, TARGET)

    def test_unconfirmed_precondition_blocks_physical_io(self):
        driver = Driver()
        with self.assertRaisesRegex(RuntimeError, "not confirmed"):
            WireGuardPeerProbeExecutor(
                readiness(confirmed=False),
                driver,
            ).check(OWNER, PEER, ROUTE)
        self.assertEqual(driver.calls, [])

    def test_missing_exact_peer_context_blocks_physical_io(self):
        driver = Driver()
        with self.assertRaisesRegex(RuntimeError, "differs"):
            WireGuardPeerProbeExecutor(
                readiness(contexts=frozenset()),
                driver,
            ).check(OWNER, PEER, ROUTE)
        self.assertEqual(driver.calls, [])

    def test_stale_interface_generation_blocks_physical_io(self):
        driver = Driver()
        stale = ProbeExecutionContextKey(
            OWNER,
            AvailabilityProbeMechanism.ICMP,
            TARGET,
            InterfaceIdentity("wg0", 16),
        )
        with self.assertRaisesRegex(RuntimeError, "differs"):
            WireGuardPeerProbeExecutor(
                readiness(contexts=frozenset({stale})),
                driver,
            ).check(OWNER, PEER, ROUTE)
        self.assertEqual(driver.calls, [])

    def test_owner_peer_or_device_mismatch_is_rejected_before_io(self):
        for owner, peer, route in (
            (
                WireGuardPeerProbeOwner("wg", "edge-b"),
                PEER,
                ROUTE,
            ),
            (
                OWNER,
                ManagedWireGuardPeerConfig(
                    peer_id="edge-b",
                    public_key="other-key",
                    endpoint_address=IPv4Address("198.51.100.11"),
                    endpoint_port=51820,
                    probe_target=IPv4Address("10.201.0.2"),
                ),
                ROUTE,
            ),
            (
                OWNER,
                PEER,
                RoutePriorityPathRoute(
                    LogicalPathId("other", 0, 0),
                    EP,
                ),
            ),
        ):
            driver = Driver()
            with self.assertRaises(ValueError):
                WireGuardPeerProbeExecutor(
                    readiness(),
                    driver,
                ).check(owner, peer, route)
            self.assertEqual(driver.calls, [])


if __name__ == "__main__":
    unittest.main()
