import unittest
from ipaddress import IPv4Address

from rou.host_boundary_prepare import prepare_linux_host_boundary_desired
from rou.host_underlay_route import HostUnderlayPin
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_boundary_policy import HostBoundaryLinuxAllocation
from rou.linux_host_boundary_routes import LinuxHostBoundaryRouteBackend
from rou.release1_config import parse_release1_config


class FakeRouteBackend(LinuxHostBoundaryRouteBackend):
    def __init__(self):
        super().__init__(SubprocessCommandRunner())
        self.observed = []

    def observe_underlay_pin(self, endpoint, *, managed_interface, owner_protocol):
        self.observed.append((endpoint, managed_interface, owner_protocol))
        return HostUnderlayPin(
            endpoint=endpoint,
            interface="eth0",
            gateway=IPv4Address("192.0.2.1"),
            source=IPv4Address("192.0.2.20"),
            protocol=owner_protocol,
        )


class HostBoundaryPrepareTests(unittest.TestCase):
    def allocation(self):
        return HostBoundaryLinuxAllocation(
            mark=0x53,
            return_table=1053,
            return_rule_priority=1053,
            route_protocol=203,
        )

    def test_all_required_endpoints_are_observed_before_desired_is_returned(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
allow_vpn_client = [
  "udp>198.51.100.10:51820",
  "tcp>203.0.113.20:443",
]

[profile.full]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0"]
device_order = ["wg"]
""")
        backend = FakeRouteBackend()
        desired = prepare_linux_host_boundary_desired(
            cfg,
            route_backend=backend,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("198.19.255.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(
            [str(item[0]) for item in backend.observed],
            ["198.51.100.10", "203.0.113.20"],
        )
        self.assertEqual(len(desired.underlay_pins), 2)
        self.assertEqual(
            [item.destination.with_prefixlen for item in desired.bootstrap_routes],
            ["0.0.0.0/1", "128.0.0.0/1"],
        )

    def test_no_captured_endpoint_means_no_external_route_observation(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false
allow_vpn_client = "udp>198.51.100.10:51820"

[profile.narrow]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg"]
""")
        backend = FakeRouteBackend()
        desired = prepare_linux_host_boundary_desired(
            cfg,
            route_backend=backend,
            host_interface="vnga-host0",
            inner_gateway=IPv4Address("198.19.255.2"),
            allocation=self.allocation(),
        )
        self.assertEqual(backend.observed, [])
        self.assertEqual(desired.underlay_pins, ())
        self.assertEqual(len(desired.bootstrap_routes), 1)


if __name__ == "__main__":
    unittest.main()
