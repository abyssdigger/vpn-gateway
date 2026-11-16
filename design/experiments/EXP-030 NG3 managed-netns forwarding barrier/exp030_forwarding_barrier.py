from __future__ import annotations

import os
import subprocess
import sys


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=True,
    )


def ns(name: str, *argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ip", "netns", "exec", name, *argv, check=check)


def sysctl_value(namespace: str | None) -> int:
    if namespace is None:
        completed = run("sysctl", "-n", "net.ipv4.ip_forward")
    else:
        completed = ns(namespace, "sysctl", "-n", "net.ipv4.ip_forward")
    value = completed.stdout.strip()
    assert value in ("0", "1"), value
    return int(value)


def set_forwarding(namespace: str, value: int) -> None:
    assert value in (0, 1)
    completed = ns(
        namespace,
        "sysctl",
        "-w",
        f"net.ipv4.ip_forward={value}",
    )
    assert completed.returncode == 0, completed
    assert sysctl_value(namespace) == value


def ping(left: str, destination: str) -> bool:
    completed = ns(
        left,
        "ping",
        "-n",
        "-c",
        "2",
        "-W",
        "1",
        destination,
        check=False,
    )
    return completed.returncode == 0


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-030 must run as root")

    suffix = str(os.getpid())
    left = f"vpng-e30-l-{suffix}"
    gate = f"vpng-e30-g-{suffix}"
    right = f"vpng-e30-r-{suffix}"
    created = []

    host_before = sysctl_value(None)

    try:
        for name in (left, gate, right):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")

        # left <-> managed gate
        run(
            "ip", "link", "add", f"e30l-{suffix}",
            "type", "veth", "peer", "name", f"e30gl-{suffix}",
        )
        run("ip", "link", "set", f"e30l-{suffix}", "netns", left)
        run("ip", "link", "set", f"e30gl-{suffix}", "netns", gate)

        # managed gate <-> right
        run(
            "ip", "link", "add", f"e30r-{suffix}",
            "type", "veth", "peer", "name", f"e30gr-{suffix}",
        )
        run("ip", "link", "set", f"e30r-{suffix}", "netns", right)
        run("ip", "link", "set", f"e30gr-{suffix}", "netns", gate)

        ns(left, "ip", "addr", "add", "10.30.1.2/24", "dev", f"e30l-{suffix}")
        ns(gate, "ip", "addr", "add", "10.30.1.1/24", "dev", f"e30gl-{suffix}")
        ns(gate, "ip", "addr", "add", "10.30.2.1/24", "dev", f"e30gr-{suffix}")
        ns(right, "ip", "addr", "add", "10.30.2.2/24", "dev", f"e30r-{suffix}")

        for namespace, ifname in (
            (left, f"e30l-{suffix}"),
            (gate, f"e30gl-{suffix}"),
            (gate, f"e30gr-{suffix}"),
            (right, f"e30r-{suffix}"),
        ):
            ns(namespace, "ip", "link", "set", ifname, "up")

        ns(
            left,
            "ip", "route", "add", "10.30.2.0/24",
            "via", "10.30.1.1",
        )
        ns(
            right,
            "ip", "route", "add", "10.30.1.0/24",
            "via", "10.30.2.1",
        )

        # H1/H5: explicit write + reread controls the managed namespace.
        set_forwarding(gate, 1)
        assert ping(left, "10.30.2.2"), "forwarding=1 did not pass transit ICMP"

        # H2: managed-netns sysctl is not the host namespace value.
        assert sysctl_value(None) == host_before, (
            host_before,
            sysctl_value(None),
        )

        # H3: verified zero is an actual packet barrier.
        set_forwarding(gate, 0)
        assert not ping(left, "10.30.2.2"), (
            "forwarding=0 unexpectedly passed transit ICMP"
        )
        assert sysctl_value(None) == host_before, (
            host_before,
            sysctl_value(None),
        )

        # H4: forwarding is restored only after explicit 1 + reread.
        set_forwarding(gate, 1)
        assert ping(left, "10.30.2.2"), (
            "forwarding=1 did not restore transit ICMP"
        )
        assert sysctl_value(None) == host_before

        print(f"EXP030_HOST_IP_FORWARD={host_before}")
        print("EXP030_MANAGED_ZERO_BLOCKED=1")
        print("EXP030_MANAGED_ONE_FORWARDED=1")
        print("EXP-030 managed-netns forwarding barrier: PASS")
        return 0
    finally:
        for name in reversed(created):
            run("ip", "netns", "del", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
