from __future__ import annotations

import json
from ipaddress import IPv4Interface
import unittest
from unittest.mock import patch

from rou.composite_nft_policy import CompositeNftDesiredState
from rou.controller_startup import (
    ControllerStartupStatus,
    start_controller_once,
)
from rou.controller_stop import (
    ControllerStopResult,
    ControllerStopStatus,
)
from rou.device_firewall_desired import DeviceFirewallDesiredState
from rou.forwarding_gate import (
    ForwardingGateExecutionResult,
    ForwardingGateExecutionStatus,
    ForwardingGateState,
)
from rou.instance_lock import ControllerInstanceBusyError
from rou.interface_identity import InterfaceIdentity
from rou.local_publication_policy import LocalPublicationDesiredState
from rou.managed_network_domain import (
    ManagedNetworkDomainEnsureResult,
    ManagedNetworkDomainPreflightResult,
    ManagedNetworkDomainSpec,
    ManagedNetworkDomainVerification,
)
from rou.network_policy_activation import NetworkPolicyActivationStatus
from rou.payload_forward_desired import PayloadForwardDesiredState
from rou.payload_nat_desired import PayloadNatDesiredState
from rou.payload_network_policy_desired import PayloadNetworkPolicyDesiredState
from rou.payload_routing_desired import PayloadRoutingDesiredState
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM


HOST = InterfaceIdentity("host0", 10)
VPN = InterfaceIdentity("vpn0", 20)

DOMAIN_SPEC = ManagedNetworkDomainSpec(
    namespace="managed",
    host_interface="vgh0",
    inner_interface="host0",
    inner_address=IPv4Interface("198.19.255.2/32"),
)

DESIRED = PayloadNetworkPolicyDesiredState(
    routing=PayloadRoutingDesiredState(
        host_boundary=HOST,
        routes=(),
        rules=(),
    ),
    nft=CompositeNftDesiredState(
        PayloadForwardDesiredState(()),
        PayloadNatDesiredState(()),
        DeviceFirewallDesiredState(()),
        LocalPublicationDesiredState(()),
    ),
)

PREFLIGHT_ABSENT = ManagedNetworkDomainPreflightResult(
    existing=False,
    verification=None,
)
PREFLIGHT_EXISTING = ManagedNetworkDomainPreflightResult(
    existing=True,
    verification=ManagedNetworkDomainVerification(
        confirmed=True,
        errors=(),
        host_boundary=HOST,
    ),
)
DOMAIN = ManagedNetworkDomainEnsureResult(
    created=True,
    verification=ManagedNetworkDomainVerification(
        confirmed=True,
        errors=(),
        host_boundary=HOST,
    ),
)
CONTAINED = ForwardingGateExecutionResult(
    status=ForwardingGateExecutionStatus.SUCCESS,
    desired=ForwardingGateState.DISABLED,
    initial=ForwardingGateState.DISABLED,
    final=ForwardingGateState.DISABLED,
    mutation_attempted=False,
)

UNCONTAINED = ForwardingGateExecutionResult(
    status=ForwardingGateExecutionStatus.POSTCONDITION_FAILED,
    desired=ForwardingGateState.DISABLED,
    initial=ForwardingGateState.ENABLED,
    final=ForwardingGateState.ENABLED,
    mutation_attempted=True,
    diagnostic="still enabled",
)

STOPPED_CLEANUP = ControllerStopResult(
    status=ControllerStopStatus.STOPPED,
    containment=CONTAINED,
)
FAILED_STOP_CLEANUP = ControllerStopResult(
    status=ControllerStopStatus.CLEANUP_FAILED_CONTAINED,
    containment=CONTAINED,
    cleanup_error="namespace remains",
)


class StopSequence:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.values:
            return self.values.pop(0)
        return False


class FakeLock:
    def __init__(self):
        self.acquired = True
        self.release_count = 0

    def release(self):
        self.release_count += 1
        self.acquired = False


