from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROU = "vpng2-ct-rou"
PEER_A = "vpng2-ct-peer-a"
PEER_B = "vpng2-ct-peer-b"

PROBE_UID = "65534"
PROBE_GID = "65534"
PING_ID = "4242"
CT_MARK_DECIMAL = "37"  # 0x25

TARGET = "203.0.113.25"
ROU_ADDR = "198.18.26.2"
PEER_ADDR = "198.18.26.1"
TABLE = "6025"
RULE_PRIORITY = "22025"

PING_COPY = Path("/tmp/vpng2-ct-ping-nocap")
NFT_TABLE = "probe_ct_generation"


def run(
    *argv: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def ns(
    namespace: str,
    *argv: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return run(
        "ip",
        "netns",
        "exec",
        namespace,
        *argv,
        check=check,
        input_text=input_text,
    )


def cleanup() -> None:
    for namespace in (ROU, PEER_A, PEER_B):
        run("ip", "netns", "del", namespace, check=False)
    PING_COPY.unlink(missing_ok=True)


def require_commands() -> None:
    missing = [
        name
        for name in ("ip", "nft", "ping", "setpriv", "conntrack")
        if shutil.which(name) is None
    ]
    if missing:
        raise RuntimeError(
            "missing required commands: " + ", ".join(missing)
        )


def create_ping_copy() -> None:
    ping = shutil.which("ping")
    assert ping is not None
    shutil.copyfile(ping, PING_COPY)
    PING_COPY.chmod(0o755)


def setup_namespaces() -> None:
    for namespace in (ROU, PEER_A, PEER_B):
        run("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "set", "lo", "up")

    ns(
        ROU,
        "sysctl",
        "-q",
        "-w",
        f"net.ipv4.ping_group_range={PROBE_GID} {PROBE_GID}",
    )
    for key in (
        "net.ipv4.conf.all.rp_filter",
        "net.ipv4.conf.default.rp_filter",
    ):
        ns(ROU, "sysctl", "-q", "-w", f"{key}=0")


def ifindex(namespace: str, ifname: str) -> int:
    result = ns(
        namespace,
        "ip",
        "-j",
        "link",
        "show",
        "dev",
        ifname,
    )
    match = re.search(r'"ifindex":\s*(\d+)', result.stdout)
    if match is None:
        raise RuntimeError(
            f"cannot parse ifindex for {namespace}/{ifname}: "
            + result.stdout
            + result.stderr
        )
    return int(match.group(1))


def create_generation(peer_namespace: str) -> int:
    run(
        "ip",
        "link",
        "add",
        "vpn0",
        "type",
        "veth",
        "peer",
        "name",
        "peer0",
    )
    run("ip", "link", "set", "vpn0", "netns", ROU)
    run("ip", "link", "set", "peer0", "netns", peer_namespace)

    ns(
        ROU,
        "ip",
        "addr",
        "add",
        f"{ROU_ADDR}/30",
        "dev",
        "vpn0",
    )
    ns(
        peer_namespace,
        "ip",
        "addr",
        "add",
        f"{PEER_ADDR}/30",
        "dev",
        "peer0",
    )
    ns(
        peer_namespace,
        "ip",
        "addr",
        "add",
        f"{TARGET}/32",
        "dev",
        "lo",
    )

    ns(ROU, "ip", "link", "set", "vpn0", "up")
    ns(peer_namespace, "ip", "link", "set", "peer0", "up")
    ns(
        ROU,
        "sysctl",
        "-q",
        "-w",
        "net.ipv4.conf.vpn0.rp_filter=0",
    )
    ns(
        peer_namespace,
        "sysctl",
        "-q",
        "-w",
        "net.ipv4.conf.peer0.rp_filter=0",
    )

    ns(
        peer_namespace,
        "ip",
        "route",
        "replace",
        f"{ROU_ADDR}/32",
        "dev",
        "peer0",
    )

    return ifindex(ROU, "vpn0")


def configure_routing(peer_namespace: str) -> None:
    del peer_namespace  # topology label only; route parameters are identical.

    ns(
        ROU,
        "ip",
        "rule",
        "del",
        "priority",
        RULE_PRIORITY,
        check=False,
    )
    ns(
        ROU,
        "ip",
        "route",
        "flush",
        "table",
        TABLE,
        check=False,
    )

    ns(
        ROU,
        "ip",
        "rule",
        "add",
        "priority",
        RULE_PRIORITY,
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
        PEER_ADDR,
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
        "42761",
    )


def install_policy(current_ifindex: int) -> None:
    ns(
        ROU,
        "nft",
        "delete",
        "table",
        "ip",
        NFT_TABLE,
        check=False,
    )

    nft = f"""table ip {NFT_TABLE} {{
chain output {{
    type filter hook output priority 0; policy accept;

    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET} icmp type echo-request ct state new ct mark set 0x25 counter accept comment "ctgen-new"
    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET} icmp type echo-request ct state established ct mark 0x25 counter accept comment "ctgen-established"
    meta skuid {PROBE_UID} counter drop comment "ctgen-output-drop"
}}

chain input {{
    type filter hook input priority 0; policy accept;

    iif {current_ifindex} ip saddr {TARGET} icmp type echo-reply ct state established ct mark 0x25 counter accept comment "ctgen-input-marked"
    iif {current_ifindex} ip saddr {TARGET} icmp type echo-reply counter drop comment "ctgen-input-unmarked"
}}
}}
"""
    ns(ROU, "nft", "-f", "-", input_text=nft)


def probe() -> subprocess.CompletedProcess[str]:
    return ns(
        ROU,
        "setpriv",
        f"--reuid={PROBE_UID}",
        f"--regid={PROBE_GID}",
        "--clear-groups",
        "--bounding-set=-all",
        "--no-new-privs",
        str(PING_COPY),
        "-n",
        "-c",
        "1",
        "-W",
        "1",
        "-e",
        PING_ID,
        "-I",
        "vpn0",
        TARGET,
        check=False,
    )


def nft_state() -> str:
    return ns(
        ROU,
        "nft",
        "-a",
        "list",
        "table",
        "ip",
        NFT_TABLE,
        check=False,
    ).stdout


def counter(comment: str) -> int:
    state = nft_state()
    pattern = re.compile(
        rf"counter packets (\d+) bytes \d+ .*comment \"{re.escape(comment)}\""
    )
    match = pattern.search(state)
    if match is None:
        # nft may print comment before counter on some versions. Keep the
        # fallback intentionally narrow to the one rule line.
        for line in state.splitlines():
            if f'comment "{comment}"' not in line:
                continue
            packet_match = re.search(r"counter packets (\d+) bytes \d+", line)
            if packet_match is not None:
                return int(packet_match.group(1))
        raise RuntimeError(
            f"cannot read nft counter for {comment!r}:\n{state}"
        )
    return int(match.group(1))


def conntrack_state() -> str:
    result = ns(
        ROU,
        "conntrack",
        "-L",
        "-p",
        "icmp",
        "-o",
        "extended",
        check=False,
    )
    # conntrack returns 1 when no entries match on some versions.
    return result.stdout + result.stderr


def matching_conntrack_lines() -> tuple[str, ...]:
    lines: list[str] = []
    for line in conntrack_state().splitlines():
        if (
            f"src={ROU_ADDR}" in line
            and f"dst={TARGET}" in line
            and f"id={PING_ID}" in line
        ):
            lines.append(line)
    return tuple(lines)


def marked_entry_present() -> bool:
    return any(
        f"mark={CT_MARK_DECIMAL}" in line
        for line in matching_conntrack_lines()
    )


def delete_matching_conntrack() -> None:
    result = ns(
        ROU,
        "conntrack",
        "-D",
        "-p",
        "icmp",
        "--orig-src",
        ROU_ADDR,
        "--orig-dst",
        TARGET,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            "cannot delete matching conntrack entry:\n"
            + result.stdout
            + result.stderr
        )


def dump_failure(label: str, completed: subprocess.CompletedProcess[str]) -> str:
    return (
        f"{label}\n"
        + completed.stdout
        + completed.stderr
        + "\nNFT:\n"
        + nft_state()
        + "\nCONNTRACK:\n"
        + conntrack_state()
        + "\nRULES:\n"
        + ns(ROU, "ip", "-4", "rule", "show", check=False).stdout
        + "\nROUTES:\n"
        + ns(
            ROU,
            "ip",
            "-4",
            "route",
            "show",
            "table",
            TABLE,
            check=False,
        ).stdout
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration experiment must run as root")

    require_commands()
    cleanup()

    try:
        create_ping_copy()
        setup_namespaces()

        if not run(
            str(PING_COPY),
            "-h",
            check=False,
        ).stdout + run(
            str(PING_COPY),
            "-h",
            check=False,
        ).stderr:
            raise RuntimeError("cannot inspect ping help")
        ping_help = (
            run(str(PING_COPY), "-h", check=False).stdout
            + run(str(PING_COPY), "-h", check=False).stderr
        )
        if "-e" not in ping_help:
            raise RuntimeError(
                "installed ping does not expose fixed identifier option -e"
            )

        ifindex_a = create_generation(PEER_A)
        ns(
            ROU,
            "ip",
            "route",
            "replace",
            f"{TARGET}/32",
            "via",
            PEER_ADDR,
            "dev",
            "vpn0",
        )
        baseline = ns(
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
        if baseline.returncode != 0:
            raise RuntimeError(
                "generation A topology baseline ping failed:\n"
                + baseline.stdout
                + baseline.stderr
                + "\nPEER ROUTE:\n"
                + ns(
                    PEER_A,
                    "ip",
                    "route",
                    "get",
                    ROU_ADDR,
                    check=False,
                ).stdout
            )
        ns(
            ROU,
            "ip",
            "route",
            "del",
            f"{TARGET}/32",
            check=False,
        )

        configure_routing(PEER_A)
        install_policy(ifindex_a)

        first = probe()
        if first.returncode != 0:
            raise RuntimeError(dump_failure("generation A probe failed", first))

        if counter("ctgen-new") != 1:
            raise RuntimeError(
                "generation A did not take NEW+mark-set path:\n" + nft_state()
            )
        if not marked_entry_present():
            raise RuntimeError(
                "generation A left no marked matching conntrack entry:\n"
                + conntrack_state()
            )

        print(
            "PASS C1: generation A created marked fixed-identifier conntrack "
            f"state ifindex={ifindex_a}"
        )
        print("CONNTRACK_A:")
        for line in matching_conntrack_lines():
            print(line)

        ns(ROU, "ip", "link", "del", "vpn0")
        if ns(
            ROU,
            "ip",
            "link",
            "show",
            "dev",
            "vpn0",
            check=False,
        ).returncode == 0:
            raise RuntimeError("generation A vpn0 survived deletion")

        ifindex_b = create_generation(PEER_B)
        if ifindex_b == ifindex_a:
            raise RuntimeError(
                "generation B unexpectedly reused generation A ifindex"
            )
        configure_routing(PEER_B)
        install_policy(ifindex_b)

        print(
            "PASS C2: generation B recreated same vpn0 identity with new "
            f"ifindex old={ifindex_a} new={ifindex_b}"
        )

        stale_survived = marked_entry_present()
        print(
            "OBS C3: generation-A marked conntrack entry after replacement = "
            + ("PRESENT" if stale_survived else "ABSENT")
        )
        if stale_survived:
            print("CONNTRACK_AFTER_REPLACEMENT:")
            for line in matching_conntrack_lines():
                print(line)

            new_before = counter("ctgen-new")
            established_before = counter("ctgen-established")

            second = probe()
            if second.returncode != 0:
                raise RuntimeError(
                    dump_failure(
                        "generation B deliberate tuple-reuse probe failed",
                        second,
                    )
                )

            new_after = counter("ctgen-new")
            established_after = counter("ctgen-established")
            new_delta = new_after - new_before
            established_delta = established_after - established_before

            print(
                "OBS C4: tuple reuse counter deltas "
                f"new={new_delta} established={established_delta}"
            )

            if established_delta == 1 and new_delta == 0:
                outcome = "STALE-INHERITANCE"
                print(
                    "FINDING C4: generation B inherited stale marked "
                    "ESTABLISHED conntrack state"
                )
            elif new_delta == 1 and established_delta == 0:
                outcome = "PASS-NO-INHERITANCE"
                print(
                    "PASS C4: stale entry survived but generation B tuple "
                    "reuse created a NEW marked flow"
                )
            else:
                raise RuntimeError(
                    "ambiguous tuple-reuse classification:\n" + nft_state()
                )
        else:
            outcome = "PASS-NO-SURVIVAL"
            print(
                "PASS C3: interface generation replacement destroyed the "
                "marked ICMP conntrack entry"
            )

        delete_matching_conntrack()
        if marked_entry_present():
            raise RuntimeError(
                "matching conntrack entry survived explicit control deletion:\n"
                + conntrack_state()
            )

        new_before = counter("ctgen-new")
        established_before = counter("ctgen-established")

        control = probe()
        if control.returncode != 0:
            raise RuntimeError(
                dump_failure("control probe after conntrack deletion failed", control)
            )

        new_delta = counter("ctgen-new") - new_before
        established_delta = (
            counter("ctgen-established") - established_before
        )
        if new_delta != 1 or established_delta != 0:
            raise RuntimeError(
                "control probe did not take NEW+mark-set path; "
                f"new={new_delta} established={established_delta}\n"
                + nft_state()
            )

        print(
            "PASS C5: explicit matching conntrack deletion restores "
            "NEW+mark-set path"
        )
        print(f"EXP_025_RESULT={outcome}")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
