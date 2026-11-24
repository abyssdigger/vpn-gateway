#!/usr/bin/env python3
"""EXP-088: ten WireGuard peers, one shared prefix, restart and generation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import subprocess
import tempfile
import time


CLIENT = "exp088-client"
PEER_COUNT = 10
CLIENT_INNER = "10.200.0.1"
REMOTE_PREFIX = "10.77.0.0/24"
REMOTE_IP = "10.77.0.1"


@dataclass(frozen=True)
class Peer:
    index: int
    label: str
    namespace: str
    client_if: str
    peer_if: str
    client_underlay: str
    endpoint_ip: str
    listen_port: int
    probe_ip: str
    private_key: str
    public_key: str

    @property
    def probe_prefix(self) -> str:
        return f"{self.probe_ip}/32"


@dataclass(frozen=True)
class AvailabilityEvidence:
    owner_label: str
    generation: int


class RealizationGeneration:
    def __init__(self) -> None:
        self.value = 0

    def advance(self) -> int:
        self.value += 1
        return self.value


def host(
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
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


def cleanup(namespaces: tuple[str, ...]) -> None:
    for namespace in namespaces:
        host("ip", "netns", "del", namespace, check=False)


def keypair() -> tuple[str, str]:
    private = host("wg", "genkey").stdout.strip()
    public = host("wg", "pubkey", input_text=private + "\n").stdout.strip()
    return private, public


def build_peers() -> tuple[Peer, ...]:
    peers: list[Peer] = []
    for index in range(PEER_COUNT):
        private_key, public_key = keypair()
        base = index * 4
        peers.append(
            Peer(
                index=index,
                label=chr(ord("A") + index),
                namespace=f"exp088-p{index:02d}",
                client_if=f"c{index:02d}",
                peer_if=f"p{index:02d}",
                client_underlay=f"192.0.2.{base + 1}",
                endpoint_ip=f"192.0.2.{base + 2}",
                listen_port=51900 + index,
                probe_ip=f"10.201.0.{index + 1}",
                private_key=private_key,
                public_key=public_key,
            )
        )
    return tuple(peers)


def setup_underlay(peers: tuple[Peer, ...]) -> None:
    host("ip", "netns", "add", CLIENT)
    ns(CLIENT, "ip", "link", "set", "lo", "up")

    for peer in peers:
        host("ip", "netns", "add", peer.namespace)
        ns(peer.namespace, "ip", "link", "set", "lo", "up")

        host(
            "ip",
            "link",
            "add",
            peer.client_if,
            "type",
            "veth",
            "peer",
            "name",
            peer.peer_if,
        )
        host("ip", "link", "set", peer.client_if, "netns", CLIENT)
        host("ip", "link", "set", peer.peer_if, "netns", peer.namespace)

        ns(
            CLIENT,
            "ip",
            "addr",
            "add",
            f"{peer.client_underlay}/30",
            "dev",
            peer.client_if,
        )
        ns(
            peer.namespace,
            "ip",
            "addr",
            "add",
            f"{peer.endpoint_ip}/30",
            "dev",
            peer.peer_if,
        )
        ns(CLIENT, "ip", "link", "set", peer.client_if, "up")
        ns(peer.namespace, "ip", "link", "set", peer.peer_if, "up")


def setup_peer_wireguard(peers: tuple[Peer, ...], client_public: str) -> None:
    for peer in peers:
        ns(peer.namespace, "ip", "link", "add", "wg0", "type", "wireguard")
        ns(peer.namespace, "ip", "addr", "add", peer.probe_prefix, "dev", "wg0")
        ns(peer.namespace, "ip", "addr", "add", f"{REMOTE_IP}/32", "dev", "wg0")
        ns(
            peer.namespace,
            "wg",
            "set",
            "wg0",
            "private-key",
            "/dev/stdin",
            "listen-port",
            str(peer.listen_port),
            "peer",
            client_public,
            "allowed-ips",
            f"{CLIENT_INNER}/32",
            input_text=peer.private_key + "\n",
        )
        ns(peer.namespace, "ip", "link", "set", "wg0", "up")
        ns(
            peer.namespace,
            "ip",
            "route",
            "add",
            f"{CLIENT_INNER}/32",
            "dev",
            "wg0",
        )


def render_client_base_config(
    client_private: str,
    peers: tuple[Peer, ...],
) -> str:
    blocks = ["[Interface]", f"PrivateKey = {client_private}", ""]
    for peer in peers:
        blocks.extend(
            [
                "[Peer]",
                f"PublicKey = {peer.public_key}",
                f"Endpoint = {peer.endpoint_ip}:{peer.listen_port}",
                f"AllowedIPs = {peer.probe_prefix}",
                "",
            ]
        )
    return "\n".join(blocks)


def apply_client_base_config(
    client_private: str,
    peers: tuple[Peer, ...],
) -> None:
    config = render_client_base_config(client_private, peers)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix="exp088-wg0-",
        suffix=".conf",
        delete=False,
    ) as handle:
        handle.write(config)
        path = handle.name
    os.chmod(path, 0o600)
    try:
        ns(CLIENT, "wg", "setconf", "wg0", path)
    finally:
        os.unlink(path)


def create_client_wireguard(
    client_private: str,
    peers: tuple[Peer, ...],
) -> int:
    ns(CLIENT, "ip", "link", "add", "wg0", "type", "wireguard")
    ns(CLIENT, "ip", "addr", "add", f"{CLIENT_INNER}/32", "dev", "wg0")
    apply_client_base_config(client_private, peers)
    ns(CLIENT, "ip", "link", "set", "wg0", "up")

    for peer in peers:
        ns(CLIENT, "ip", "route", "add", peer.probe_prefix, "dev", "wg0")
    ns(CLIENT, "ip", "route", "add", REMOTE_PREFIX, "dev", "wg0")
    return interface_ifindex()


def interface_ifindex() -> int:
    output = ns(CLIENT, "ip", "-o", "link", "show", "dev", "wg0").stdout
    match = re.match(r"^(\d+):", output)
    if match is None:
        raise RuntimeError(f"cannot parse wg0 ifindex from {output!r}")
    return int(match.group(1))


def allowed_ips(peers: tuple[Peer, ...]) -> dict[str, tuple[str, ...]]:
    by_public = {peer.public_key: peer.label for peer in peers}
    result: dict[str, tuple[str, ...]] = {}
    output = ns(CLIENT, "wg", "show", "wg0", "allowed-ips").stdout
    for line in output.splitlines():
        if not line.strip():
            continue
        public_key, values = line.split("\t", 1)
        label = by_public.get(public_key)
        if label is None:
            raise RuntimeError(f"unexpected WireGuard peer {public_key!r}")
        if values.strip() == "(none)":
            result[label] = ()
        else:
            result[label] = tuple(values.replace(",", " ").split())
    return result


def transfers(peers: tuple[Peer, ...]) -> dict[str, tuple[int, int]]:
    by_public = {peer.public_key: peer.label for peer in peers}
    result: dict[str, tuple[int, int]] = {}
    output = ns(CLIENT, "wg", "show", "wg0", "transfer").stdout
    for line in output.splitlines():
        if not line.strip():
            continue
        public_key, received, sent = line.split("\t")
        label = by_public.get(public_key)
        if label is None:
            raise RuntimeError(f"unexpected WireGuard peer {public_key!r}")
        result[label] = (int(received), int(sent))
    return result


def sent_delta(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
    label: str,
) -> int:
    return after.get(label, (0, 0))[1] - before.get(label, (0, 0))[1]


def selected_peer(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> str:
    changed = [
        label
        for label in after
        if sent_delta(before, after, label) > 0
    ]
    if len(changed) != 1:
        raise RuntimeError(
            f"expected one peer tx counter to increase, got {changed!r}; "
            f"before={before!r} after={after!r}"
        )
    return changed[0]


def ping(
    target: str,
    *,
    count: int = 1,
    timeout: int = 1,
) -> subprocess.CompletedProcess[str]:
    return ns(
        CLIENT,
        "ping",
        "-n",
        "-I",
        "wg0",
        "-c",
        str(count),
        "-W",
        str(timeout),
        target,
        check=False,
    )


def require_ping(target: str, *, count: int = 2) -> None:
    result = ping(target, count=count, timeout=2)
    if result.returncode != 0:
        raise RuntimeError(
            f"ping to {target} failed unexpectedly:\n"
            f"{result.stdout}{result.stderr}"
        )


def require_no_ping(target: str) -> None:
    result = ping(target, count=1, timeout=1)
    if result.returncode == 0:
        raise RuntimeError(f"ping to {target} unexpectedly succeeded")


def assert_no_payload_owner(peers: tuple[Peer, ...]) -> dict[str, tuple[str, ...]]:
    state = allowed_ips(peers)
    if set(state) != {peer.label for peer in peers}:
        raise RuntimeError(f"incomplete peer inventory: {state!r}")
    for peer in peers:
        if set(state[peer.label]) != {peer.probe_prefix}:
            raise RuntimeError(
                f"base state for peer {peer.label} is not probe-only: {state!r}"
            )
    return state


def assert_payload_owner(
    peers: tuple[Peer, ...],
    owner_label: str,
) -> dict[str, tuple[str, ...]]:
    state = allowed_ips(peers)
    for peer in peers:
        expected = {peer.probe_prefix}
        if peer.label == owner_label:
            expected.add(REMOTE_PREFIX)
        if set(state.get(peer.label, ())) != expected:
            raise RuntimeError(
                f"unexpected AllowedIPs for owner {owner_label}: {state!r}"
            )
    return state


def apply_payload_owner(
    peers: tuple[Peer, ...],
    owner_label: str,
    generation: RealizationGeneration,
) -> int:
    if owner_label not in {peer.label for peer in peers}:
        raise ValueError(owner_label)

    args: list[str] = ["wg", "set", "wg0"]
    for peer in peers:
        values = peer.probe_prefix
        if peer.label == owner_label:
            values += f",{REMOTE_PREFIX}"
        args.extend(
            [
                "peer",
                peer.public_key,
                "allowed-ips",
                values,
            ]
        )

    ns(CLIENT, *args)
    assert_payload_owner(peers, owner_label)
    return generation.advance()


def payload_selected_peer(peers: tuple[Peer, ...], *, count: int = 2) -> str:
    before = transfers(peers)
    require_ping(REMOTE_IP, count=count)
    time.sleep(0.1)
    after = transfers(peers)
    return selected_peer(before, after)


def verify_probe_discrimination(peers: tuple[Peer, ...]) -> None:
    for peer in peers:
        before = transfers(peers)
        require_ping(peer.probe_ip)
        time.sleep(0.05)
        after = transfers(peers)
        actual = selected_peer(before, after)
        if actual != peer.label:
            raise RuntimeError(
                f"probe {peer.probe_ip} selected peer {actual}, "
                f"expected {peer.label}"
            )


def set_underlay(peer: Peer, up: bool) -> None:
    ns(
        peer.namespace,
        "ip",
        "link",
        "set",
        peer.peer_if,
        "up" if up else "down",
    )


def evidence_is_current(
    evidence: AvailabilityEvidence,
    generation: RealizationGeneration,
) -> bool:
    return evidence.generation == generation.value


def require_stale(
    evidence: AvailabilityEvidence,
    generation: RealizationGeneration,
) -> None:
    if evidence_is_current(evidence, generation):
        raise RuntimeError(
            f"evidence from generation {evidence.generation} incorrectly remained current"
        )


def parse_ping_summary(output: str) -> tuple[int, int]:
    match = re.search(
        r"(\d+) packets transmitted, (\d+) received",
        output,
    )
    if match is None:
        raise RuntimeError(f"cannot parse ping summary:\n{output}")
    return int(match.group(1)), int(match.group(2))


def transition_observation(
    peers: tuple[Peer, ...],
    generation: RealizationGeneration,
) -> str:
    owner_a = peers[0]
    owner_b = peers[1]

    for peer in peers:
        set_underlay(peer, True)
    require_ping(owner_a.probe_ip)
    require_ping(owner_b.probe_ip)

    if payload_selected_peer(peers) != owner_a.label:
        raise RuntimeError("transition observation did not start on peer A")

    command = [
        "ip",
        "netns",
        "exec",
        CLIENT,
        "ping",
        "-n",
        "-q",
        "-I",
        "wg0",
        "-c",
        "200",
        "-i",
        "0.02",
        "-W",
        "1",
        REMOTE_IP,
    ]
    process = subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(0.5)
    before_apply = transfers(peers)
    started = time.monotonic()
    apply_payload_owner(peers, owner_b.label, generation)
    confirmed = time.monotonic()
    after_apply = transfers(peers)

    stdout, stderr = process.communicate(timeout=15)
    if process.returncode not in (0, 1):
        raise RuntimeError(
            f"parallel transition ping failed rc={process.returncode}:\n"
            f"{stdout}{stderr}"
        )
    transmitted, received = parse_ping_summary(stdout)
    loss = transmitted - received

    post_before = transfers(peers)
    require_ping(REMOTE_IP, count=20)
    time.sleep(0.1)
    post_after = transfers(peers)
    post_old_delta = sent_delta(post_before, post_after, owner_a.label)
    post_new_delta = sent_delta(post_before, post_after, owner_b.label)
    if post_old_delta != 0 or post_new_delta <= 0:
        raise RuntimeError(
            "after confirmed switch, payload did not remain exclusively on peer B: "
            f"old_delta={post_old_delta}, new_delta={post_new_delta}"
        )

    old_during = sent_delta(before_apply, after_apply, owner_a.label)
    new_during = sent_delta(before_apply, after_apply, owner_b.label)
    elapsed_ms = (confirmed - started) * 1000.0
    return (
        f"lost_packets={loss};"
        f"confirm_ms={elapsed_ms:.3f};"
        f"old_tx_bytes_during_confirm={old_during};"
        f"new_tx_bytes_during_confirm={new_during};"
        f"post_confirm_old_tx_bytes={post_old_delta};"
        f"post_confirm_new_tx_bytes={post_new_delta}"
    )


def verify_failed_apply_does_not_confirm(
    peers: tuple[Peer, ...],
    owner_label: str,
    generation: RealizationGeneration,
) -> None:
    before_generation = generation.value
    before_state = assert_payload_owner(peers, owner_label)
    failed = ns(
        CLIENT,
        "wg",
        "set",
        "wg-missing",
        "peer",
        peers[1].public_key,
        "allowed-ips",
        f"{peers[1].probe_prefix},{REMOTE_PREFIX}",
        check=False,
    )
    if failed.returncode == 0:
        raise RuntimeError("deliberately invalid wg set unexpectedly succeeded")
    after_state = assert_payload_owner(peers, owner_label)
    if before_state != after_state:
        raise RuntimeError("failed apply changed confirmed AllowedIPs state")
    if generation.value != before_generation:
        raise RuntimeError("failed apply advanced realization generation")


def main() -> None:
    client_private, client_public = keypair()
    peers = build_peers()
    namespaces = (CLIENT,) + tuple(peer.namespace for peer in peers)
    generation = RealizationGeneration()

    cleanup(namespaces)
    try:
        setup_underlay(peers)
        setup_peer_wireguard(peers, client_public)
        initial_ifindex = create_client_wireguard(client_private, peers)

        initial_state = assert_no_payload_owner(peers)
        require_no_ping(REMOTE_IP)
        print(f"EXP088_BASE_STATE={initial_state}")
        print("EXP088_BASE_NO_OWNER=PASS")

        verify_probe_discrimination(peers)
        print("EXP088_TEN_PEER_PROBES=PASS")

        apply_payload_owner(peers, "A", generation)
        if payload_selected_peer(peers) != "A":
            raise RuntimeError("initial shared-prefix selection did not use peer A")
        profile_evidence = AvailabilityEvidence("A", generation.value)
        print("EXP088_INITIAL_SELECT=PASS")

        for current_index in range(PEER_COUNT - 1):
            current = peers[current_index]
            next_peer = peers[current_index + 1]

            set_underlay(current, False)
            require_no_ping(current.probe_ip)
            require_ping(next_peer.probe_ip)

            previous_evidence = profile_evidence
            apply_payload_owner(peers, next_peer.label, generation)
            require_stale(previous_evidence, generation)
            if payload_selected_peer(peers) != next_peer.label:
                raise RuntimeError(
                    f"failover from {current.label} did not use {next_peer.label}"
                )
            profile_evidence = AvailabilityEvidence(
                next_peer.label,
                generation.value,
            )

        if profile_evidence.owner_label != "J":
            raise RuntimeError(f"ordered failover ended on {profile_evidence!r}")
        print("EXP088_ORDERED_FAILOVER=PASS")
        print("EXP088_GENERATION_REJECTS_STALE=PASS")

        for peer in peers:
            set_underlay(peer, True)
        require_ping(peers[0].probe_ip)

        previous_evidence = profile_evidence
        apply_payload_owner(peers, "A", generation)
        require_stale(previous_evidence, generation)
        if payload_selected_peer(peers) != "A":
            raise RuntimeError("recovery did not return payload to peer A")
        profile_evidence = AvailabilityEvidence("A", generation.value)
        print("EXP088_RECOVERY=PASS")

        transition = transition_observation(peers, generation)
        require_stale(profile_evidence, generation)
        profile_evidence = AvailabilityEvidence("B", generation.value)
        print(f"EXP088_TRANSITION_OBSERVATION={transition}")

        before_restart_ifindex = interface_ifindex()
        ns(CLIENT, "ip", "link", "del", "wg0")
        after_restart_ifindex = create_client_wireguard(client_private, peers)
        generation.advance()
        require_stale(profile_evidence, generation)

        restart_state = assert_no_payload_owner(peers)
        require_no_ping(REMOTE_IP)
        verify_probe_discrimination(peers)
        print(
            "EXP088_RESTART_STATE="
            f"before_ifindex={before_restart_ifindex};"
            f"after_ifindex={after_restart_ifindex};"
            f"allowed_ips={restart_state}"
        )
        print("EXP088_RESTART_RESETS_OWNER=PASS")

        apply_payload_owner(peers, "A", generation)
        if payload_selected_peer(peers) != "A":
            raise RuntimeError("fresh selection after restart did not use peer A")

        verify_failed_apply_does_not_confirm(peers, "A", generation)
        print("EXP088_CONFIRMED_APPLY=PASS")

        if initial_ifindex == after_restart_ifindex:
            print("EXP088_IFINDEX_REUSE=OBSERVED")
        else:
            print("EXP088_IFINDEX_REUSE=NOT_OBSERVED")

        print("EXP088_RESULT=PASS")
    finally:
        cleanup(namespaces)


if __name__ == "__main__":
    main()
