#!/usr/bin/env python3
"""EXP-086: prove WireGuard same-prefix peer selection is not Linux FIB priority."""

from __future__ import annotations

import subprocess
import time


CLIENT = "exp086-client"
PEER_A = "exp086-a"
PEER_B = "exp086-b"
NAMESPACES = (CLIENT, PEER_A, PEER_B)
REMOTE_PREFIX = "10.77.0.0/24"
REMOTE_IP = "10.77.0.1"
CLIENT_INNER = "10.200.0.1"


def host(*args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed rc={completed.returncode}: {args!r}\\n"
            f"stdout:\\n{completed.stdout}\\n"
            f"stderr:\\n{completed.stderr}"
        )
    return completed


def ns(
    namespace: str,
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return host(
        "ip",
        "netns",
        "exec",
        namespace,
        *args,
        check=check,
        input_text=input_text,
    )


def cleanup() -> None:
    for namespace in NAMESPACES:
        host("ip", "netns", "del", namespace, check=False)


def keypair() -> tuple[str, str]:
    private = host("wg", "genkey").stdout.strip()
    public = host("wg", "pubkey", input_text=private + "\n").stdout.strip()
    return private, public


def allowed_ips() -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    output = ns(CLIENT, "wg", "show", "wg0", "allowed-ips").stdout
    for line in output.splitlines():
        if not line.strip():
            continue
        peer, values = line.split("\t", 1)
        if values.strip() == "(none)":
            result[peer] = ()
        else:
            result[peer] = tuple(value.strip() for value in values.split(","))
    return result


def transfers() -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    output = ns(CLIENT, "wg", "show", "wg0", "transfer").stdout
    for line in output.splitlines():
        if not line.strip():
            continue
        peer, received, sent = line.split("\t")
        result[peer] = (int(received), int(sent))
    return result


def ping_remote() -> None:
    completed = ns(
        CLIENT,
        "ping",
        "-c",
        "2",
        "-W",
        "2",
        "-I",
        CLIENT_INNER,
        REMOTE_IP,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "payload ping failed:\n"
            + completed.stdout
            + completed.stderr
        )
    # Transfer counters are normally updated synchronously, but leave a tiny margin
    # before reading them through the userspace tool.
    time.sleep(0.1)


def owner_for_prefix(state: dict[str, tuple[str, ...]]) -> str:
    owners = [peer for peer, prefixes in state.items() if REMOTE_PREFIX in prefixes]
    if len(owners) != 1:
        raise RuntimeError(
            f"expected exactly one owner for {REMOTE_PREFIX}, got {owners!r}; state={state!r}"
        )
    return owners[0]


def selected_peer(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> str:
    changed = []
    for peer in after:
        before_sent = before.get(peer, (0, 0))[1]
        after_sent = after[peer][1]
        if after_sent > before_sent:
            changed.append(peer)
    if len(changed) != 1:
        raise RuntimeError(
            f"expected exactly one peer tx counter to increase, got {changed!r}; "
            f"before={before!r} after={after!r}"
        )
    return changed[0]


def add_payload_routes(first_metric: int, second_metric: int) -> None:
    ns(CLIENT, "ip", "route", "flush", REMOTE_PREFIX)
    ns(CLIENT, "ip", "route", "add", REMOTE_PREFIX, "dev", "wg0", "metric", str(first_metric))
    ns(CLIENT, "ip", "route", "add", REMOTE_PREFIX, "dev", "wg0", "metric", str(second_metric))


def setup_underlay() -> None:
    for namespace in NAMESPACES:
        host("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "set", "lo", "up")

    host("ip", "link", "add", "c-a", "type", "veth", "peer", "name", "a-c")
    host("ip", "link", "set", "c-a", "netns", CLIENT)
    host("ip", "link", "set", "a-c", "netns", PEER_A)
    ns(CLIENT, "ip", "addr", "add", "192.0.2.1/24", "dev", "c-a")
    ns(PEER_A, "ip", "addr", "add", "192.0.2.2/24", "dev", "a-c")
    ns(CLIENT, "ip", "link", "set", "c-a", "up")
    ns(PEER_A, "ip", "link", "set", "a-c", "up")

    host("ip", "link", "add", "c-b", "type", "veth", "peer", "name", "b-c")
    host("ip", "link", "set", "c-b", "netns", CLIENT)
    host("ip", "link", "set", "b-c", "netns", PEER_B)
    ns(CLIENT, "ip", "addr", "add", "198.51.100.1/24", "dev", "c-b")
    ns(PEER_B, "ip", "addr", "add", "198.51.100.2/24", "dev", "b-c")
    ns(CLIENT, "ip", "link", "set", "c-b", "up")
    ns(PEER_B, "ip", "link", "set", "b-c", "up")


def setup_wireguard() -> tuple[str, str]:
    client_key, client_public = keypair()
    a_key, a_public = keypair()
    b_key, b_public = keypair()

    ns(CLIENT, "ip", "link", "add", "wg0", "type", "wireguard")
    ns(CLIENT, "ip", "addr", "add", f"{CLIENT_INNER}/32", "dev", "wg0")
    ns(
        CLIENT,
        "wg",
        "set",
        "wg0",
        "private-key",
        "/dev/stdin",
        "peer",
        a_public,
        "endpoint",
        "192.0.2.2:51821",
        "allowed-ips",
        REMOTE_PREFIX,
        input_text=client_key + "\n",
    )
    ns(
        CLIENT,
        "wg",
        "set",
        "wg0",
        "peer",
        b_public,
        "endpoint",
        "198.51.100.2:51822",
        "allowed-ips",
        REMOTE_PREFIX,
    )
    ns(CLIENT, "ip", "link", "set", "wg0", "up")

    for namespace, ifname, listen_port, private_key in (
        (PEER_A, "wga", "51821", a_key),
        (PEER_B, "wgb", "51822", b_key),
    ):
        ns(namespace, "ip", "link", "add", ifname, "type", "wireguard")
        ns(namespace, "ip", "addr", "add", f"{REMOTE_IP}/32", "dev", ifname)
        ns(
            namespace,
            "wg",
            "set",
            ifname,
            "private-key",
            "/dev/stdin",
            "listen-port",
            listen_port,
            "peer",
            client_public,
            "allowed-ips",
            f"{CLIENT_INNER}/32",
            input_text=private_key + "\n",
        )
        ns(namespace, "ip", "route", "add", f"{CLIENT_INNER}/32", "dev", ifname)
        ns(namespace, "ip", "link", "set", ifname, "up")

    return a_public, b_public


def main() -> None:
    cleanup()
    try:
        setup_underlay()
        a_public, b_public = setup_wireguard()

        ownership = allowed_ips()
        owner = owner_for_prefix(ownership)
        if owner != b_public:
            raise RuntimeError(
                "second same-prefix assignment did not transfer ownership to peer B; "
                f"state={ownership!r}"
            )
        if REMOTE_PREFIX in ownership.get(a_public, ()):
            raise RuntimeError(f"peer A unexpectedly still owns {REMOTE_PREFIX}")
        print(f"EXP086_ALLOWEDIPS_STATE={ownership}")
        print("EXP086_ALLOWEDIPS_EXCLUSIVE=PASS")

        # Two otherwise different Linux priorities still collapse to the same egress
        # interface. The lower metric is intentionally changed between payload attempts.
        add_payload_routes(10, 20)
        before = transfers()
        ping_remote()
        after = transfers()
        selected_before = selected_peer(before, after)
        if selected_before != owner:
            raise RuntimeError(
                f"payload used {selected_before}, expected AllowedIPs owner {owner}"
            )

        add_payload_routes(200, 5)
        before = transfers()
        ping_remote()
        after = transfers()
        selected_after = selected_peer(before, after)
        if selected_after != selected_before:
            raise RuntimeError(
                "changing Linux route metrics changed WireGuard peer unexpectedly: "
                f"{selected_before} -> {selected_after}"
            )
        route = ns(CLIENT, "ip", "route", "get", REMOTE_IP).stdout.strip()
        print(f"EXP086_FIB_ROUTE={route}")
        print(f"EXP086_FIB_SELECTED_PEER={selected_after}")
        print("EXP086_FIB_PRIORITY_PEER_UNCHANGED=PASS")

        # Move only cryptokey destination ownership to A. Linux egress remains wg0.
        ns(
            CLIENT,
            "wg",
            "set",
            "wg0",
            "peer",
            a_public,
            "allowed-ips",
            REMOTE_PREFIX,
        )
        switched_state = allowed_ips()
        switched_owner = owner_for_prefix(switched_state)
        if switched_owner != a_public or switched_owner == owner:
            raise RuntimeError(
                "AllowedIPs ownership did not move to peer A as expected; "
                f"state={switched_state!r}"
            )

        before = transfers()
        ping_remote()
        after = transfers()
        selected_switched = selected_peer(before, after)
        if selected_switched != switched_owner:
            raise RuntimeError(
                f"payload used {selected_switched}, expected new AllowedIPs owner "
                f"{switched_owner}"
            )
        print(f"EXP086_SWITCHED_ALLOWEDIPS_STATE={switched_state}")
        print(f"EXP086_SWITCHED_SELECTED_PEER={selected_switched}")
        print("EXP086_ALLOWEDIPS_OWNER_SWITCH=PASS")
        print("EXP086_RESULT=PASS")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
