from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.availability_collector import (
    AvailabilityGoodNews,
    AvailabilityHysteresisPolicy,
    AvailabilityPriorityChannel,
    AvailabilityTick,
    ProfileAvailabilityAssignment,
)
from rou.availability_probe_manager import AvailabilityProbeManager
from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    ActionResult,
    NetworkRulesSpec,
    NetworkRulesState,
    StateKnowledge,
)
from rou.payload_rules import (
    PayloadDirection,
    PayloadPath,
    PayloadProfileRequest,
    PayloadTrafficStateRequest,
)
from rou.payload_traffic_manager import PayloadTrafficManager
from rou.probe_rules import AvailabilityProbeRequest, AvailabilityProbeSetRequest
from rou.runtime_assembly import (
    AvailabilityConfigFanout,
    AvailabilityGoodNewsPort,
    AvailabilityPriorityConfigCalculator,
    AvailabilityTickPort,
    ProbeExecutionPlanPort,
)


A = InterfaceIdentity("vpns00", 10)
B = InterfaceIdentity("vpns01", 11)


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, value):
        self.events.append(value)


class FakeAdapter:
    def __init__(self):
        self.state = NetworkRulesState(
            StateKnowledge.UNKNOWN,
            None,
            fresh=False,
        )
        self.apply_specs = []
        self.apply_hook = None

    def apply(self, owner, spec):
        self.apply_specs.append(spec)
        if self.apply_hook is not None:
            self.apply_hook(spec)
        self.state = NetworkRulesState(
            StateKnowledge.KNOWN,
            spec,
            fresh=True,
        )
        return ActionResult(True)

    def renew_state(self, owner):
        return ActionResult(True)

    def get_last_state(self, owner):
        return self.state

    def cleanup(self, owner):
        return ActionResult(True)


class PlanConsumer:
    def __init__(self):
        self.plans = []

    def update_plan(self, plan):
        self.plans.append(plan)


def probe(
    channel_id,
    path,
    target,
    *,
    enabled=True,
    interval=10,
    failure=2,
    recovery=2,
):
    return AvailabilityProbeRequest(
        channel_id,
        path,
        IPv4Address(target),
        enabled=enabled,
        interval_seconds=interval,
        hysteresis=AvailabilityHysteresisPolicy(failure, recovery),
    )


def payload_request(*paths):
    return PayloadTrafficStateRequest(
        (
            PayloadProfileRequest(
                "corp",
                PayloadDirection.OUTBOUND,
                (IPv4Network("10.0.0.0/8"),),
                tuple(PayloadPath(path) for path in paths),
            ),
        )
    )


class AvailabilityPriorityConfigCalculatorTests(unittest.TestCase):
    def test_projects_only_payload_priority_fields(self):
        probes = AvailabilityProbeSetRequest(
            (
                probe(
                    "a",
                    A,
                    "203.0.113.10",
                    interval=30,
                    failure=4,
                    recovery=3,
                ),
            )
        )
        assignments = (
            ProfileAvailabilityAssignment("corp", ("a",)),
        )

        config = AvailabilityPriorityConfigCalculator().calculate(
            probes,
            assignments,
        )

        self.assertEqual(
            config.channels,
            (
                AvailabilityPriorityChannel(
                    "a",
                    A,
                    True,
                    AvailabilityHysteresisPolicy(4, 3),
                ),
            ),
        )
        channel = config.channels[0]
        self.assertFalse(hasattr(channel, "target"))
        self.assertFalse(hasattr(channel, "mechanism"))
        self.assertFalse(hasattr(channel, "interval_seconds"))

    def test_disabled_probe_remains_disabled_priority_channel(self):
        probes = AvailabilityProbeSetRequest(
            (
                probe(
                    "a",
                    A,
                    "203.0.113.10",
                    enabled=False,
                ),
            )
        )

        config = AvailabilityPriorityConfigCalculator().calculate(
            probes,
            (ProfileAvailabilityAssignment("corp", ("a",)),),
        )

        self.assertFalse(config.channels[0].enabled)


