from __future__ import annotations

from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.interface_identity import InterfaceIdentity
from rou.linux_local_process import LinuxLocalProcessConfig
from rou.linux_probe_driver import (
    LinuxIcmpProbeDriver,
    LinuxIcmpProbeDriverConfig,
    ProbeAttemptOutcome,
)
from rou.linux_driver import (
    LinuxNetworkDriver,
    NetworkNamespaceLinuxRunner,
    SubprocessLinuxRunner,
)
from rou.network_rules import NetworkRulesSpec
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeRulesCalculator,
)
from rou.runtime_bootstrap import bootstrap_linux_network_rules_adapter


ROU = "vpng2-localproc-rou"
PRI = "vpng2-localproc-pri"
ALT = "vpng2-localproc-alt"
TARGET = "203.0.113.24"
PROBE_UID = "65534"
PING_COPY = Path("/tmp/vpng2-localproc-ping")
PING_OVERRIDE = os.environ.get("VPNG_NG2_PROBE_PING_PATH")
PING_EXECUTABLE = Path(PING_OVERRIDE) if PING_OVERRIDE else PING_COPY


def host(*argv: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        argv,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def ns(namespace: str, *argv: str, check: bool = True):
    return host("ip", "netns", "exec", namespace, *argv, check=check)


def cleanup() -> None:
    for namespace in (ROU, PRI, ALT):
        host("ip", "netns", "del", namespace, check=False)
    PING_COPY.unlink(missing_ok=True)


def make_topology() -> None:
    cleanup()

    if PING_OVERRIDE:
        if not PING_EXECUTABLE.is_absolute() or not PING_EXECUTABLE.is_file():
            raise RuntimeError(
                "VPNG_NG2_PROBE_PING_PATH must name an existing absolute file"
            )
    else:
        ping = shutil.which("ping")
        if ping is None:
            raise RuntimeError("ping binary is missing")
        shutil.copyfile(ping, PING_COPY)
        PING_COPY.chmod(0o755)

    for namespace in (ROU, PRI, ALT):
        host("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "set", "lo", "up")

    ns(ROU, "ip", "link", "add", "host0", "type", "dummy")
    ns(ROU, "ip", "link", "set", "host0", "up")

    host("ip", "link", "add", "vpn0", "type", "veth", "peer", "name", "pri0")
    host("ip", "link", "set", "vpn0", "netns", ROU)
    host("ip", "link", "set", "pri0", "netns", PRI)
    ns(ROU, "ip", "addr", "add", "198.18.24.2/30", "dev", "vpn0")
    ns(PRI, "ip", "addr", "add", "198.18.24.1/30", "dev", "pri0")
    ns(PRI, "ip", "addr", "add", f"{TARGET}/32", "dev", "pri0")
    ns(ROU, "ip", "link", "set", "vpn0", "up")
    ns(PRI, "ip", "link", "set", "pri0", "up")

    host("ip", "link", "add", "alt0", "type", "veth", "peer", "name", "altp0")
    host("ip", "link", "set", "alt0", "netns", ROU)
    host("ip", "link", "set", "altp0", "netns", ALT)
    ns(ROU, "ip", "addr", "add", "198.18.25.2/30", "dev", "alt0")
    ns(ALT, "ip", "addr", "add", "198.18.25.1/30", "dev", "altp0")
    ns(ALT, "ip", "addr", "add", f"{TARGET}/32", "dev", "altp0")
    ns(ROU, "ip", "link", "set", "alt0", "up")
    ns(ALT, "ip", "link", "set", "altp0", "up")

    # Ordinary local traffic deliberately prefers the alternate path.
    ns(ROU, "ip", "route", "replace", f"{TARGET}/32", "dev", "alt0")



def identity(namespace: str, ifname: str) -> InterfaceIdentity:
    raw = ns(namespace, "ip", "-j", "link", "show", "dev", ifname).stdout
    item = json.loads(raw)[0]
    return InterfaceIdentity(item["ifname"], item["ifindex"])


def ping_as_probe(*args: str):
    return ns(
        ROU,
        "setpriv",
        f"--reuid={PROBE_UID}",
        f"--regid={PROBE_UID}",
        "--clear-groups",
        "--bounding-set=-all",
        "--no-new-privs",
        str(PING_EXECUTABLE),
        "-n",
        "-c",
        "1",
        "-W",
        "1",
        *args,
        check=False,
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    make_topology()
    try:
        namespace_runner = NetworkNamespaceLinuxRunner(
            SubprocessLinuxRunner(),
            ROU,
        )
        driver = LinuxNetworkDriver(namespace_runner)
        local_process = LinuxLocalProcessConfig(
            uid=65534,
            ct_mark=0x24,
        )
        boot = bootstrap_linux_network_rules_adapter(
            driver,
            local_interface="host0",
            local_process=local_process,
        )
        if not boot.success or boot.adapter is None:
            raise RuntimeError(
                f"LOCAL_PROCESS adapter bootstrap failed: {boot.diagnostic}"
            )
        adapter = boot.adapter

        path = identity(ROU, "vpn0")
        spec = ProbeRulesCalculator().calculate(
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest(
                        "primary",
                        path,
                        IPv4Address(TARGET),
                    ),
                )
            )
        )

        owner = object()
        applied = adapter.apply(owner, spec)
        if not applied.success:
            rules = ns(ROU, "ip", "-j", "-4", "rule", "show", check=False)
            nft = ns(
                ROU,
                "nft",
                "-n",
                "list",
                "table",
                "ip",
                "vpng2_filter",
                check=False,
            )
            raise RuntimeError(
                f"LOCAL_PROCESS production apply failed: {applied.diagnostic}"
                + "\nRULES:\n"
                + rules.stdout
                + rules.stderr
                + "\nNFT:\n"
                + nft.stdout
                + nft.stderr
            )
        if not adapter.renew_state(owner).success:
            state = adapter.get_last_state(owner)
            raise RuntimeError(
                f"LOCAL_PROCESS exact renew failed: {state.diagnostic}"
            )
        print("PASS LP1: production ProbeRules apply and exact renew succeed")

        ip_forward = ns(
            ROU,
            "sysctl",
            "-n",
            "net.ipv4.ip_forward",
        ).stdout.strip()
        if ip_forward != "0":
            raise RuntimeError(
                f"LOCAL_PROCESS-only policy unexpectedly enabled ip_forward={ip_forward}"
            )
        print("PASS LP2: LOCAL_PROCESS-only policy leaves forwarding closed")

        ordinary_route = ns(ROU, "ip", "route", "get", TARGET).stdout
        if "dev alt0" not in ordinary_route:
            raise RuntimeError(
                "ordinary local route no longer selects alt0: " + ordinary_route
            )
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
                "unrelated root process lost ordinary local networking: "
                + ordinary.stdout
                + ordinary.stderr
            )
        print("PASS LP3: unrelated local process retains ordinary alt0 path")

        probe_driver = LinuxIcmpProbeDriver(
            namespace_runner,
            LinuxIcmpProbeDriverConfig(
                local_process=local_process,
                gid=65534,
                ping_path=str(PING_EXECUTABLE),
            ),
        )
        attempt = probe_driver.execute(
            AvailabilityProbeRequest(
                "primary-execution",
                path,
                IPv4Address(TARGET),
            ),
            timeout_seconds=1,
        )
        if attempt.outcome is not ProbeAttemptOutcome.REPLY:
            rules = ns(ROU, "ip", "-j", "-4", "rule", "show", check=False)
            nft = ns(
                ROU,
                "nft",
                "-a",
                "list",
                "table",
                "ip",
                "vpng2_filter",
                check=False,
            )
            raise RuntimeError(
                "production LOCAL_PROCESS executor probe failed: "
                f"{attempt}\nRULES:\n"
                + rules.stdout
                + rules.stderr
                + "\nNFT:\n"
                + nft.stdout
                + nft.stderr
            )
        print(
            "PASS LP4: production executor runs capability-free bound probe "
            "through production probe plane"
        )

        unbound = ping_as_probe(TARGET)
        if unbound.returncode == 0:
            raise RuntimeError(
                "production LOCAL_PROCESS probe escaped unbound via ordinary route"
            )
        wrong_target = ping_as_probe("-I", "vpn0", "198.18.24.1")
        if wrong_target.returncode == 0:
            raise RuntimeError(
                "production LOCAL_PROCESS probe widened beyond admitted target"
            )
        print("PASS LP5: UID guard blocks unbound escape and target widening")

        host("ip", "-n", ROU, "link", "del", "vpn0")
        host("ip", "-n", ROU, "link", "add", "vpn0", "type", "dummy")
        host("ip", "-n", ROU, "link", "set", "vpn0", "up")
        replacement = identity(ROU, "vpn0")
        if replacement.ifindex == path.ifindex:
            raise RuntimeError("replacement vpn0 unexpectedly reused old ifindex")
        renewed = adapter.renew_state(owner)
        if renewed.success:
            raise RuntimeError(
                "same-name/new-ifindex LOCAL_PROCESS generation drift was not detected"
            )
        print(
            "PASS LP6: bound-output same-name/new-ifindex drift fails exact renew "
            f"old={path.ifindex} new={replacement.ifindex}"
        )

        # A reconcile for another owner must not remove the dedicated UID guard merely
        # because this owner's concrete bound generation is currently unrealizable.
        other_owner = object()
        other = adapter.apply(other_owner, NetworkRulesSpec())
        if not other.success:
            raise RuntimeError(
                "other-owner reconcile after probe generation loss failed: "
                f"{other.diagnostic}"
            )
        unbound_after_reconcile = ping_as_probe(TARGET)
        if unbound_after_reconcile.returncode == 0:
            raise RuntimeError(
                "other-owner structural reconcile removed LOCAL_PROCESS uid guard"
            )
        nft_after = ns(
            ROU,
            "nft",
            "-n",
            "list",
            "table",
            "ip",
            "vpng2_filter",
        ).stdout
        if "meta skuid 65534 drop" not in nft_after:
            raise RuntimeError(
                "LOCAL_PROCESS uid guard absent after projected other-owner reconcile"
            )
        print(
            "PASS LP7: projected generation loss retains uid guard across "
            "other-owner structural reconcile"
        )

        print("NG2_LINUX_LOCAL_PROCESS_INTEGRATION=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