class FakeRunner:
    def __init__(self, events, *, fail_observe=False):
        self.events = events
        self.fail_observe = fail_observe

    def run(self, argv):
        self.events.append("observe_interfaces")
        if self.fail_observe:
            raise RuntimeError("synthetic interface observation failure")
        return json.dumps([
            {"ifname": "host0", "ifindex": 10},
            {"ifname": "vpn0", "ifindex": 20},
        ])

    def run_script(self, argv, script):
        raise AssertionError("unexpected script call in patched startup unit test")


class FakePrepared:
    def __init__(self, events, *, fail=False):
        self.events = events
        self.fail = fail

    def build_current(self, host_boundary, interfaces):
        self.events.append("build_desired")
        if self.fail:
            raise RuntimeError("synthetic desired failure")
        if host_boundary != HOST:
            raise AssertionError(host_boundary)
        if interfaces != (HOST, VPN):
            raise AssertionError(interfaces)
        return DESIRED


class FakeBoundaryContribution:
    def __init__(self, events, *, fail_converge=False, fail_cleanup=False):
        self.events = events
        self.fail_converge = fail_converge
        self.fail_cleanup = fail_cleanup

    def converge(self):
        self.events.append("boundary_converge")
        if self.fail_converge:
            raise RuntimeError("synthetic host-routing convergence failure")

    def cleanup(self):
        self.events.append("host_routing_cleanup")
        if self.fail_cleanup:
            raise RuntimeError("synthetic host-routing cleanup failure")


class FakeActivation:
    def __init__(self, *, ready, status, diagnostic=None):
        self.ready = ready
        self.status = status
        self.diagnostic = diagnostic


READY_ACTIVATION = FakeActivation(
    ready=True,
    status=NetworkPolicyActivationStatus.READY,
)
FAILED_ACTIVATION = FakeActivation(
    ready=False,
    status=NetworkPolicyActivationStatus.STRUCTURAL_FAILED,
    diagnostic="synthetic activation failure",
)
UNCONTAINED_ACTIVATION = FakeActivation(
    ready=False,
    status=NetworkPolicyActivationStatus.FAILURE_CONTAINMENT_FAILED,
    diagnostic="synthetic containment failure",
)


