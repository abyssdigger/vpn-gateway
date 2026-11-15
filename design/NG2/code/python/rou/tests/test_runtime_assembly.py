from ipaddress import IPv4Address, IPv4Network
import time
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
from rou.linux_driver import LinuxDriverResult
from rou.linux_probe_execution import (
    ProbeExecutionHealth,
    ProbeSendResult,
)
from rou.runtime_assembly import (
    AvailabilityConfigFanout,
    AvailabilityGoodNewsPort,
    AvailabilityPriorityConfigCalculator,
    AvailabilityProbeSetCalculator,
    AvailabilityTickPort,
    ProbeExecutionPlanPort,
    RuntimeAvailabilityChannel,
    RuntimeAvailabilityConfig,
    LinuxNetworkPolicyRuntimeBootstrapResult,
    bootstrap_linux_network_policy_runtime,
    build_linux_availability_runtime,
    build_linux_network_policy_runtime,
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
        self.cleanup_calls = 0

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
        self.cleanup_calls += 1
        return ActionResult(True)


class FakeSendDriver:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute_send(self, path, target, *, timeout_seconds):
        self.calls.append((path, target, timeout_seconds))
        return self.result


class FakeBootstrapBackend:
    def __init__(self, result):
        self.result = result
        self.close_calls = 0

    def close_forwarding_verified(self):
        self.close_calls += 1
        return self.result


class OwnerScopedFakeAdapter:
    def __init__(self):
        self.states = {}
        self.apply_calls = []
        self.renew_calls = []
        self.cleanup_calls = []
        self.cleanup_results = {}
        self.cleanup_raise = set()

    def apply(self, owner, spec):
        self.apply_calls.append((owner, spec))
        self.states[owner] = NetworkRulesState(
            StateKnowledge.KNOWN,
            spec,
            fresh=True,
        )
        return ActionResult(True)

    def renew_state(self, owner):
        self.renew_calls.append(owner)
        if owner not in self.states:
            self.states[owner] = NetworkRulesState(
                StateKnowledge.KNOWN,
                NetworkRulesSpec(),
                fresh=True,
            )
        return ActionResult(True)

    def get_last_state(self, owner):
        return self.states.get(
            owner,
            NetworkRulesState(
                StateKnowledge.UNKNOWN,
                None,
                fresh=False,
            ),
        )

    def cleanup(self, owner):
        self.cleanup_calls.append(owner)
        self.states.pop(owner, None)
        if owner in self.cleanup_raise:
            raise RuntimeError("cleanup boom")
        return self.cleanup_results.get(owner, ActionResult(True))


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



class LinuxAvailabilityRuntimeAssemblyTests(unittest.TestCase):
    def test_builder_wires_probe_reply_directly_back_to_payload_priority(self):
        payload_adapter = FakeAdapter()
        payload_manager = PayloadTrafficManager(
            payload_adapter,
            RecordingPublisher(),
        )
        payload_manager.handle_request(payload_request(A, B))

        probe_adapter = FakeAdapter()
        diagnostics = RecordingPublisher()
        driver = FakeSendDriver(ProbeSendResult(True))
        runtime = build_linux_availability_runtime(
            probe_adapter,
            payload_manager,
            driver,
            diagnostics,
            timeout_seconds=1,
            clock=lambda: 100.0,
        )
        source = runtime_config(
            runtime_channel(
                "a",
                A,
                "203.0.113.10",
                failure=1,
                recovery=1,
            )
        )
        runtime.configure(source)

        channel = AvailabilityPriorityConfigCalculator().calculate(
            source
        ).channels[0]
        payload_manager.handle_availability_tick(
            AvailabilityTick(channel)
        )
        self.assertEqual(
            payload_adapter.state.rules.routing_domains[0].ordered_paths,
            (B, A),
        )

        runtime.agent.process_due(100.0)

        deadline = time.monotonic() + 2
        while (
            payload_adapter.state.rules.routing_domains[0].ordered_paths
            != (A, B)
            and time.monotonic() < deadline
        ):
            time.sleep(0.005)

        self.assertEqual(
            payload_adapter.state.rules.routing_domains[0].ordered_paths,
            (A, B),
        )
        self.assertEqual(len(driver.calls), 1)
        self.assertTrue(
            any(
                item.health is ProbeExecutionHealth.READY
                for item in diagnostics.events
            )
        )

    def test_stop_quiesces_agent_and_cleans_probe_rules(self):
        payload_manager = PayloadTrafficManager(
            FakeAdapter(),
            RecordingPublisher(),
        )
        payload_manager.handle_request(payload_request(A))

        probe_adapter = FakeAdapter()
        driver = FakeSendDriver(ProbeSendResult(False))
        runtime = build_linux_availability_runtime(
            probe_adapter,
            payload_manager,
            driver,
            RecordingPublisher(),
            timeout_seconds=1,
            clock=lambda: 100.0,
        )
        runtime.configure(
            runtime_config(
                runtime_channel("a", A, "203.0.113.10")
            )
        )
        runtime.start()

        result = runtime.stop()
        calls_after_stop = len(driver.calls)

        self.assertTrue(result.success)
        self.assertEqual(probe_adapter.cleanup_calls, 1)

        runtime.agent.process_due(100.0)
        self.assertEqual(len(driver.calls), calls_after_stop)



class LinuxNetworkPolicyRuntimeTests(unittest.TestCase):
    def test_builder_uses_one_adapter_with_distinct_manager_owners(self):
        adapter = OwnerScopedFakeAdapter()
        payload_events = RecordingPublisher()
        diagnostics = RecordingPublisher()
        driver = FakeSendDriver(ProbeSendResult(False))

        runtime = build_linux_network_policy_runtime(
            adapter,
            payload_events,
            driver,
            diagnostics,
            timeout_seconds=1,
            clock=lambda: 100.0,
        )

        runtime.handle_payload_request(payload_request(A, B))
        runtime.configure_availability(
            runtime_config(
                runtime_channel("a", A, "203.0.113.10")
            )
        )

        owners = [owner for owner, _spec in adapter.apply_calls]
        self.assertIn(runtime.payload_manager, owners)
        self.assertIn(runtime.availability.probe_manager, owners)
        self.assertIsNot(
            runtime.payload_manager,
            runtime.availability.probe_manager,
        )

    def test_audit_refreshes_both_network_policy_owners(self):
        adapter = OwnerScopedFakeAdapter()
        runtime = build_linux_network_policy_runtime(
            adapter,
            RecordingPublisher(),
            FakeSendDriver(ProbeSendResult(False)),
            RecordingPublisher(),
            timeout_seconds=1,
            clock=lambda: 100.0,
        )
        runtime.handle_payload_request(payload_request(A))
        runtime.configure_availability(
            runtime_config(
                runtime_channel("a", A, "203.0.113.10")
            )
        )
        adapter.renew_calls.clear()

        runtime.audit()

        self.assertEqual(
            set(adapter.renew_calls),
            {
                runtime.payload_manager,
                runtime.availability.probe_manager,
            },
        )

    def test_stop_reports_probe_cleanup_failure_but_still_cleans_payload(self):
        adapter = OwnerScopedFakeAdapter()
        runtime = build_linux_network_policy_runtime(
            adapter,
            RecordingPublisher(),
            FakeSendDriver(ProbeSendResult(False)),
            RecordingPublisher(),
            timeout_seconds=1,
            clock=lambda: 100.0,
        )
        runtime.handle_payload_request(payload_request(A))
        runtime.configure_availability(
            runtime_config(
                runtime_channel("a", A, "203.0.113.10")
            )
        )
        adapter.cleanup_results[
            runtime.availability.probe_manager
        ] = ActionResult(False, "probe cleanup failed")

        result = runtime.stop()

        self.assertFalse(result.success)
        self.assertFalse(result.probe_cleanup.success)
        self.assertTrue(result.payload_cleanup.success)
        self.assertIn(runtime.payload_manager, adapter.cleanup_calls)

    def test_unexpected_probe_cleanup_exception_still_attempts_payload_cleanup(self):
        adapter = OwnerScopedFakeAdapter()
        runtime = build_linux_network_policy_runtime(
            adapter,
            RecordingPublisher(),
            FakeSendDriver(ProbeSendResult(False)),
            RecordingPublisher(),
            timeout_seconds=1,
            clock=lambda: 100.0,
        )
        runtime.handle_payload_request(payload_request(A))
        runtime.configure_availability(
            runtime_config(
                runtime_channel("a", A, "203.0.113.10")
            )
        )
        adapter.cleanup_raise.add(runtime.availability.probe_manager)

        with self.assertRaisesRegex(RuntimeError, "cleanup boom"):
            runtime.stop()

        self.assertIn(runtime.payload_manager, adapter.cleanup_calls)

    def test_stop_cleans_both_manager_owners(self):
        adapter = OwnerScopedFakeAdapter()
        runtime = build_linux_network_policy_runtime(
            adapter,
            RecordingPublisher(),
            FakeSendDriver(ProbeSendResult(False)),
            RecordingPublisher(),
            timeout_seconds=1,
            clock=lambda: 100.0,
        )
        runtime.handle_payload_request(payload_request(A))
        runtime.configure_availability(
            runtime_config(
                runtime_channel("a", A, "203.0.113.10")
            )
        )

        result = runtime.stop()

        self.assertTrue(result.success)
        self.assertEqual(
            set(adapter.cleanup_calls),
            {
                runtime.payload_manager,
                runtime.availability.probe_manager,
            },
        )



class LinuxNetworkPolicyBootstrapTests(unittest.TestCase):
    def test_runtime_is_exposed_only_after_verified_protective_close(self):
        backend = FakeBootstrapBackend(LinuxDriverResult(True))

        result = bootstrap_linux_network_policy_runtime(
            backend,
            local_interface="host0",
            payload_publisher=RecordingPublisher(),
            probe_driver=FakeSendDriver(ProbeSendResult(False)),
            diagnostic_publisher=RecordingPublisher(),
            timeout_seconds=1,
            clock=lambda: 100.0,
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.runtime)
        self.assertEqual(backend.close_calls, 1)

    def test_failed_protective_close_exposes_no_runtime(self):
        backend = FakeBootstrapBackend(
            LinuxDriverResult(False, "cannot prove forwarding closed")
        )

        result = bootstrap_linux_network_policy_runtime(
            backend,
            local_interface="host0",
            payload_publisher=RecordingPublisher(),
            probe_driver=FakeSendDriver(ProbeSendResult(False)),
            diagnostic_publisher=RecordingPublisher(),
            timeout_seconds=1,
            clock=lambda: 100.0,
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.runtime)
        self.assertEqual(
            result.diagnostic,
            "cannot prove forwarding closed",
        )
        self.assertEqual(backend.close_calls, 1)

    def test_bootstrap_result_rejects_inconsistent_runtime_exposure(self):
        with self.assertRaisesRegex(
            ValueError,
            "successful network-policy bootstrap requires runtime",
        ):
            LinuxNetworkPolicyRuntimeBootstrapResult(True)


if __name__ == "__main__":
    unittest.main()