class RuntimeAssemblyPortTests(unittest.TestCase):
    def setUp(self):
        self.payload_adapter = FakeAdapter()
        self.payload_publisher = RecordingPublisher()
        self.payload_manager = PayloadTrafficManager(
            self.payload_adapter,
            self.payload_publisher,
        )
        self.payload_manager.handle_request(payload_request(A, B))

    def test_plan_port_forwards_plan_and_quiesce(self):
        consumer = PlanConsumer()
        port = ProbeExecutionPlanPort(consumer)

        port.publish(None)

        self.assertEqual(consumer.plans, [None])

    def test_good_news_and_tick_ports_use_payload_manager_boundary(self):
        policy = AvailabilityHysteresisPolicy(1, 1)
        channel = AvailabilityPriorityChannel("a", A, True, policy)
        self.payload_manager.configure_availability(
            AvailabilityPriorityConfigCalculator().calculate(
                AvailabilityProbeSetRequest(
                    (
                        probe(
                            "a",
                            A,
                            "203.0.113.10",
                            failure=1,
                            recovery=1,
                        ),
                    )
                ),
                (ProfileAvailabilityAssignment("corp", ("a",)),),
            )
        )

        tick = AvailabilityTickPort(self.payload_manager)
        good = AvailabilityGoodNewsPort(self.payload_manager)

        tick.publish(AvailabilityTick(channel))
        self.assertEqual(
            self.payload_adapter.state.rules.routing_domains[0].ordered_paths,
            (B, A),
        )

        good.publish(AvailabilityGoodNews(channel))
        self.assertEqual(
            self.payload_adapter.state.rules.routing_domains[0].ordered_paths,
            (A, B),
        )

    def test_config_fanout_installs_payload_priority_before_probe_rules(self):
        plan_consumer = PlanConsumer()
        probe_adapter = FakeAdapter()
        probe_manager = AvailabilityProbeManager(
            probe_adapter,
            execution_plan_publisher=ProbeExecutionPlanPort(plan_consumer),
        )
        fanout = AvailabilityConfigFanout(
            probe_manager,
            self.payload_manager,
        )
        probes = AvailabilityProbeSetRequest(
            (probe("a", A, "203.0.113.10"),)
        )
        assignments = (
            ProfileAvailabilityAssignment("corp", ("a",)),
        )

        observed_prefixes = []

        def during_probe_apply(_spec):
            observed_prefixes.append(
                self.payload_adapter.state.rules.routing_domains[
                    0
                ].preferred_prefix_length
            )

        probe_adapter.apply_hook = during_probe_apply

        fanout.apply(probes, assignments)

        self.assertEqual(observed_prefixes, [2])
        self.assertEqual(len(plan_consumer.plans), 1)
        self.assertEqual(
            plan_consumer.plans[0].channels[0].priority,
            AvailabilityPriorityChannel(
                "a",
                A,
                True,
                AvailabilityHysteresisPolicy(2, 2),
            ),
        )

    def test_stale_old_priority_descriptor_is_rejected_after_fanout(self):
        probe_adapter = FakeAdapter()
        probe_manager = AvailabilityProbeManager(probe_adapter)
        fanout = AvailabilityConfigFanout(
            probe_manager,
            self.payload_manager,
        )
        first = AvailabilityProbeSetRequest(
            (probe("a", A, "203.0.113.10", failure=2),)
        )
        assignment = (
            ProfileAvailabilityAssignment("corp", ("a",)),
        )
        fanout.apply(first, assignment)

        stale = AvailabilityPriorityChannel(
            "a",
            A,
            True,
            AvailabilityHysteresisPolicy(2, 2),
        )

        changed = AvailabilityProbeSetRequest(
            (probe("a", A, "203.0.113.10", failure=5),)
        )
        fanout.apply(changed, assignment)

        self.assertFalse(
            self.payload_manager.handle_availability_good_news(
                AvailabilityGoodNews(stale)
            )
        )


if __name__ == "__main__":
    unittest.main()