class ControllerStartupTests(unittest.TestCase):
    def run_startup(
        self,
        *,
        preflight=PREFLIGHT_ABSENT,
        prepared=None,
        activation=READY_ACTIVATION,
        runner=None,
        preflight_error=None,
        ensure_error=None,
        loader_error=None,
        containment=CONTAINED,
        stop_requested=None,
        stop_cleanup=STOPPED_CLEANUP,
        host_routing_contribution=None,
        host_routing_build_error=None,
    ):
        events = []
        lock = FakeLock()
        runner = runner or FakeRunner(events)
        prepared = prepared or FakePrepared(events)

        def acquire(_spec):
            events.append("lock")
            return lock

        def do_preflight(*args):
            events.append("preflight")
            if preflight_error:
                raise preflight_error
            return preflight

        def loader():
            events.append("load_policy")
            if loader_error:
                raise loader_error
            return prepared

        def ensure(*args):
            events.append("ensure_domain")
            if ensure_error:
                raise ensure_error
            return DOMAIN

        def activate(*args):
            events.append("activate")
            return activation

        def build_host_routing(prepared_arg, domain_spec_arg):
            events.append("host_routing_build")
            if host_routing_build_error:
                raise host_routing_build_error
            if prepared_arg is not prepared:
                raise AssertionError(prepared_arg)
            if domain_spec_arg != DOMAIN_SPEC:
                raise AssertionError(domain_spec_arg)
            return host_routing_contribution

        def cleanup_owned(*args):
            events.append("cleanup_owned")
            if stop_cleanup.stopped:
                lock.release()
            return stop_cleanup

        with (
            patch(
                "rou.controller_startup.acquire_controller_instance_lock",
                side_effect=acquire,
            ),
            patch(
                "rou.controller_startup.preflight_managed_network_domain",
                side_effect=do_preflight,
            ) as preflight_mock,
            patch(
                "rou.controller_startup.ensure_managed_network_domain",
                side_effect=ensure,
            ) as ensure_mock,
            patch(
                "rou.controller_startup.activate_network_policy",
                side_effect=activate,
            ) as activation_mock,
            patch(
                "rou.controller_startup._contain",
                return_value=containment,
            ) as containment_mock,
            patch(
                "rou.controller_startup.cleanup_controller_owned_domain_once",
                side_effect=cleanup_owned,
            ),
        ):
            result = start_controller_once(
                object(),
                DOMAIN_SPEC,
                runner,
                NG3_LINUX_POLICY_PLATFORM,
                loader,
                stop_requested=stop_requested,
                build_host_routing_contribution=(
                    build_host_routing
                    if host_routing_contribution is not None or host_routing_build_error is not None
                    else None
                ),
            )

        return (
            result,
            events,
            lock,
            preflight_mock,
            ensure_mock,
            activation_mock,
            containment_mock,
        )

    def test_ready_order_retains_lifetime_lock(self):
        result, events, lock, *_ = self.run_startup()

        self.assertEqual(result.status, ControllerStartupStatus.READY)
        self.assertTrue(result.ready)
        self.assertIsNotNone(result.session)
        self.assertIs(result.session.lock, lock)
        self.assertTrue(lock.acquired)
        self.assertEqual(lock.release_count, 0)
        self.assertEqual(
            events,
            [
                "lock",
                "preflight",
                "load_policy",
                "ensure_domain",
                "observe_interfaces",
                "build_desired",
                "activate",
            ],
        )

        result.session.lock.release()

    def test_stop_requested_before_ownership_does_not_acquire_lock(self):
        stop = StopSequence(True)

        result, events, lock, preflight_mock, ensure_mock, activation_mock, _ = (
            self.run_startup(stop_requested=stop)
        )

        self.assertEqual(result.status, ControllerStartupStatus.STOPPED)
        self.assertTrue(result.stopped)
        self.assertEqual(events, [])
        preflight_mock.assert_not_called()
        ensure_mock.assert_not_called()
        activation_mock.assert_not_called()
        self.assertTrue(lock.acquired)
        self.assertEqual(lock.release_count, 0)

    def test_stop_requested_after_lock_releases_without_domain_work(self):
        stop = StopSequence(False, True)

        result, events, lock, preflight_mock, ensure_mock, activation_mock, _ = (
            self.run_startup(stop_requested=stop)
        )

        self.assertEqual(result.status, ControllerStartupStatus.STOPPED)
        self.assertEqual(events, ["lock"])
        preflight_mock.assert_not_called()
        ensure_mock.assert_not_called()
        activation_mock.assert_not_called()
        self.assertFalse(lock.acquired)
        self.assertEqual(lock.release_count, 1)

    def test_every_post_preflight_phase_boundary_stops_before_next_phase(self):
        cases = (
            (
                "preflight",
                3,
                ["lock", "preflight", "cleanup_owned"],
            ),
            (
                "policy_load",
                4,
                ["lock", "preflight", "load_policy", "cleanup_owned"],
            ),
            (
                "domain_ensure",
                5,
                [
                    "lock",
                    "preflight",
                    "load_policy",
                    "ensure_domain",
                    "cleanup_owned",
                ],
            ),
            (
                "interface_observation",
                6,
                [
                    "lock",
                    "preflight",
                    "load_policy",
                    "ensure_domain",
                    "observe_interfaces",
                    "cleanup_owned",
                ],
            ),
            (
                "desired_build",
                7,
                [
                    "lock",
                    "preflight",
                    "load_policy",
                    "ensure_domain",
                    "observe_interfaces",
                    "build_desired",
                    "cleanup_owned",
                ],
            ),
            (
                "activation",
                8,
                [
                    "lock",
                    "preflight",
                    "load_policy",
                    "ensure_domain",
                    "observe_interfaces",
                    "build_desired",
                    "activate",
                    "cleanup_owned",
                ],
            ),
        )

        for name, call_number, expected_events in cases:
            with self.subTest(phase=name):
                stop = StopSequence(
                    *([False] * (call_number - 1)),
                    True,
                )
                result, events, lock, *_ = self.run_startup(
                    stop_requested=stop,
                )

                self.assertEqual(
                    result.status,
                    ControllerStartupStatus.STOPPED,
                )
                self.assertEqual(events, expected_events)
                self.assertFalse(lock.acquired)
                self.assertEqual(lock.release_count, 1)
                self.assertEqual(stop.calls, call_number)

    def test_stop_checkpoint_after_preflight_blocks_policy_load_and_cleans(self):
        stop = StopSequence(False, False, True)

        result, events, lock, _, ensure_mock, activation_mock, _ = self.run_startup(
            stop_requested=stop,
        )

        self.assertEqual(result.status, ControllerStartupStatus.STOPPED)
        self.assertEqual(events, ["lock", "preflight", "cleanup_owned"])
        ensure_mock.assert_not_called()
        activation_mock.assert_not_called()
        self.assertFalse(lock.acquired)
        self.assertIsNotNone(result.stop)
        self.assertTrue(result.stop.stopped)

    def test_stop_checkpoint_after_domain_ensure_blocks_interface_observation(self):
        stop = StopSequence(False, False, False, False, True)

        result, events, lock, *_ = self.run_startup(stop_requested=stop)

        self.assertEqual(result.status, ControllerStartupStatus.STOPPED)
        self.assertEqual(
            events,
            [
                "lock",
                "preflight",
                "load_policy",
                "ensure_domain",
                "cleanup_owned",
            ],
        )
        self.assertFalse(lock.acquired)

    def test_stop_after_activation_never_publishes_ready_session(self):
        stop = StopSequence(
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
        )

        result, events, lock, *_ = self.run_startup(stop_requested=stop)

        self.assertEqual(result.status, ControllerStartupStatus.STOPPED)
        self.assertFalse(result.ready)
        self.assertIsNone(result.session)
        self.assertEqual(
            events,
            [
                "lock",
                "preflight",
                "load_policy",
                "ensure_domain",
                "observe_interfaces",
                "build_desired",
                "activate",
                "cleanup_owned",
            ],
        )
        self.assertIs(result.activation, READY_ACTIVATION)
        self.assertFalse(lock.acquired)

    def test_interrupted_cleanup_failure_retains_lock_and_context(self):
        stop = StopSequence(
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
        )

        result, events, lock, *_ = self.run_startup(
            stop_requested=stop,
            stop_cleanup=FAILED_STOP_CLEANUP,
        )

        self.assertEqual(
            result.status,
            ControllerStartupStatus.STOP_CLEANUP_FAILED,
        )
        self.assertFalse(result.ready)
        self.assertFalse(result.stopped)
        self.assertIsNone(result.session)
        self.assertIsNotNone(result.stopping)
        self.assertIs(result.stopping.lock, lock)
        self.assertIs(result.stopping.stop, FAILED_STOP_CLEANUP)
        self.assertTrue(lock.acquired)
        self.assertEqual(lock.release_count, 0)
        self.assertEqual(events[-2:], ["activate", "cleanup_owned"])

    def test_invalid_candidate_does_not_create_absent_domain(self):
        (
            result,
            events,
            lock,
            _,
            ensure_mock,
            activation_mock,
            _,
        ) = self.run_startup(
            loader_error=ValueError("bad config"),
        )

        self.assertEqual(
            result.status,
            ControllerStartupStatus.POLICY_LOAD_FAILED,
        )
        self.assertEqual(events, ["lock", "preflight", "load_policy"])
        ensure_mock.assert_not_called()
        activation_mock.assert_not_called()
        self.assertFalse(lock.acquired)
        self.assertEqual(lock.release_count, 1)

    def test_preflight_failure_stops_before_config_load(self):
        result, events, lock, *_ = self.run_startup(
            preflight_error=RuntimeError("partial domain"),
        )

        self.assertEqual(
            result.status,
            ControllerStartupStatus.DOMAIN_PREFLIGHT_FAILED,
        )
        self.assertEqual(events, ["lock", "preflight"])
        self.assertFalse(lock.acquired)

    def test_domain_ensure_failure_releases_lock_without_activation(self):
        (
            result,
            events,
            lock,
            _,
            _,
            activation_mock,
            _,
        ) = self.run_startup(
            ensure_error=RuntimeError("domain create failed"),
        )

        self.assertEqual(
            result.status,
            ControllerStartupStatus.DOMAIN_ENSURE_FAILED,
        )
        self.assertEqual(
            events,
            ["lock", "preflight", "load_policy", "ensure_domain"],
        )
        activation_mock.assert_not_called()
        self.assertFalse(lock.acquired)

    def test_interface_observation_failure_is_recontained(self):
        events = []
        runner = FakeRunner(events, fail_observe=True)
        (
            result,
            _events,
            lock,
            _,
            _,
            activation_mock,
            containment_mock,
        ) = self.run_startup(runner=runner)

        self.assertEqual(
            result.status,
            ControllerStartupStatus.INTERFACE_OBSERVATION_FAILED,
        )
        containment_mock.assert_called_once()
        activation_mock.assert_not_called()
        self.assertTrue(result.failure_containment.confirmed)
        self.assertFalse(lock.acquired)

    def test_desired_build_failure_is_recontained(self):
        events = []
        prepared = FakePrepared(events, fail=True)
        (
            result,
            _events,
            lock,
            _,
            _,
            activation_mock,
            containment_mock,
        ) = self.run_startup(prepared=prepared)

        self.assertEqual(
            result.status,
            ControllerStartupStatus.DESIRED_BUILD_FAILED,
        )
        containment_mock.assert_called_once()
        activation_mock.assert_not_called()
        self.assertFalse(lock.acquired)

    def test_failed_recontainment_has_distinct_status(self):
        failed_containment = ForwardingGateExecutionResult(
            status=ForwardingGateExecutionStatus.POSTCONDITION_FAILED,
            desired=ForwardingGateState.DISABLED,
            initial=ForwardingGateState.ENABLED,
            final=ForwardingGateState.ENABLED,
            mutation_attempted=True,
            diagnostic="still enabled",
        )
        events = []
        prepared = FakePrepared(events, fail=True)

        result, _, lock, *rest = self.run_startup(
            prepared=prepared,
            containment=failed_containment,
        )

        self.assertEqual(
            result.status,
            ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED,
        )
        self.assertEqual(
            result.failure_status,
            ControllerStartupStatus.DESIRED_BUILD_FAILED,
        )
        self.assertFalse(result.failure_containment.confirmed)
        self.assertFalse(lock.acquired)

    def test_boundary_converges_before_internal_activation_and_is_retained(self):
        events = []
        boundary = FakeBoundaryContribution(events)
        result, startup_events, lock, *_ = self.run_startup(
            host_routing_contribution=boundary,
        )
        combined = startup_events + events
        self.assertEqual(result.status, ControllerStartupStatus.READY)
        self.assertIs(result.session.host_routing_contribution, boundary)
        self.assertLess(
            startup_events.index("build_desired"),
            startup_events.index("host_routing_build"),
        )
        self.assertEqual(events, ["boundary_converge"])
        self.assertLess(
            startup_events.index("host_routing_build"),
            startup_events.index("activate"),
        )
        result.session.lock.release()

    def test_boundary_convergence_failure_cleans_and_never_activates(self):
        events = []
        boundary = FakeBoundaryContribution(events, fail_converge=True)
        result, startup_events, lock, *rest = self.run_startup(
            host_routing_contribution=boundary,
        )
        activation_mock = rest[2]
        self.assertEqual(
            result.status,
            ControllerStartupStatus.HOST_ROUTING_CONVERGENCE_FAILED,
        )
        self.assertEqual(events, ["boundary_converge", "host_routing_cleanup"])
        activation_mock.assert_not_called()
        self.assertFalse(lock.acquired)

    def test_boundary_convergence_and_cleanup_failure_retains_lock(self):
        events = []
        boundary = FakeBoundaryContribution(
            events,
            fail_converge=True,
            fail_cleanup=True,
        )
        result, startup_events, lock, *rest = self.run_startup(
            host_routing_contribution=boundary,
        )
        activation_mock = rest[2]
        self.assertEqual(
            result.status,
            ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED,
        )
        self.assertEqual(
            result.failure_status,
            ControllerStartupStatus.HOST_ROUTING_CONVERGENCE_FAILED,
        )
        self.assertEqual(events, ["boundary_converge", "host_routing_cleanup"])
        self.assertTrue(lock.acquired)
        activation_mock.assert_not_called()
        lock.release()

    def test_activation_failure_cleans_boundary_before_lock_release(self):
        events = []
        boundary = FakeBoundaryContribution(events)
        result, startup_events, lock, *_ = self.run_startup(
            host_routing_contribution=boundary,
            activation=FAILED_ACTIVATION,
        )
        self.assertEqual(result.status, ControllerStartupStatus.ACTIVATION_FAILED)
        self.assertEqual(events, ["boundary_converge", "host_routing_cleanup"])
        self.assertFalse(lock.acquired)

    def test_host_routing_cleanup_failure_after_activation_failure_is_containment_failure(self):
        events = []
        boundary = FakeBoundaryContribution(events, fail_cleanup=True)
        result, startup_events, lock, *_ = self.run_startup(
            host_routing_contribution=boundary,
            activation=FAILED_ACTIVATION,
        )
        self.assertEqual(
            result.status,
            ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED,
        )
        self.assertEqual(
            result.failure_status,
            ControllerStartupStatus.ACTIVATION_FAILED,
        )
        self.assertTrue(lock.acquired)
        self.assertEqual(events, ["boundary_converge", "host_routing_cleanup"])
        lock.release()

    def test_activation_failure_is_not_retried(self):
        (
            result,
            events,
            lock,
            _,
            _,
            activation_mock,
            containment_mock,
        ) = self.run_startup(activation=FAILED_ACTIVATION)

        self.assertEqual(
            result.status,
            ControllerStartupStatus.ACTIVATION_FAILED,
        )
        activation_mock.assert_called_once()
        containment_mock.assert_not_called()
        self.assertEqual(events.count("activate"), 1)
        self.assertFalse(lock.acquired)

    def test_activation_containment_failure_is_preserved(self):
        result, _, lock, *_ = self.run_startup(
            activation=UNCONTAINED_ACTIVATION,
        )

        self.assertEqual(
            result.status,
            ControllerStartupStatus.FAILURE_CONTAINMENT_FAILED,
        )
        self.assertEqual(
            result.failure_status,
            ControllerStartupStatus.ACTIVATION_FAILED,
        )
        self.assertFalse(lock.acquired)

    def test_busy_lock_stops_before_preflight(self):
        with (
            patch(
                "rou.controller_startup.acquire_controller_instance_lock",
                side_effect=ControllerInstanceBusyError("busy"),
            ),
            patch(
                "rou.controller_startup.preflight_managed_network_domain",
            ) as preflight_mock,
        ):
            result = start_controller_once(
                object(),
                object(),
                FakeRunner([]),
                NG3_LINUX_POLICY_PLATFORM,
                lambda: FakePrepared([]),
            )

        self.assertEqual(result.status, ControllerStartupStatus.LOCK_BUSY)
        preflight_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
