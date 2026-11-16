from __future__ import annotations

from ipaddress import IPv4Network
import os
import subprocess

from rou.binding import LogicalPathId
from rou.interface_inventory import parse_ip_link_inventory
from rou.iproute_priority_backend import (
    IproutePriorityBackend,
    SubprocessCommandRunner,
)
from rou.route_priority_executor import (
    RoutePriorityExecutionStatus,
    converge_route_priority_once,
)
from rou.route_priority_inventory import RoutePriorityPathRoute


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 0, 0)
DEST = IPv4Network("10.77.0.0/16")
TABLE = 100
PROTO = 202


def run(*argv):
    subprocess.run(argv, check=True, text=True, capture_output=True)


def main():
    ns = f"vpng-ng3-priority-{os.getpid()}"
    runner = SubprocessCommandRunner()

    try:
        run("ip", "netns", "add", ns)
        for ifname in ("patha", "pathb"):
            run("ip", "-n", ns, "link", "add", ifname, "type", "dummy")
            run("ip", "-n", ns, "link", "set", ifname, "up")

        links = parse_ip_link_inventory(
            runner.run(("ip", "-n", ns, "-j", "link", "show"))
        )
        by_name = {endpoint.ifname: endpoint for endpoint in links}

        paths = (
            RoutePriorityPathRoute(A, by_name["patha"]),
            RoutePriorityPathRoute(B, by_name["pathb"]),
        )

        run(
            "ip", "-n", ns, "-4", "route", "add", "unicast", str(DEST),
            "table", str(TABLE), "proto", str(PROTO), "metric", "10",
            "dev", "patha",
        )
        run(
            "ip", "-n", ns, "-4", "route", "add", "unicast", str(DEST),
            "table", str(TABLE), "proto", str(PROTO), "metric", "20",
            "dev", "pathb",
        )

        backend = IproutePriorityBackend(
            runner=runner,
            namespace=ns,
            table=TABLE,
            owner_protocol=PROTO,
            destination=DEST,
            path_routes=paths,
        )

        initial = backend.observe_route_priority()
        assert initial.routes[A] == frozenset((10,))
        assert initial.routes[B] == frozenset((20,))

        swapped = converge_route_priority_once(
            backend,
            {A: 20, B: 10},
            (10, 20, 30),
        )
        assert swapped.status is RoutePriorityExecutionStatus.SUCCESS
        assert swapped.final.routes[A] == frozenset((20,))
        assert swapped.final.routes[B] == frozenset((10,))

        # Create the exact physical shape left by failure after add-new and
        # before delete-old, then prove fresh-state recovery without replay.
        run(
            "ip", "-n", ns, "-4", "route", "add", "unicast", str(DEST),
            "table", str(TABLE), "proto", str(PROTO), "metric", "30",
            "dev", "patha",
        )
        partial = backend.observe_route_priority()
        assert partial.routes[A] == frozenset((20, 30))
        assert partial.routes[B] == frozenset((10,))

        recovered = converge_route_priority_once(
            backend,
            {A: 10, B: 20},
            (10, 20, 30),
        )
        assert recovered.status is RoutePriorityExecutionStatus.SUCCESS
        assert recovered.final.routes[A] == frozenset((10,))
        assert recovered.final.routes[B] == frozenset((20,))

        print("NG3 route-priority Linux integration: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", ns),
            check=False,
            text=True,
            capture_output=True,
        )


if __name__ == "__main__":
    main()
