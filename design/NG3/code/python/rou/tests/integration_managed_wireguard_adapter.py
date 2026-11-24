#!/usr/bin/env python3
"""Integration evidence for production D.001 managed WireGuard Adapter."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from rou.managed_wireguard_adapter import (
    LinuxManagedWireGuardAdapter,
    ManagedWireGuardError,
    ManagedWireGuardState,
    SubprocessManagedWireGuardRunner,
)
from rou.release1_config import parse_current_config


NS = "ng3-d001-wg"


def run(*argv: str, check: bool = True, input_text: str | None = None) -> str:
    completed = subprocess.run(
        argv,
        check=check,
        input=input_text,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def ns(*argv: str) -> str:
    return run("ip", "netns", "exec", NS, *argv)


def keypair() -> tuple[str, str]:
    private = run("wg", "genkey").strip()
    public = run("wg", "pubkey", input_text=private + "\n").strip()
    return private, public


def config_text(
    private_path: Path,
    psk_path: Path,
    peer_a_public: str,
    peer_b_public: str,
    *,
    reverse_peers: bool = False,
) -> str:
    peer_a = f"""
[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "{peer_a_public}"
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"
preshared_key_file = "{psk_path}"
"""
    peer_b = f"""
[[device.wg-main.managed_vpn.peers]]
id = "edge-b"
public_key = "{peer_b_public}"
endpoint = "198.51.100.11:51820"
probe_target = "10.201.0.2"
"""
    peers = peer_b + peer_a if reverse_peers else peer_a + peer_b
    return f"""
[device.wg-main]
enabled = true
use_outbound_nat = true

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "{private_path}"
listen_port = 51820
{peers}
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.77.0.0/24"]
device_order = ["wg-main"]
"""


def main() -> None:
    subprocess.run(("ip", "netns", "del", NS), check=False)
    try:
        run("ip", "netns", "add", NS)
        ns("ip", "link", "set", "lo", "up")

        private_a, _ = keypair()
        _, peer_a_public = keypair()
        _, peer_b_public = keypair()
        private_c, public_c = keypair()
        psk = run("wg", "genpsk").strip()

        with tempfile.TemporaryDirectory(prefix="ng3-d001-wg-") as root_text:
            root = Path(root_text)
            private_path = root / "private.key"
            psk_path = root / "peer.psk"
            private_path.write_text(private_a + "\n", encoding="ascii")
            psk_path.write_text(psk + "\n", encoding="ascii")
            private_path.chmod(0o600)
            psk_path.chmod(0o600)

            cfg = parse_current_config(
                config_text(
                    private_path,
                    psk_path,
                    peer_a_public,
                    peer_b_public,
                )
            )
            desired = cfg.managed_vpns["wg-main"]
            adapter = LinuxManagedWireGuardAdapter(
                SubprocessManagedWireGuardRunner(),
                NS,
            )

            ns("ip", "link", "add", "wg0", "type", "dummy")
            try:
                adapter.converge_present("wg-main", desired)
            except ManagedWireGuardError:
                pass
            else:
                raise AssertionError("foreign same-name wg0 was adopted")
            kind = run("ip", "-n", NS, "-d", "-j", "link", "show", "dev", "wg0")
            if '"info_kind":"dummy"' not in kind.replace(" ", ""):
                raise AssertionError("foreign dummy wg0 was changed")
            ns("ip", "link", "del", "wg0")
            print("D001_WG_FOREIGN_PRESENT_REJECTED=PASS")

            first = adapter.converge_present("wg-main", desired)
            if first.state is not ManagedWireGuardState.PRESENT:
                raise AssertionError("managed WireGuard did not become present")
            if first.confirmed_generation is None:
                raise AssertionError("confirmed generation is missing")
            assert first.interface is not None
            first_ifindex = first.interface.ifindex
            print("D001_WG_START_CONFIRMED=PASS")

            repeated = adapter.converge_present("wg-main", desired)
            assert repeated.interface is not None
            if repeated.interface.ifindex != first_ifindex:
                raise AssertionError("exact present was unnecessarily recreated")
            if repeated.confirmed_generation != first.confirmed_generation:
                raise AssertionError("same desired generation changed")
            print("D001_WG_IDEMPOTENT_PRESENT=PASS")

            reordered_desired = parse_current_config(
                config_text(
                    private_path,
                    psk_path,
                    peer_a_public,
                    peer_b_public,
                    reverse_peers=True,
                )
            ).managed_vpns["wg-main"]
            reordered = adapter.converge_present("wg-main", reordered_desired)
            assert reordered.interface is not None
            if reordered.interface.ifindex != first_ifindex:
                raise AssertionError("peer preference reorder recreated base interface")
            if reordered.confirmed_generation != first.confirmed_generation:
                raise AssertionError("peer preference reorder changed D.001 base generation")
            print("D001_WG_PEER_ORDER_NOT_BASE_GENERATION=PASS")

            ns(
                "wg",
                "set",
                "wg0",
                "peer",
                peer_a_public,
                "allowed-ips",
                "10.201.0.1/32,10.77.0.0/24",
            )
            with_dynamic = adapter.converge_present("wg-main", desired)
            assert with_dynamic.interface is not None
            if with_dynamic.interface.ifindex != first_ifindex:
                raise AssertionError(
                    "D.001 restarted interface because of D.002-owned AllowedIPs"
                )
            allowed = ns("wg", "show", "wg0", "allowed-ips")
            if "10.77.0.0/24" not in allowed:
                raise AssertionError("D.001 removed D.002-owned shared prefix")
            print("D001_WG_DYNAMIC_ALLOWEDIPS_IGNORED=PASS")

            private_path.chmod(0o640)
            try:
                adapter.converge_present("wg-main", desired)
            except ManagedWireGuardError:
                pass
            else:
                raise AssertionError("unsafe private-key permissions were accepted")
            current = adapter.observe("wg-main")
            assert current.interface is not None
            if current.interface.ifindex != first_ifindex:
                raise AssertionError("secret precondition failure mutated interface")
            private_path.chmod(0o600)
            print("D001_WG_SECRET_PRECONDITION=PASS")

            private_path.write_text(private_c + "\n", encoding="ascii")
            private_path.chmod(0o600)
            changed = adapter.converge_present("wg-main", desired)
            assert changed.interface is not None
            if changed.confirmed_generation == first.confirmed_generation:
                raise AssertionError("same-path private-key change kept old generation")
            observed_public = ns("wg", "show", "wg0", "public-key").strip()
            if observed_public != public_c:
                raise AssertionError("changed private-key generation was not applied")
            allowed = ns("wg", "show", "wg0", "allowed-ips")
            if "10.77.0.0/24" in allowed:
                raise AssertionError("base restart retained dynamic shared-prefix owner")
            print("D001_WG_CHANGED_SECRET_RESTART=PASS")

            absent = adapter.converge_absent("wg-main")
            if absent.state is not ManagedWireGuardState.ABSENT:
                raise AssertionError("managed WireGuard stop was not confirmed")
            if adapter.observe("wg-main").state is not ManagedWireGuardState.ABSENT:
                raise AssertionError("managed WireGuard marker remains after stop")
            print("D001_WG_STOP_CONFIRMED=PASS")

            ns("ip", "link", "add", "wg0", "type", "dummy")
            absent_foreign = adapter.converge_absent("wg-main")
            if absent_foreign.state is not ManagedWireGuardState.ABSENT:
                raise AssertionError("foreign interface changed managed absence")
            kind = run("ip", "-n", NS, "-d", "-j", "link", "show", "dev", "wg0")
            if '"info_kind":"dummy"' not in kind.replace(" ", ""):
                raise AssertionError("converge_absent deleted foreign same-name link")
            print("D001_WG_FOREIGN_STOP_PRESERVED=PASS")

        print("D001_WG_RESULT=PASS")
    finally:
        subprocess.run(("ip", "netns", "del", NS), check=False)


if __name__ == "__main__":
    main()
