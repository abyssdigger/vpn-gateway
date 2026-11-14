from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROU = "vpng2-probe-rou"
PRI = "vpng2-probe-pri"
ALT = "vpng2-probe-alt"
PROBE_UID = "65534"
TARGET = "203.0.113.24"
PRI_R = "198.18.24.2"
PRI_P = "198.18.24.1"
ALT_R = "198.18.25.2"
ALT_P = "198.18.25.1"
TABLE = "6024"


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        text=True,
        capture_output=True,
        check=check,
    )


def ns(
    namespace: str,
    *argv: str,
    check: bool = True,
    input_text: str | None = None,
):
    return subprocess.run(
        ("ip", "netns", "exec", namespace, *argv),
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def cleanup() -> None:
    for namespace in (ROU, PRI, ALT):
        run("ip", "netns", "del", namespace, check=False)


def setup() -> None:
    cleanup()
    for namespace in (ROU, PRI, ALT):
        run("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "set", "lo", "up")

    run("ip", "link", "add", "vpn0", "type", "veth", "peer", "name", "pri0")
    run("ip", "link", "set", "vpn0", "netns", ROU)
    run("ip", "link", "set", "pri0", "netns", PRI)
    ns(ROU, "ip", "addr", "add", f"{PRI_R}/30", "dev", "vpn0")
    ns(PRI, "ip", "addr", "add", f"{PRI_P}/30", "dev", "pri0")
    ns(ROU, "ip", "link", "set", "vpn0", "up")
    ns(PRI, "ip", "link", "set", "pri0", "up")

    run("ip", "link", "add", "alt0", "type", "veth", "peer", "name", "altp0")
    run("ip", "link", "set", "alt0", "netns", ROU)
    run("ip", "link", "set", "altp0", "netns", ALT)
    ns(ROU, "ip", "addr", "add", f"{ALT_R}/30", "dev", "alt0")
    ns(ALT, "ip", "addr", "add", f"{ALT_P}/30", "dev", "altp0")
    ns(ROU, "ip", "link", "set", "alt0", "up")
    ns(ALT, "ip", "link", "set", "altp0", "up")

    for namespace, peer_if, rou_ip in (
        (PRI, "pri0", PRI_R),
        (ALT, "altp0", ALT_R),
    ):
        ns(namespace, "ip", "addr", "add", f"{TARGET}/32", "dev", "lo")
        ns(namespace, "ip", "route", "replace", f"{rou_ip}/32", "dev", peer_if)

    # Ordinary local traffic deliberately prefers the alternate path.
    ns(ROU, "ip", "route", "replace", f"{TARGET}/32", "via", ALT_P, "dev", "alt0")

    # Probe plane is selected only for an interface-bound ICMP socket of PROBE_UID.
    ns(
        ROU,
        "ip",
        "rule",
        "add",
        "priority",
        "22024",
        "uidrange",
        f"{PROBE_UID}-{PROBE_UID}",
        "ipproto",
        "icmp",
        "to",
        f"{TARGET}/32",
        "oif",
        "vpn0",
        "lookup",
        TABLE,
    )
    ns(
        ROU,
        "ip",
        "route",
        "add",
        "table",
        TABLE,
        f"{TARGET}/32",
        "via",
        PRI_P,
        "dev",
        "vpn0",
    )
    ns(
        ROU,
        "ip",
        "route",
        "add",
        "table",
        TABLE,
        "unreachable",
        "default",
        "metric",
        "42760",
    )

    ns(
        ROU,
        "sysctl",
        "-q",
        "-w",
        f"net.ipv4.ping_group_range={PROBE_UID} {PROBE_UID}",
    )

    nft = f"""table ip probe_selective {{
chain output {{
    type filter hook output priority 0; policy accept;
    meta skuid {PROBE_UID} oifname "vpn0" ip daddr {TARGET} icmp type echo-request accept
    meta skuid {PROBE_UID} drop
}}
chain input {{
    type filter hook input priority 0; policy accept;
    iifname "vpn0" ip saddr {TARGET} icmp type echo-reply meta skuid {PROBE_UID} accept
    iifname "vpn0" ip saddr {TARGET} icmp type echo-reply drop
}}
}}
"""
    ns(ROU, "nft", "-f", "-", check=True, input_text=nft)


def probe(*ping_args: str) -> subprocess.CompletedProcess[str]:
    return ns(
        ROU,
        "setpriv",
        f"--reuid={PROBE_UID}",
        f"--regid={PROBE_UID}",
        "--clear-groups",
        "--bounding-set=-all",
        "--no-new-privs",
        "ping",
        "-n",
        "-c",
        "1",
        "-W",
        "1",
        *ping_args,
        check=False,
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    try:
        setup()

        ordinary = ns(
            ROU,
            "ping",
            "-n",
            "-c",
            "1",
            "-W",
            "1",
            TARGET,
            check=False,
        )
        if ordinary.returncode != 0:
            raise RuntimeError(
                "ordinary local process lost unrelated main-route traffic: "
                + ordinary.stderr
            )
        route = ns(ROU, "ip", "route", "get", TARGET).stdout
        if "dev alt0" not in route:
            raise RuntimeError(
                "ordinary route no longer demonstrates alternate path: " + route
            )
        print("PASS P1: unrelated local process remains on ordinary alt0 path")

        bound = probe("-I", "vpn0", TARGET)
        if bound.returncode != 0:
            raise RuntimeError(
                "selectively admitted bound probe failed; "
                "INPUT socket-uid isolation may be unsupported: "
                + bound.stdout
                + bound.stderr
            )
        print(
            "PASS P2: capability-free probe UID uses isolated bound vpn0 plane "
            "with selective INPUT/OUTPUT admission"
        )

        unbound = probe(TARGET)
        if unbound.returncode == 0:
            raise RuntimeError(
                "unbound probe escaped through ordinary alternate route"
            )
        print("PASS P3: same probe UID cannot escape unbound through alt0")

        wrong_target = probe("-I", "vpn0", PRI_P)
        if wrong_target.returncode == 0:
            raise RuntimeError("probe UID reached a non-admitted target")
        print("PASS P4: probe UID cannot widen target admission")

        ordinary_again = ns(
            ROU,
            "ping",
            "-n",
            "-c",
            "1",
            "-W",
            "1",
            TARGET,
            check=False,
        )
        if ordinary_again.returncode != 0:
            raise RuntimeError(
                "probe isolation damaged unrelated local traffic"
            )
        print("PASS P5: selective probe policy leaves unrelated local traffic intact")

        print("NG2_SELECTIVE_PROBE_PROCESS_ISOLATION=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
