import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.host_boundary_route_convergence import (
    HostBoundaryRouteConvergenceError,
    activate_host_boundary_bootstrap_once,
    cleanup_host_boundary_route_state_once,
    prepare_host_boundary_route_dependencies_once,
)
from rou.host_boundary_policy import HostReturnClassifierRule
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


class FakeBackend(LinuxHostBoundaryRouteBackend):
    def __init__(self):
        super().__init__(SubprocessCommandRunner())
        self.pins = {}
        self.bootstrap = set()
        self.return_route = False
        self.return_rule = False
        self.events = []
        self.fail_bootstrap = None

    def observe_underlay_pin(self, endpoint, *, managed_interface, owner_protocol):
        pin = self.pins.get(endpoint)
        if pin is None:
            raise RuntimeError(f"missing ordinary path for {endpoint}")
        return pin

    def add_underlay_pin(self, pin):
        self.events.append(("add_pin", str(pin.endpoint)))
        self.pins[pin.endpoint] = HostUnderlayPin(
            endpoint=pin.endpoint,
            interface=pin.interface,
            gateway=pin.gateway,
            source=pin.source,
            protocol=pin.protocol,
            owned=True,
            present=True,
        )

    def delete_underlay_pin(self, pin):
        self.events.append(("del_pin", str(pin.endpoint)))
        self.pins[pin.endpoint] = HostUnderlayPin(
            endpoint=pin.endpoint,
            interface=pin.interface,
            gateway=pin.gateway,
            source=pin.source,
            protocol=pin.protocol,
            owned=True,
            present=False,
        )

    def bootstrap_route_present(self, route):
        return route in self.bootstrap

    def add_bootstrap_route(self, route):
        self.events.append(("add_bootstrap", route.destination.with_prefixlen))
        if self.fail_bootstrap == route.destination:
            raise RuntimeError("synthetic bootstrap failure")
        self.bootstrap.add(route)

    def delete_bootstrap_route(self, route):
        self.events.append(("del_bootstrap", route.destination.with_prefixlen))
        self.bootstrap.discard(route)

    def return_route_present(self, route):
        return self.return_route

    def add_return_route(self, route):
        self.events.append(("add_return_route",))
        self.return_route = True

    def delete_return_route(self, route):
        self.events.append(("del_return_route",))
        self.return_route = False

    def return_rule_present(self, rule):
        return self.return_rule

    def add_return_rule(self, rule):
        self.events.append(("add_return_rule",))
        self.return_rule = True

    def delete_return_rule(self, rule):
        self.events.append(("del_return_rule",))
        self.return_rule = False


def desired():
    pin = HostUnderlayPin(
        endpoint=IPv4Address("198.51.100.10"),
        interface="eth0",
        gateway=IPv4Address("192.0.2.1"),
        source=IPv4Address("192.0.2.20"),
        protocol=203,
    )
    return HostBoundaryLinuxDesired(
        underlay_pins=(pin,),
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
        return_rule=HostBoundaryRuleSpec(mark=0x53, table=1053, priority=1053),
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


class HostBoundaryRouteConvergenceTests(unittest.TestCase):
    def test_prepare_orders_pin_before_dormant_return_state(self):
        backend = FakeBackend()
        d = desired()
        backend.pins[d.underlay_pins[0].endpoint] = d.underlay_pins[0]
        result = prepare_host_boundary_route_dependencies_once(backend, d)
        self.assertTrue(result.confirmed)
        self.assertEqual(
            backend.events,
            [
                ("add_pin", "198.51.100.10"),
                ("add_return_route",),
                ("add_return_rule",),
            ],
        )
        self.assertEqual(backend.bootstrap, set())

    def test_activation_rolls_back_new_bootstrap_routes_on_partial_failure(self):
        backend = FakeBackend()
        d = desired()
        pin = d.underlay_pins[0]
        backend.pins[pin.endpoint] = HostUnderlayPin(
            endpoint=pin.endpoint,
            interface=pin.interface,
            gateway=pin.gateway,
            source=pin.source,
            protocol=pin.protocol,
            owned=True,
            present=True,
        )
        backend.fail_bootstrap = IPv4Network("128.0.0.0/1")
        with self.assertRaisesRegex(
            HostBoundaryRouteConvergenceError,
            "synthetic bootstrap failure",
        ):
            activate_host_boundary_bootstrap_once(backend, d)
        self.assertEqual(backend.bootstrap, set())
        self.assertIn(("del_bootstrap", "0.0.0.0/1"), backend.events)

    def test_cleanup_removes_capture_before_owned_pin(self):
        backend = FakeBackend()
        d = desired()
        pin = d.underlay_pins[0]
        backend.pins[pin.endpoint] = HostUnderlayPin(
            endpoint=pin.endpoint,
            interface=pin.interface,
            gateway=pin.gateway,
            source=pin.source,
            protocol=pin.protocol,
            owned=True,
            present=True,
        )
        backend.bootstrap.update(d.bootstrap_routes)
        backend.return_route = True
        backend.return_rule = True

        cleanup_host_boundary_route_state_once(backend, d)
        first_pin_delete = backend.events.index(("del_pin", "198.51.100.10"))
        self.assertLess(
            backend.events.index(("del_bootstrap", "128.0.0.0/1")),
            first_pin_delete,
        )
        self.assertFalse(backend.bootstrap)
        self.assertFalse(backend.return_rule)
        self.assertFalse(backend.return_route)

    def test_external_pin_survives_cleanup(self):
        backend = FakeBackend()
        d = desired()
        external = HostUnderlayPin(
            endpoint=d.underlay_pins[0].endpoint,
            interface="eth0",
            gateway=IPv4Address("192.0.2.1"),
            source=IPv4Address("192.0.2.20"),
            protocol=203,
            owned=False,
            present=True,
        )
        bootstrap = HostBoundaryRouteSpec(
            destination=IPv4Network("0.0.0.0/1"),
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            protocol=203,
        )
        d = HostBoundaryLinuxDesired(
            underlay_pins=(external,),
            bootstrap_routes=(bootstrap,),
            return_route=None,
            return_rule=None,
            return_nft=None,
        )
        backend.pins[external.endpoint] = external
        backend.bootstrap.add(bootstrap)
        cleanup_host_boundary_route_state_once(backend, d)
        self.assertNotIn(("del_pin", str(external.endpoint)), backend.events)


if __name__ == "__main__":
    unittest.main()
