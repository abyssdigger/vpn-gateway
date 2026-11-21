from __future__ import annotations

from ipaddress import IPv4Interface
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from rou.interface_identity import InterfaceIdentity
from rou.managed_network_domain import (
    ManagedL3BoundaryEnsureResult,
    ManagedL3BoundaryVerification,
    ManagedNetworkDomainError,
    ManagedNetworkDomainSpec,
    ManagedNetworkDomainVerification,
    ManagedNetworkEnvironmentEnsureResult,
    ManagedNetworkEnvironmentVerification,
    destroy_managed_network_domain,
    ensure_managed_network_domain,
    preflight_managed_l3_boundary,
    preflight_managed_network_domain,
)


SPEC = ManagedNetworkDomainSpec(
    namespace="vg-test",
    host_interface="vghost0",
    inner_interface="host0",
    inner_address=IPv4Interface("198.19.255.2/32"),
)

PRIVATE_BOUNDARY = InterfaceIdentity("host0", 11)


class ManagedLifecycleDecompositionTests(unittest.TestCase):
    def test_exact_environment_with_absent_transition_is_recoverable(self):
        with (
            patch(
                "rou.managed_network_domain.preflight_managed_network_environment",
                return_value=True,
            ) as environment,
            patch(
                "rou.managed_network_domain.preflight_managed_l3_boundary",
                return_value=False,
            ) as boundary,
        ):
            result = preflight_managed_network_domain(SPEC, object())

        self.assertTrue(result.confirmed)
        self.assertFalse(result.existing)
        self.assertIsNone(result.verification)
        environment.assert_called_once_with(SPEC, unittest.mock.ANY)
        boundary.assert_called_once_with(SPEC, unittest.mock.ANY)

    def test_composed_ensure_orders_environment_boundary_portal(self):
        events = []
        final = ManagedNetworkDomainVerification(
            confirmed=True,
            errors=(),
            host_boundary=PRIVATE_BOUNDARY,
        )

        def environment(*_args):
            events.append("environment")
            return ManagedNetworkEnvironmentEnsureResult(
                created=False,
                verification=ManagedNetworkEnvironmentVerification(True, ()),
            )

        def boundary(*_args):
            events.append("boundary")
            return ManagedL3BoundaryEnsureResult(
                created=True,
                verification=ManagedL3BoundaryVerification(
                    True,
                    (),
                    PRIVATE_BOUNDARY,
                ),
            )

        def portal(*_args):
            events.append("portal")
            return SimpleNamespace(confirmed=True, errors=())

        def verify(*_args):
            events.append("verify")
            return final

        with (
            patch(
                "rou.managed_network_domain.preflight_managed_network_domain",
                return_value=SimpleNamespace(existing=False),
            ),
            patch(
                "rou.managed_network_domain.ensure_managed_network_environment",
                side_effect=environment,
            ),
            patch(
                "rou.managed_network_domain.ensure_managed_l3_boundary",
                side_effect=boundary,
            ),
            patch(
                "rou.managed_network_domain.ensure_ordinary_side_portal",
                side_effect=portal,
            ),
            patch(
                "rou.managed_network_domain.verify_managed_network_domain",
                side_effect=verify,
            ),
        ):
            result = ensure_managed_network_domain(SPEC, object())

        self.assertEqual(events, ["environment", "boundary", "portal", "verify"])
        self.assertTrue(result.created)
        self.assertTrue(result.confirmed)
        self.assertIs(result.verification, final)

    def test_orphan_host_endpoint_without_environment_is_conflict(self):
        host = {
            "ifname": SPEC.host_interface,
            "ifindex": 10,
            "link_index": 11,
            "flags": ["UP"],
            "linkinfo": {"info_kind": "veth"},
        }
        with (
            patch(
                "rou.managed_network_domain._namespace_names",
                return_value=(),
            ),
            patch(
                "rou.managed_network_domain._link_rows",
                return_value=[host],
            ),
        ):
            with self.assertRaisesRegex(
                ManagedNetworkDomainError,
                "without managed network environment",
            ):
                preflight_managed_l3_boundary(SPEC, object())

    def test_composite_destroy_attempts_all_independent_lifecycle_areas(self):
        events = []

        def fail_portal(*_args):
            events.append("portal")
            raise RuntimeError("portal synthetic failure")

        def fail_boundary(*_args):
            events.append("boundary")
            raise RuntimeError("boundary synthetic failure")

        def environment(*_args):
            events.append("environment")

        with (
            patch(
                "rou.managed_network_domain.cleanup_ordinary_side_portal",
                side_effect=fail_portal,
            ),
            patch(
                "rou.managed_network_domain.destroy_managed_l3_boundary",
                side_effect=fail_boundary,
            ),
            patch(
                "rou.managed_network_domain.destroy_managed_network_environment",
                side_effect=environment,
            ),
            patch(
                "rou.managed_network_domain._namespace_names",
                return_value=(),
            ),
            patch(
                "rou.managed_network_domain._link_rows",
                return_value=[],
            ),
        ):
            # Strong final absence supersedes contained-artifact cleanup errors.
            destroy_managed_network_domain(SPEC, object())

        self.assertEqual(events, ["portal", "boundary", "environment"])

    def test_composite_destroy_reports_errors_when_final_absence_is_unconfirmed(self):
        with (
            patch(
                "rou.managed_network_domain.cleanup_ordinary_side_portal",
                side_effect=RuntimeError("portal remains"),
            ),
            patch(
                "rou.managed_network_domain.destroy_managed_l3_boundary",
            ),
            patch(
                "rou.managed_network_domain.destroy_managed_network_environment",
            ),
            patch(
                "rou.managed_network_domain._namespace_names",
                return_value=(SPEC.namespace,),
            ),
            patch(
                "rou.managed_network_domain._link_rows",
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(
                ManagedNetworkDomainError,
                "portal remains",
            ):
                destroy_managed_network_domain(SPEC, object())


if __name__ == "__main__":
    unittest.main()
