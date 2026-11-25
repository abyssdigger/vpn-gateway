#!/usr/bin/env python3
"""Kernel integration evidence for production D.003 AllowedIPs ownership."""

from __future__ import annotations

from ipaddress import IPv4Network
from pathlib import Path
import subprocess
import tempfile

from rou.managed_wireguard_adapter import (
    LinuxManagedWireGuardAdapter,
    SubprocessManagedWireGuardRunner,
)
from rou.release1_config import parse_current_config
from rou.wireguard_peer_ownership import (
    WireGuardPeerAllowedIPs,
    WireGuardPeerOwnershipDesired,
    WireGuardPeerOwnershipEnforcer,
)


NS = "ng3-d003-wg"


def run(*argv: str, input_text: str | None = None) -> str:
    return subprocess.run(
        argv, input=input_text, check=True, text=True, capture_output=True
    ).stdout


def ns(*argv: str) -> str:
    return run("ip", "netns", "exec", NS, *argv)


def keypair() -> tuple[str, str]:
    private = run("wg", "genkey").strip()
    public = run("wg", "pubkey", input_text=private + "\n").strip()
    return private, public


def desired_state(cfg, interface, owner_id):
    managed = cfg.managed_vpns["wg-main"]
    shared = managed.shared_prefixes
    peers = []
    for peer in managed.peers:
        networks = [IPv4Network(f"{peer.probe_target}/32")]
        if peer.peer_id == owner_id:
            networks.extend(shared)
        peers.append(
            WireGuardPeerAllowedIPs(
                peer.public_key,
                tuple(sorted(networks)),
            )
        )
    return WireGuardPeerOwnershipDesired(
        "wg-main",
        interface,
        tuple(sorted(peers, key=lambda item: item.public_key)),
    )


def main() -> None:
    subprocess.run(("ip", "netns", "del", NS), check=False)
    try:
        run("ip", "netns", "add", NS)
        private, _ = keypair()
        _, peer_a = keypair()
        _, peer_b = keypair()
        with tempfile.TemporaryDirectory(prefix="ng3-d003-") as root_text:
            key_path = Path(root_text) / "private.key"
            key_path.write_text(private + "\n", encoding="ascii")
            key_path.chmod(0o600)
            cfg = parse_current_config(
                f"""
[device.wg-main]
enabled = true
[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "{key_path}"
[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "{peer_a}"
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"
[[device.wg-main.managed_vpn.peers]]
id = "edge-b"
public_key = "{peer_b}"
endpoint = "198.51.100.11:51820"
probe_target = "10.201.0.2"
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.77.0.0/24"]
device_order = ["wg-main"]
"""
            )
            runner = SubprocessManagedWireGuardRunner()
            adapter = LinuxManagedWireGuardAdapter(runner, NS)
            base = adapter.converge_present(
                "wg-main", cfg.managed_vpns["wg-main"]
            )
            assert base.interface is not None
            ifindex = base.interface.ifindex
            enforcer = WireGuardPeerOwnershipEnforcer(runner, NS, adapter)

            first = enforcer.converge(
                desired_state(cfg, base.interface, "edge-a")
            )
            if not first.confirmed:
                raise AssertionError(first.diagnostic)
            allowed = ns("wg", "show", "wg0", "allowed-ips")
            if allowed.count("10.77.0.0/24") != 1:
                raise AssertionError("shared prefix does not have exactly one owner")
            print("D003_WG_OWNER_A_EXACT=PASS")

            second = enforcer.converge(
                desired_state(cfg, base.interface, "edge-b")
            )
            if not second.confirmed:
                raise AssertionError(second.diagnostic)
            current = adapter.observe("wg-main")
            assert current.interface is not None
            if current.interface.ifindex != ifindex:
                raise AssertionError("D.003 owner transfer restarted wg0")
            allowed = ns("wg", "show", "wg0", "allowed-ips")
            rows = dict(line.split("\t", 1) for line in allowed.splitlines())
            if "10.77.0.0/24" in rows[peer_a]:
                raise AssertionError("old owner retained shared prefix")
            if "10.77.0.0/24" not in rows[peer_b]:
                raise AssertionError("new owner lacks shared prefix")
            if "10.201.0.1/32" not in rows[peer_a]:
                raise AssertionError("peer A probe prefix was lost")
            if "10.201.0.2/32" not in rows[peer_b]:
                raise AssertionError("peer B probe prefix was lost")
            print("D003_WG_FULL_STATE_TRANSFER=PASS")
            print("D003_WG_NO_INTERFACE_RESTART=PASS")
            print("D003_WG_RESULT=PASS")
    finally:
        subprocess.run(("ip", "netns", "del", NS), check=False)


if __name__ == "__main__":
    main()
