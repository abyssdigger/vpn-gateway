from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess


ROU = "vpng2-ctclean-rou"
PEER = "vpng2-ctclean-peer"

PROBE_UID = "65534"
PROBE_GID = "65534"

ROU_ADDR = "198.18.27.2"
PEER_ADDR = "198.18.27.1"

TARGET_A = "203.0.113.31"
TARGET_B = "203.0.113.32"
TARGET_CONTROL = "203.0.113.33"

ID_A = "4242"
ID_B = "4343"
ID_CONTROL = "4444"

PROBE_MARK = "38"    # 0x26
CONTROL_MARK = "119" # 0x77

PING_COPY = Path("/tmp/vpng2-ctclean-ping-nocap")
NFT_TABLE = "probe_ct_cleanup"


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
    for namespace in (ROU, PEER):
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
    for namespace in (ROU, PEER):
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


def create_generation() -> int:
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
    run("ip", "link", "set", "peer0", "netns", PEER)

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
        PEER,
        "ip",
        "addr",
        "add",
        f"{PEER_ADDR}/30",
        "dev",
        "peer0",
    )

    for target in (TARGET_A, TARGET_B, TARGET_CONTROL):
        ns(PEER, "ip", "addr", "add", f"{target}/32", "dev", "lo")

    ns(ROU, "ip", "link", "set", "vpn0", "up")
    ns(PEER, "ip", "link", "set", "peer0", "up")

    ns(
        ROU,
        "sysctl",
        "-q",
        "-w",
        "net.ipv4.conf.vpn0.rp_filter=0",
    )
    ns(
        PEER,
        "sysctl",
        "-q",
        "-w",
        "net.ipv4.conf.peer0.rp_filter=0",
    )

    for target in (TARGET_A, TARGET_B, TARGET_CONTROL):
        ns(
            ROU,
            "ip",
            "route",
            "replace",
            f"{target}/32",
            "via",
            PEER_ADDR,
            "dev",
            "vpn0",
        )

    ns(
        PEER,
        "ip",
        "route",
        "replace",
        f"{ROU_ADDR}/32",
        "dev",
        "peer0",
    )

    return ifindex(ROU, "vpn0")


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

    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET_A} icmp type echo-request ct state new ct mark set 0x26 counter accept comment "probe-a-new"
    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET_A} icmp type echo-request ct state established ct mark 0x26 counter accept comment "probe-a-established"

    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET_B} icmp type echo-request ct state new ct mark set 0x26 counter accept comment "probe-b-new"
    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET_B} icmp type echo-request ct state established ct mark 0x26 counter accept comment "probe-b-established"

    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET_CONTROL} icmp type echo-request ct state new ct mark set 0x77 counter accept comment "control-new"
    meta skuid {PROBE_UID} oif {current_ifindex} ip daddr {TARGET_CONTROL} icmp type echo-request ct state established ct mark 0x77 counter accept comment "control-established"

    meta skuid {PROBE_UID} counter drop comment "output-drop"
}}

