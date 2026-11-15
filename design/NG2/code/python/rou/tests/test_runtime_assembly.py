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
from rou.runtime_assembly import (
    AvailabilityConfigFanout,
    AvailabilityGoodNewsPort,
    AvailabilityPriorityConfigCalculator,
    AvailabilityProbeSetCalculator,
    AvailabilityTickPort,
    ProbeExecutionPlanPort,
    RuntimeAvailabilityChannel,
    RuntimeAvailabilityConfig,
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


def runtime_channel(
    channel_id,
    path,
    target,
    *,
    enabled=True,
    interval=10,
    failure=2,
    recovery=2,
):
    return RuntimeAvailabilityChannel(
        channel_id,
        path,
        IPv4Address(target),
        enabled=enabled,
        interval_seconds=interval,
        hysteresis=AvailabilityHysteresisPolicy(failure, recovery),
    )


def runtime_config(*channels):
    return RuntimeAvailabilityConfig(
        tuple(channels),
        (ProfileAvailabilityAssignment("corp", tuple(
            item.channel_id for item in channels
        )),),
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


class AvailabilityProjectionCalculatorTests(unittest.TestCase):
    def test_priority_projection_contains_only_payload_fields(self):
        source = runtime_config(
            runtime_channel(
                "a",
                A,
                "203.0.113.10",
                interval=30,
                failure=4,
                recovery=3,
            )
        )

        config = AvailabilityPriorityConfigCalculator().calculate(source)

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

    def test_probe_projection_keeps_physical_fields_independently(self):
        source = runtime_config(
            runtime_channel(
                "a",
                A,
                "203.0.113.10",
                interval=30,
                failure=4,
                recovery=3,
            )
        )

        probes = AvailabilityProbeSetCalculator().calculate(source)

        self.assertEqual(len(probes.probes), 1)
        item = probes.probes[0]
        self.assertEqual(item.probe_id, "a")
        self.assertEqual(item.path, A)
        self.assertEqual(item.target, IPv4Address("203.0.113.10"))
        self.assertEqual(item.interval_seconds, 30)
        self.assertEqual(
            item.hysteresis,
            AvailabilityHysteresisPolicy(4, 3),
        )

    def test_disabled_channel_is_disabled_in_both_projections(self):
        source = runtime_config(
            runtime_channel(
                "a",
                A,
                "203.0.113.10",
                enabled=False,
            )
        )

        priority = AvailabilityPriorityConfigCalculator().calculate(source)
        probes = AvailabilityProbeSetCalculator().calculate(source)

        self.assertFalse(priority.channels[0].enabled)
        self.assertFalse(probes.probes[0].enabled)


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
                runtime_config(
                    runtime_channel(
                        "a",
                        A,
                        "203.0.113.10",
                        failure=1,
                        recovery=1,
                    )
                )
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
        source = runtime_config(
            runtime_channel("a", A, "203.0.113.10")
        )

        observed_prefixes = []

        def during_probe_apply(_spec):
            observed_prefixes.append(
                self.payload_adapter.state.rules.routing_domains[
                    0
                ].preferred_prefix_length
            )

        probe_adapter.apply_hook = during_probe_apply

        fanout.apply(source)

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
        first = runtime_config(
            runtime_channel("a", A, "203.0.113.10", failure=2)
        )
        fanout.apply(first)

        stale = AvailabilityPriorityChannel(
            "a",
            A,
            True,
            AvailabilityHysteresisPolicy(2, 2),
        )

        changed = runtime_config(
            runtime_channel("a", A, "203.0.113.10", failure=5)
        )
        fanout.apply(changed)

        self.assertFalse(
            self.payload_manager.handle_availability_good_news(
                AvailabilityGoodNews(stale)
            )
        )


if __name__ == "__main__":
    unittest.main()
