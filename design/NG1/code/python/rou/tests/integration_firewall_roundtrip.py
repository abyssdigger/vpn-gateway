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
    Availability,
    Device,
    Direction,
    EnvelopeAction,
    EnvelopeDirection,
    EnvelopeProtocol,
    NatMode,
    PortRange,
    Profile,
    TrafficEnvelope,
    TrafficEnvelopeRule,
)
from rou.firewall_kernel import apply_filter_state, verify_filter_state
from rou.firewall_state import compile_filter_state
from rou.nat_kernel import apply_nat_state, verify_nat_state
from rou.nat_state import ConfigNatProvider


NS = "vpn-gate-ng1-ci-fw"


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
        run("ip", "-n", NS, "link", "add", "host0", "type", "dummy")
        run("ip", "-n", NS, "link", "add", "vpns00", "type", "dummy")
        run("ip", "-n", NS, "link", "set", "host0", "up")
        run("ip", "-n", NS, "link", "set", "vpns00", "up")

        config = ActiveConfig(
            devices={
                "oc": Device(
                    "oc",
                    True,
                    nat=NatMode.MASQUERADE,
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
                "specific": Profile(
                    "specific",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.20.0.0/16"),),
                    ("oc",),
                ),
                "broad": Profile(
                    "broad",
                    True,
                    Direction.BIDIRECTIONAL,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc",),
                ),
            },
        )
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns00", 3),
                    Availability.UNKNOWN,
                ),
            ),
            (),
        )
        desired = compile_filter_state(config, bindings)
        backend = NamespaceBackend(NS, SubprocessBackend())

        apply_filter_state(desired, backend)
        result = verify_filter_state(desired, backend)
        if not result.ok:
            print("FILTER EXPECTED:")
            print(result.expected)
            print("FILTER ACTUAL:")
            print(result.actual)
            return 1

        nat = ConfigNatProvider().compile(config, bindings)
        apply_nat_state(nat, backend)
        nat_result = verify_nat_state(nat, backend)
        if not nat_result.ok:
            print("NAT EXPECTED:")
            print(nat_result.expected)
            print("NAT ACTUAL:")
            print(nat_result.actual)
            return 1

        print("NG1_FIREWALL_ROUNDTRIP=PASS")
        print("NG1_NAT_ROUNDTRIP=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
