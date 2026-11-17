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
    host_address=IPv4Interface("192.0.2.1/30"),
    inner_address=IPv4Interface("192.0.2.2/30"),
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
        ):
            result = start_controller_once(
                object(),
                DOMAIN_SPEC,
                runner,
                NG3_LINUX_POLICY_PLATFORM,
                loader,
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
