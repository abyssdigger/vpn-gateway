#!/usr/bin/env python3
"""EXP-087: runtime WireGuard AllowedIPs failover with peer-specific probe /32s."""

from __future__ import annotations

import subprocess
import time


CLIENT = "exp087-client"
PEER_A = "exp087-a"
PEER_B = "exp087-b"
NAMESPACES = (CLIENT, PEER_A, PEER_B)

CLIENT_INNER = "10.200.0.1"
PROBE_A = "10.201.0.1"
PROBE_B = "10.201.0.2"
PROBE_A_PREFIX = f"{PROBE_A}/32"
PROBE_B_PREFIX = f"{PROBE_B}/32"
REMOTE_PREFIX = "10.77.0.0/24"
REMOTE_IP = "10.77.0.1"

A_ENDPOINT_IP = "192.0.2.2"
B_ENDPOINT_IP = "198.51.100.2"


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
            f"command failed rc={completed.returncode}: {args!r}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
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


def setup_underlay() -> None:
    for namespace in NAMESPACES:
        host("ip", "netns", "add", namespace)
        ns(namespace, "ip", "link", "set", "lo", "up")

    host("ip", "link", "add", "c-a", "type", "veth", "peer", "name", "a-c")
    host("ip", "link", "set", "c-a", "netns", CLIENT)
    host("ip", "link", "set", "a-c", "netns", PEER_A)
    ns(CLIENT, "ip", "addr", "add", "192.0.2.1/24", "dev", "c-a")
    ns(PEER_A, "ip", "addr", "add", f"{A_ENDPOINT_IP}/24", "dev", "a-c")
    ns(CLIENT, "ip", "link", "set", "c-a", "up")
    ns(PEER_A, "ip", "link", "set", "a-c", "up")

    host("ip", "link", "add", "c-b", "type", "veth", "peer", "name", "b-c")
    host("ip", "link", "set", "c-b", "netns", CLIENT)
    host("ip", "link", "set", "b-c", "netns", PEER_B)
    ns(CLIENT, "ip", "addr", "add", "198.51.100.1/24", "dev", "c-b")
    ns(PEER_B, "ip", "addr", "add", f"{B_ENDPOINT_IP}/24", "dev", "b-c")
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
        f"{A_ENDPOINT_IP}:51821",
        "allowed-ips",
        f"{PROBE_A_PREFIX},{REMOTE_PREFIX}",
        "peer",
        b_public,
        "endpoint",
        f"{B_ENDPOINT_IP}:51822",
        "allowed-ips",
        PROBE_B_PREFIX,
        input_text=client_key + "\n",
    )
    ns(CLIENT, "ip", "link", "set", "wg0", "up")
    ns(CLIENT, "ip", "route", "add", PROBE_A_PREFIX, "dev", "wg0")
    ns(CLIENT, "ip", "route", "add", PROBE_B_PREFIX, "dev", "wg0")
    ns(CLIENT, "ip", "route", "add", REMOTE_PREFIX, "dev", "wg0")

    for namespace, ifname, listen_port, private_key, probe_ip in (
        (PEER_A, "wga", "51821", a_key, PROBE_A),
        (PEER_B, "wgb", "51822", b_key, PROBE_B),
    ):
        ns(namespace, "ip", "link", "add", ifname, "type", "wireguard")
        ns(namespace, "ip", "addr", "add", f"{probe_ip}/32", "dev", ifname)
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
        ns(namespace, "ip", "link", "set", ifname, "up")
        ns(namespace, "ip", "route", "add", f"{CLIENT_INNER}/32", "dev", ifname)

    return a_public, b_public


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
            result[peer] = tuple(values.replace(",", " ").split())
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


