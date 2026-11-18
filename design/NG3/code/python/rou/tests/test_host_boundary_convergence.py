import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.host_boundary_convergence import (
    HostBoundaryConvergenceError,
    cleanup_host_boundary_once,
    converge_host_boundary_once,
)
from rou.host_boundary_policy import HostReturnClassifierRule
from rou.host_boundary_route_convergence import HostBoundaryRoutePhaseResult
from rou.host_underlay_route import HostUnderlayPin
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_boundary_policy import (
    HostBoundaryLinuxDesired,
    HostBoundaryReturnRouteSpec,
    HostBoundaryRouteSpec,
    HostBoundaryRuleSpec,
    HostReturnNftSpec,
)
from rou.linux_host_boundary_routes import LinuxHostBoundaryRouteBackend
from rou.linux_host_return_nft import HostReturnNftObservation, LinuxHostReturnNftBackend


class FakeRoute(LinuxHostBoundaryRouteBackend):
    pass


class FakeNft(LinuxHostReturnNftBackend):
    pass


def desired():
    return HostBoundaryLinuxDesired(
        underlay_pins=(),
        bootstrap_routes=(
            HostBoundaryRouteSpec(
                destination=IPv4Network("10.0.0.0/8"),
                via=IPv4Address("198.19.255.2"),
                interface="vnga-host0",
                protocol=203,
            ),
        ),
        return_route=HostBoundaryReturnRouteSpec(
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            table=1053,
            protocol=203,
        ),
        return_rule=HostBoundaryRuleSpec(mark=83, table=1053, priority=1053),
        return_nft=HostReturnNftSpec(
            interface="vnga-host0",
            mark=83,
            classifier=(
                HostReturnClassifierRule(
                    remote_prefix=IPv4Network("10.0.0.0/8"),
                    profile_id="p",
                    stateful_return=True,
                ),
            ),
        ),
    )


class HostBoundaryConvergenceTests(unittest.TestCase):
    def test_apply_order_is_dependencies_nft_bootstrap(self):
        import rou.host_boundary_convergence as mod
        events = []
        old_prepare = mod.prepare_host_boundary_route_dependencies_once
        old_nft = mod.converge_host_return_nft_once
        old_activate = mod.activate_host_boundary_bootstrap_once
        try:
            mod.prepare_host_boundary_route_dependencies_once = lambda b, d: (
                events.append("deps") or HostBoundaryRoutePhaseResult(False, True)
            )
            mod.converge_host_return_nft_once = lambda b, d: (
                events.append("nft") or HostReturnNftObservation(True, True, ())
            )
            mod.activate_host_boundary_bootstrap_once = lambda b, d: (
                events.append("bootstrap") or HostBoundaryRoutePhaseResult(False, True)
            )
            result = converge_host_boundary_once(object(), object(), desired())
            self.assertTrue(result.confirmed)
            self.assertEqual(events, ["deps", "nft", "bootstrap"])
        finally:
            mod.prepare_host_boundary_route_dependencies_once = old_prepare
            mod.converge_host_return_nft_once = old_nft
            mod.activate_host_boundary_bootstrap_once = old_activate

    def test_nft_failure_never_calls_bootstrap_activation(self):
        import rou.host_boundary_convergence as mod
        events = []
        old_prepare = mod.prepare_host_boundary_route_dependencies_once
        old_nft = mod.converge_host_return_nft_once
        old_activate = mod.activate_host_boundary_bootstrap_once
        try:
            mod.prepare_host_boundary_route_dependencies_once = lambda b, d: (
                events.append("deps") or HostBoundaryRoutePhaseResult(True, True)
            )
            def fail_nft(b, d):
                events.append("nft")
                raise RuntimeError("synthetic nft failure")
            mod.converge_host_return_nft_once = fail_nft
            mod.activate_host_boundary_bootstrap_once = lambda b, d: (
                events.append("bootstrap") or HostBoundaryRoutePhaseResult(True, True)
            )
            with self.assertRaisesRegex(HostBoundaryConvergenceError, "return nft"):
                converge_host_boundary_once(object(), object(), desired())
            self.assertEqual(events, ["deps", "nft"])
        finally:
            mod.prepare_host_boundary_route_dependencies_once = old_prepare
            mod.converge_host_return_nft_once = old_nft
            mod.activate_host_boundary_bootstrap_once = old_activate

    def test_cleanup_order_is_bootstrap_nft_dependencies(self):
        import rou.host_boundary_convergence as mod
        events = []
        old_deactivate = mod.deactivate_host_boundary_bootstrap_once
        old_nft = mod.converge_host_return_nft_once
        old_deps = mod.cleanup_host_boundary_route_dependencies_once
        try:
            mod.deactivate_host_boundary_bootstrap_once = lambda b, d: (
                events.append("bootstrap") or HostBoundaryRoutePhaseResult(True, True)
            )
            mod.converge_host_return_nft_once = lambda b, d: (
                events.append(("nft", d)) or HostReturnNftObservation(False, True, ())
            )
            mod.cleanup_host_boundary_route_dependencies_once = lambda b, d: (
                events.append("deps") or HostBoundaryRoutePhaseResult(True, True)
            )
            result = cleanup_host_boundary_once(object(), object(), desired())
            self.assertTrue(result.confirmed)
            self.assertEqual(events, ["bootstrap", ("nft", None), "deps"])
        finally:
            mod.deactivate_host_boundary_bootstrap_once = old_deactivate
            mod.converge_host_return_nft_once = old_nft
            mod.cleanup_host_boundary_route_dependencies_once = old_deps


if __name__ == "__main__":
    unittest.main()
