from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import NamespaceBackend, SubprocessBackend
from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import (
    ActiveConfig,
    Device,
    Direction,
    EnvelopeAction,
    EnvelopeDirection,
    EnvelopeProtocol,
    NatMode,
    PortRange,
    Profile,
    Publication,
    TrafficEnvelope,
    TrafficEnvelopeRule,
    TransportProtocol,
)
from rou.nft_policy import (
    apply_nft_table,
    compile_nft_filter_state,
    compile_nft_nat_state,
    verify_nft_table,
)


NS = "vpn-gate-ng1-ci-nft"


def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def cleanup() -> None:
    run("ip", "netns", "del", NS, check=False)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    cleanup()
    try:
        run("ip", "netns", "add", NS)
        run("ip", "-n", NS, "link", "set", "lo", "up")
        for ifname in ("host0", "vpns00"):
            run("ip", "-n", NS, "link", "add", ifname, "type", "dummy")
            run("ip", "-n", NS, "link", "set", ifname, "up")
        run("ip", "-n", NS, "addr", "add", "192.0.2.2/30", "dev", "host0")

        ifindex = int(
            run(
                "ip", "netns", "exec", NS,
                "cat", "/sys/class/net/vpns00/ifindex",
            ).stdout.strip()
        )

        config = ActiveConfig(
            devices={
                "oc": Device(
                    "oc",
                    True,
                    nat=NatMode.MASQUERADE,
                    publications=(
                        Publication(
                            TransportProtocol.TCP,
                            PortRange(44443, 44443),
                            PortRange(44443, 44443),
                        ),
                    ),
                    traffic_envelope=TrafficEnvelope(
                        default_action=EnvelopeAction.ALLOW,
                        rules=(
                            TrafficEnvelopeRule(
                                direction=EnvelopeDirection.FROM_DEVICE,
                                action=EnvelopeAction.DROP,
                                source=ipaddress.IPv4Network("10.20.0.0/16"),
                                protocol=EnvelopeProtocol.TCP,
                                destination_ports=(PortRange(8007, 8007),),
                            ),
                        ),
                    ),
                )
            },
            profiles={
                "corp": Profile(
                    "corp",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc",),
                )
            },
        )
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns00", ifindex),
                ),
            ),
            (),
        )

        backend = NamespaceBackend(NS, SubprocessBackend())
        filter_state = compile_nft_filter_state(
            config,
            bindings,
            local_publication_address=ipaddress.IPv4Address("192.0.2.2"),
        )
        nat_state = compile_nft_nat_state(config, bindings)

        apply_nft_table(filter_state, backend)
        filter_verify = verify_nft_table(filter_state, backend)
        if not filter_verify.ok:
            print("NFT FILTER EXPECTED:")
            print(filter_verify.expected)
            print("NFT FILTER ACTUAL:")
            print(filter_verify.actual)
            return 1

        apply_nft_table(nat_state, backend)
        nat_verify = verify_nft_table(nat_state, backend)
        if not nat_verify.ok:
            print("NFT NAT EXPECTED:")
            print(nat_verify.expected)
            print("NFT NAT ACTUAL:")
            print(nat_verify.actual)
            return 1

        # Reapply both tables to exercise atomic replace of existing owned tables.
        apply_nft_table(filter_state, backend)
        apply_nft_table(nat_state, backend)
        if not verify_nft_table(filter_state, backend).ok:
            print("NFT FILTER REPLACE VERIFY FAIL")
            return 1
        if not verify_nft_table(nat_state, backend).ok:
            print("NFT NAT REPLACE VERIFY FAIL")
            return 1

        print(f"NG1_NFT_POLICY_ROUNDTRIP=PASS ifindex={ifindex}")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
