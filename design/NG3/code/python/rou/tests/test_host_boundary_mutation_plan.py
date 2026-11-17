import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.host_boundary_mutation_plan import (
    HostBoundaryMutationKind,
    build_host_boundary_apply_plan,
    build_host_boundary_cleanup_plan,
)
from rou.host_boundary_policy import HostReturnClassifierRule
from rou.host_underlay_route import HostUnderlayPin
from rou.linux_host_boundary_policy import (
    HostBoundaryLinuxDesired,
    HostBoundaryReturnRouteSpec,
    HostBoundaryRouteSpec,
    HostBoundaryRuleSpec,
    HostReturnNftSpec,
)


class HostBoundaryMutationPlanTests(unittest.TestCase):
    def desired(self):
        return HostBoundaryLinuxDesired(
            underlay_pins=(
                HostUnderlayPin(
                    endpoint=IPv4Address("198.51.100.10"),
                    interface="eth0",
                    gateway=IPv4Address("192.0.2.1"),
                    source=None,
                    protocol=203,
                ),
            ),
            bootstrap_routes=(
                HostBoundaryRouteSpec(
                    destination=IPv4Network("0.0.0.0/1"),
                    via=IPv4Address("198.19.255.2"),
                    interface="vnga-host0",
                    protocol=203,
                ),
                HostBoundaryRouteSpec(
                    destination=IPv4Network("128.0.0.0/1"),
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
            return_rule=HostBoundaryRuleSpec(
                mark=0x53,
                table=1053,
                priority=1053,
            ),
            return_nft=HostReturnNftSpec(
                interface="vnga-host0",
                mark=0x53,
                classifier=(
                    HostReturnClassifierRule(
                        remote_prefix=IPv4Network("10.0.0.0/8"),
                        profile_id="p",
                        stateful_return=True,
                    ),
                ),
            ),
        )

    def test_apply_orders_pin_before_capture(self):
        kinds = [step.kind for step in build_host_boundary_apply_plan(self.desired())]
        self.assertEqual(
            kinds,
            [
                HostBoundaryMutationKind.UNDERLAY_PIN,
                HostBoundaryMutationKind.RETURN_ROUTE,
                HostBoundaryMutationKind.RETURN_RULE,
                HostBoundaryMutationKind.RETURN_NFT,
                HostBoundaryMutationKind.BOOTSTRAP_ROUTE,
                HostBoundaryMutationKind.BOOTSTRAP_ROUTE,
            ],
        )

    def test_cleanup_stops_capture_before_removing_pin(self):
        kinds = [step.kind for step in build_host_boundary_cleanup_plan(self.desired())]
        self.assertEqual(
            kinds,
            [
                HostBoundaryMutationKind.BOOTSTRAP_ROUTE,
                HostBoundaryMutationKind.BOOTSTRAP_ROUTE,
                HostBoundaryMutationKind.RETURN_NFT,
                HostBoundaryMutationKind.RETURN_RULE,
                HostBoundaryMutationKind.RETURN_ROUTE,
                HostBoundaryMutationKind.UNDERLAY_PIN,
            ],
        )


if __name__ == "__main__":
    unittest.main()