chain input {{
    type filter hook input priority 0; policy accept;

    iif {current_ifindex} ip saddr {TARGET_A} icmp type echo-reply ct mark 0x26 counter accept comment "probe-a-input"
    iif {current_ifindex} ip saddr {TARGET_B} icmp type echo-reply ct mark 0x26 counter accept comment "probe-b-input"
    iif {current_ifindex} ip saddr {TARGET_CONTROL} icmp type echo-reply ct mark 0x77 counter accept comment "control-input"

    iif {current_ifindex} ip saddr {TARGET_A} icmp type echo-reply counter drop comment "probe-a-input-drop"
    iif {current_ifindex} ip saddr {TARGET_B} icmp type echo-reply counter drop comment "probe-b-input-drop"
    iif {current_ifindex} ip saddr {TARGET_CONTROL} icmp type echo-reply counter drop comment "control-input-drop"
}}
}}
"""
    ns(ROU, "nft", "-f", "-", input_text=nft)


def probe(target: str, identifier: str) -> subprocess.CompletedProcess[str]:
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
        identifier,
        "-I",
        "vpn0",
        target,
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
    for line in state.splitlines():
        if f'comment "{comment}"' not in line:
            continue
        match = re.search(r"counter packets (\d+) bytes \d+", line)
        if match is not None:
            return int(match.group(1))
    raise RuntimeError(
        f"cannot read nft counter for {comment!r}:\n{state}"
    )


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
    return result.stdout + result.stderr


def entries_with_mark(mark_decimal: str) -> tuple[str, ...]:
    return tuple(
        line
        for line in conntrack_state().splitlines()
        if f"mark={mark_decimal}" in line
        and "src=" in line
        and "dst=" in line
    )


def entry_present(
    *,
    target: str,
    identifier: str,
    mark_decimal: str,
) -> bool:
    return any(
        f"src={ROU_ADDR}" in line
        and f"dst={target}" in line
        and f"id={identifier}" in line
        and f"mark={mark_decimal}" in line
        for line in conntrack_state().splitlines()
    )


def delete_probe_class() -> str:
    result = ns(
        ROU,
        "conntrack",
        "-D",
        "-p",
        "icmp",
        "-m",
        PROBE_MARK,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "probe-class conntrack delete failed:\n"
            + result.stdout
            + result.stderr
        )
    return result.stdout + result.stderr


def require_probe_success(
    *,
    target: str,
    identifier: str,
    label: str,
) -> None:
    completed = probe(target, identifier)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed:\n"
            + completed.stdout
            + completed.stderr
            + "\nNFT:\n"
            + nft_state()
            + "\nCONNTRACK:\n"
            + conntrack_state()
        )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration experiment must run as root")

    require_commands()
    cleanup()

    try:
        create_ping_copy()
        setup_namespaces()

        ping_help = (
            run(str(PING_COPY), "-h", check=False).stdout
            + run(str(PING_COPY), "-h", check=False).stderr
        )
        if "-e" not in ping_help:
            raise RuntimeError(
                "installed ping does not expose fixed identifier option -e"
            )

        ifindex_a = create_generation()
        install_policy(ifindex_a)

        require_probe_success(
            target=TARGET_A,
            identifier=ID_A,
            label="probe A",
        )
        require_probe_success(
            target=TARGET_B,
            identifier=ID_B,
            label="probe B",
        )
        require_probe_success(
            target=TARGET_CONTROL,
            identifier=ID_CONTROL,
            label="control probe",
        )

        if not entry_present(
            target=TARGET_A,
            identifier=ID_A,
            mark_decimal=PROBE_MARK,
        ):
            raise RuntimeError("probe A conntrack entry is missing")
        if not entry_present(
            target=TARGET_B,
            identifier=ID_B,
            mark_decimal=PROBE_MARK,
        ):
            raise RuntimeError("probe B conntrack entry is missing")
        if not entry_present(
            target=TARGET_CONTROL,
            identifier=ID_CONTROL,
            mark_decimal=CONTROL_MARK,
        ):
            raise RuntimeError("control conntrack entry is missing")

        print(
            "PASS K1: two probe-mark entries and one different-mark control "
            "entry exist"
        )
        print("PROBE_ENTRIES_BEFORE_DELETE:")
        for line in entries_with_mark(PROBE_MARK):
            print(line)
        print("CONTROL_ENTRIES_BEFORE_DELETE:")
        for line in entries_with_mark(CONTROL_MARK):
            print(line)

        delete_output = delete_probe_class()
        print("DELETE_OUTPUT:")
        print(delete_output.strip())

        if entries_with_mark(PROBE_MARK):
            raise RuntimeError(
                "probe-mark conntrack entries survived selective delete:\n"
                + conntrack_state()
            )
        if not entry_present(
            target=TARGET_CONTROL,
            identifier=ID_CONTROL,
            mark_decimal=CONTROL_MARK,
        ):
            raise RuntimeError(
                "different-mark control entry was removed by probe cleanup:\n"
                + conntrack_state()
            )

        print(
            "PASS K2: mark-filtered delete removed probe class and preserved "
            "different-mark control state"
        )

        ns(ROU, "ip", "link", "del", "vpn0")
        ifindex_b = create_generation()
        if ifindex_b == ifindex_a:
            raise RuntimeError(
                "replacement vpn0 unexpectedly reused old ifindex"
            )
        install_policy(ifindex_b)

        if not entry_present(
            target=TARGET_CONTROL,
            identifier=ID_CONTROL,
            mark_decimal=CONTROL_MARK,
        ):
            raise RuntimeError(
                "control entry did not survive interface replacement:\n"
                + conntrack_state()
            )

        new_before = counter("probe-a-new")
        established_before = counter("probe-a-established")

        require_probe_success(
            target=TARGET_A,
            identifier=ID_A,
            label="probe A after selective cleanup and generation replacement",
        )

        new_delta = counter("probe-a-new") - new_before
        established_delta = (
            counter("probe-a-established") - established_before
        )

        if new_delta != 1 or established_delta != 0:
            raise RuntimeError(
                "probe A did not return to NEW path after selective cleanup; "
                f"new={new_delta} established={established_delta}\n"
                + nft_state()
                + "\nCONNTRACK:\n"
                + conntrack_state()
            )

        print(
            "PASS K3: cleaned fixed-id probe uses NEW+mark-set after "
            f"generation replacement old={ifindex_a} new={ifindex_b}"
        )

        if not entry_present(
            target=TARGET_CONTROL,
            identifier=ID_CONTROL,
            mark_decimal=CONTROL_MARK,
        ):
            raise RuntimeError(
                "control conntrack entry disappeared after probe reuse:\n"
                + conntrack_state()
            )

        control_before = counter("control-established")
        require_probe_success(
            target=TARGET_CONTROL,
            identifier=ID_CONTROL,
            label="control flow after probe cleanup",
        )
        control_established_delta = (
            counter("control-established") - control_before
        )
        if control_established_delta != 1:
            raise RuntimeError(
                "different-mark control flow was not still established; "
                f"delta={control_established_delta}\n"
                + nft_state()
                + "\nCONNTRACK:\n"
                + conntrack_state()
            )

        print(
            "PASS K4: different-mark control conntrack state remains usable"
        )
        print("EXP_026_PROBE_CLASS_CLEANUP=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
