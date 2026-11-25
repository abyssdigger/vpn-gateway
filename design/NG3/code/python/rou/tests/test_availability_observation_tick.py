from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.availability_manager import AvailabilityManager, AvailabilityManagerPolicy
from rou.availability_observation_tick import run_availability_observation_tick
from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.payload_profile import PayloadProfileRequest
from rou.network_policy_layout import WireGuardPeerProbeOwner
from rou.probe_desired import build_probe_desired_assembly
from rou.probe_plane_desired import build_probe_plane_desired_assembly
from rou.probe_local_observation import ProbeLocalComparison
from rou.probe_policy import ProbeLocalPlatform
from rou.probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
)
from rou.probe_routing_compare import ProbeRoutingComparison
from rou.probe_runtime import (
    AvailabilityProbeRuntime,
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from rou.release1_config import parse_release1_config
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_peer_probe_policy import WireGuardPeerProbeIntent


A = LogicalPathId("wg", 0, 0)
B = LogicalPathId("oc", 0, 0)
EA = InterfaceIdentity("wg0", 10)
EB = InterfaceIdentity("oc0", 20)
ROUTES = (
    RoutePriorityPathRoute(A, EA),
    RoutePriorityPathRoute(B, EB),
)
LOCAL = ProbeLocalPlatform(4242, 0x20000001)


def cfg():
    return parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[device.oc]
enabled = true
expected_interfaces = ["oc0"]
use_outbound_nat = false

[device.oc.availability_check]
mechanism = "icmp"
target = "198.51.100.20"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg", "oc"]
availability_check = "default"
""")


def baseline():
    return PayloadProfileRequest(
        "corp",
        Direction.OUTBOUND,
        (IPv4Network("10.0.0.0/8"),),
        (A, B),
    )


def exact_precondition(assembly):
    contexts = frozenset(
        ProbeExecutionContextKey(
            owner=rule.owner,
            mechanism=rule.mechanism,
            target=rule.target,
            endpoint=rule.endpoint,
        )
        for rule in assembly.probe.rules
    )
    return ProbeExecutionPrecondition(
        routing=ProbeRoutingComparison((), (), (), (), (), (), (), ()),
        local=ProbeLocalComparison(assembly.probe.local_rules, (), (), ()),
        interfaces_stable_snapshot=(EA, EB),
        contexts=contexts,
    )


class Driver:
    def __init__(self, outcomes):
        self.outcomes = dict(outcomes)
        self.contexts = []

    def check(self, context):
        self.contexts.append(context)
        return ProbeTechnicalObservation(
            self.outcomes[context.intent.owner.path_id]
        )


class AvailabilityObservationTickTests(unittest.TestCase):
    def test_one_external_tick_attempts_each_subject_once_and_reorders(self):
        config = cfg()
        p = baseline()
        assembly = build_probe_desired_assembly(
            config,
            (p,),
            ROUTES,
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        runtime = AvailabilityProbeRuntime()
        manager = AvailabilityManager(AvailabilityManagerPolicy(1, 1))
        driver = Driver({
            A: ProbeTechnicalOutcome.NO_REPLY,
            B: ProbeTechnicalOutcome.REPLY,
        })

        result = run_availability_observation_tick(
            config,
            (p,),
            ROUTES,
            assembly,
            exact_precondition(assembly),
            runtime,
            manager,
            driver,
        )

        self.assertTrue(result.attempts_enabled)
        self.assertEqual(len(result.evidence), 2)
        self.assertEqual(len(driver.contexts), 2)
        self.assertEqual(
            result.projection.effective_profiles[0].ordered_paths,
            (B, A),
        )

    def test_combined_plane_tick_executes_only_availability_owners(self):
        config = cfg()
        p = baseline()
        legacy = build_probe_desired_assembly(
            config,
            (p,),
            ROUTES,
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        peer = WireGuardPeerProbeIntent(
            WireGuardPeerProbeOwner("wg", "edge-a"),
            IPv4Address("10.201.0.1"),
            ROUTES[0],
        )
        assembly = build_probe_plane_desired_assembly(
            (p,),
            legacy.intents,
            (peer,),
            (),
            ROUTES,
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        runtime = AvailabilityProbeRuntime()
        driver = Driver({
            A: ProbeTechnicalOutcome.REPLY,
            B: ProbeTechnicalOutcome.REPLY,
        })

        result = run_availability_observation_tick(
            config,
            (p,),
            ROUTES,
            assembly,
            exact_precondition(assembly),
            runtime,
            AvailabilityManager(AvailabilityManagerPolicy(1, 1)),
            driver,
        )

        self.assertTrue(result.attempts_enabled)
        self.assertEqual(len(result.evidence), 2)
        self.assertEqual(len(driver.contexts), 2)
        self.assertTrue(
            all(
                hasattr(context.intent.owner, "path_id")
                for context in driver.contexts
            )
        )
        self.assertEqual(
            {context.intent.owner for context in runtime.current_contexts},
            {intent.owner for intent in assembly.availability_intents},
        )

    def test_unconfirmed_precondition_runs_no_probe_and_fabricates_no_failure(self):
        config = cfg()
        p = baseline()
        assembly = build_probe_desired_assembly(
            config,
            (p,),
            ROUTES,
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        ready = exact_precondition(assembly)
        blocked = ProbeExecutionPrecondition(
            routing=ready.routing,
            local=ProbeLocalComparison(
                (),
                (assembly.probe.local_rules[0],),
                (),
                (),
            ),
            interfaces_stable_snapshot=ready.interfaces_stable_snapshot,
            contexts=ready.contexts,
        )
        driver = Driver({
            A: ProbeTechnicalOutcome.NO_REPLY,
            B: ProbeTechnicalOutcome.NO_REPLY,
        })

        result = run_availability_observation_tick(
            config,
            (p,),
            ROUTES,
            assembly,
            blocked,
            AvailabilityProbeRuntime(),
            AvailabilityManager(AvailabilityManagerPolicy(1, 1)),
            driver,
        )

        self.assertFalse(result.attempts_enabled)
        self.assertEqual(result.evidence, ())
        self.assertEqual(driver.contexts, [])
        self.assertEqual(
            result.projection.effective_profiles[0].ordered_paths,
            (A, B),
        )

    def test_local_error_produces_no_evidence_state_change(self):
        config = cfg()
        p = baseline()
        assembly = build_probe_desired_assembly(
            config,
            (p,),
            ROUTES,
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        driver = Driver({
            A: ProbeTechnicalOutcome.LOCAL_ERROR,
            B: ProbeTechnicalOutcome.REPLY,
        })

        # Driver helper cannot attach diagnostics, so use a dedicated variant.
        class LocalErrorDriver(Driver):
            def check(self, context):
                self.contexts.append(context)
                if context.intent.owner.path_id == A:
                    return ProbeTechnicalObservation(
                        ProbeTechnicalOutcome.LOCAL_ERROR,
                        "local execution failure",
                    )
                return ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)

        result = run_availability_observation_tick(
            config,
            (p,),
            ROUTES,
            assembly,
            exact_precondition(assembly),
            AvailabilityProbeRuntime(),
            AvailabilityManager(AvailabilityManagerPolicy(1, 1)),
            LocalErrorDriver(driver.outcomes),
        )

        self.assertEqual(
            result.projection.effective_profiles[0].ordered_paths,
            (A, B),
        )


if __name__ == "__main__":
    unittest.main()