def selected_peer(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> str:
    changed = []
    for peer in after:
        before_sent = before.get(peer, (0, 0))[1]
        if after[peer][1] > before_sent:
            changed.append(peer)
    if len(changed) != 1:
        raise RuntimeError(
            f"expected exactly one peer tx counter to increase, got {changed!r}; "
            f"before={before!r} after={after!r}"
        )
    return changed[0]


def ping(target: str, *, interface: str = "wg0", count: int = 1, timeout: int = 1) -> subprocess.CompletedProcess[str]:
    return ns(
        CLIENT,
        "ping",
        "-n",
        "-I",
        interface,
        "-c",
        str(count),
        "-W",
        str(timeout),
        target,
        check=False,
    )


def require_ping(target: str) -> None:
    result = ping(target, count=2, timeout=2)
    if result.returncode != 0:
        raise RuntimeError(
            f"ping to {target} failed unexpectedly:\n{result.stdout}{result.stderr}"
        )


def require_no_ping(target: str) -> None:
    result = ping(target, count=1, timeout=1)
    if result.returncode == 0:
        raise RuntimeError(f"ping to {target} unexpectedly succeeded")


def apply_payload_owner(a_public: str, b_public: str, owner: str) -> None:
    if owner not in {"A", "B"}:
        raise ValueError(owner)
    a_allowed = PROBE_A_PREFIX + (f",{REMOTE_PREFIX}" if owner == "A" else "")
    b_allowed = PROBE_B_PREFIX + (f",{REMOTE_PREFIX}" if owner == "B" else "")
    # One runtime wg(8) invocation carries the complete desired AllowedIPs for both peers.
    # No config file is written or reloaded.
    ns(
        CLIENT,
        "wg",
        "set",
        "wg0",
        "peer",
        a_public,
        "allowed-ips",
        a_allowed,
        "peer",
        b_public,
        "allowed-ips",
        b_allowed,
    )


def assert_state(a_public: str, b_public: str, owner: str) -> dict[str, tuple[str, ...]]:
    state = allowed_ips()
    expected_a = {PROBE_A_PREFIX}
    expected_b = {PROBE_B_PREFIX}
    if owner == "A":
        expected_a.add(REMOTE_PREFIX)
    else:
        expected_b.add(REMOTE_PREFIX)
    if set(state.get(a_public, ())) != expected_a:
        raise RuntimeError(f"unexpected peer A AllowedIPs: {state!r}")
    if set(state.get(b_public, ())) != expected_b:
        raise RuntimeError(f"unexpected peer B AllowedIPs: {state!r}")
    return state


def payload_selected_peer() -> str:
    before = transfers()
    require_ping(REMOTE_IP)
    time.sleep(0.1)
    after = transfers()
    return selected_peer(before, after)


def test_transport_endpoint_probe_shape() -> None:
    # Underlay host is alive.
    direct = ns(CLIENT, "ping", "-n", "-c", "1", "-W", "1", A_ENDPOINT_IP, check=False)
    if direct.returncode != 0:
        raise RuntimeError(
            "peer A underlay endpoint is not reachable for control check:\n"
            + direct.stdout
            + direct.stderr
        )

    # Mimic the accepted probe routing shape without disturbing WireGuard's own UDP route:
    # local output bound to wg0 is selected into a dedicated table whose target /32 points
    # to wg0. The transport endpoint itself is intentionally not in any peer AllowedIPs.
    ns(CLIENT, "ip", "route", "add", f"{A_ENDPOINT_IP}/32", "dev", "wg0", "table", "100")
    ns(
        CLIENT,
        "ip",
        "rule",
        "add",
        "priority",
        "100",
        "to",
        f"{A_ENDPOINT_IP}/32",
        "oif",
        "wg0",
        "lookup",
        "100",
    )
    forced = ping(A_ENDPOINT_IP, count=1, timeout=1)
    ns(
        CLIENT,
        "ip",
        "rule",
        "del",
        "priority",
        "100",
        "to",
        f"{A_ENDPOINT_IP}/32",
        "oif",
        "wg0",
        "lookup",
        "100",
        check=False,
    )
    ns(CLIENT, "ip", "route", "flush", "table", "100", check=False)
    if forced.returncode == 0:
        raise RuntimeError(
            "transport endpoint unexpectedly became a valid in-tunnel ICMP target"
        )
    print("EXP087_TRANSPORT_ENDPOINT_PROBE_UNSUITABLE=PASS")


def main() -> None:
    cleanup()
    try:
        setup_underlay()
        a_public, b_public = setup_wireguard()

        state = assert_state(a_public, b_public, "A")
        print(f"EXP087_INITIAL_ALLOWEDIPS={state}")
        print("EXP087_RUNTIME_ONLY_ALLOWEDIPS=PASS")

        test_transport_endpoint_probe_shape()

        before = transfers()
        require_ping(PROBE_A)
        after_a = transfers()
        selected_a = selected_peer(before, after_a)
        before_b = after_a
        require_ping(PROBE_B)
        after_b = transfers()
        selected_b = selected_peer(before_b, after_b)
        if selected_a != a_public or selected_b != b_public:
            raise RuntimeError(
                "peer-specific probe targets did not select their expected peers: "
                f"A={selected_a} B={selected_b}"
            )
        print("EXP087_PEER_PROBE_DISCRIMINATION=PASS")

        initial_payload_peer = payload_selected_peer()
        if initial_payload_peer != a_public:
            raise RuntimeError(
                f"initial payload used {initial_payload_peer}, expected peer A {a_public}"
            )

        # Make only A unavailable. B's unique probe /32 remains usable through the same wg0.
        ns(PEER_A, "ip", "link", "set", "a-c", "down")
        require_no_ping(PROBE_A)
        require_ping(PROBE_B)

        apply_payload_owner(a_public, b_public, "B")
        failed_over_state = assert_state(a_public, b_public, "B")
        failed_over_peer = payload_selected_peer()
        if failed_over_peer != b_public:
            raise RuntimeError(
                f"payload after failover used {failed_over_peer}, expected peer B {b_public}"
            )
        print(f"EXP087_FAILOVER_ALLOWEDIPS={failed_over_state}")
        print("EXP087_FAILOVER_TO_B=PASS")

        ns(PEER_A, "ip", "link", "set", "a-c", "up")
        require_ping(PROBE_A)

        apply_payload_owner(a_public, b_public, "A")
        recovered_state = assert_state(a_public, b_public, "A")
        recovered_peer = payload_selected_peer()
        if recovered_peer != a_public:
            raise RuntimeError(
                f"payload after recovery used {recovered_peer}, expected peer A {a_public}"
            )
        print(f"EXP087_RECOVERY_ALLOWEDIPS={recovered_state}")
        print("EXP087_RECOVERY_TO_A=PASS")
        print("EXP087_RESULT=PASS")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
