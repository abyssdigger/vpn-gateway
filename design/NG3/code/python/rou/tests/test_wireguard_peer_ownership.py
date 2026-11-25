from __future__ import annotations

from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.managed_wireguard_adapter import (
    ManagedWireGuardObservation,
    ManagedWireGuardState,
)
from rou.wireguard_peer_ownership import (
    WireGuardPeerAllowedIPs,
    WireGuardPeerOwnershipDesired,
    WireGuardPeerOwnershipEnforcer,
)


IFACE = InterfaceIdentity("wg0", 17)
A = "a-key"
B = "b-key"
A_PROBE = IPv4Network("10.200.0.1/32")
B_PROBE = IPv4Network("10.200.0.2/32")
SHARED = IPv4Network("10.77.0.0/24")


def dump(a: str, b: str) -> str:
    return (
        "priv\tpub\t0\toff\n"
        f"{A}\t(none)\t198.51.100.1:51820\t{a}\t0\t0\t0\toff\n"
        f"{B}\t(none)\t198.51.100.2:51820\t{b}\t0\t0\t0\toff\n"
    )


def desired() -> WireGuardPeerOwnershipDesired:
    return WireGuardPeerOwnershipDesired(
        "wg-main",
        IFACE,
        (
            WireGuardPeerAllowedIPs(A, (SHARED, A_PROBE)),
            WireGuardPeerAllowedIPs(B, (B_PROBE,)),
        ),
    )


class BaseObserver:
    def __init__(self, interface=IFACE):
        self.interface = interface

    def observe(self, device_id):
        return ManagedWireGuardObservation(
            device_id,
            ManagedWireGuardState.PRESENT,
            self.interface,
        )


class Runner:
    def __init__(self, observations, *, apply_error=None):
        self.observations = list(observations)
        self.apply_error = apply_error
        self.commands = []

    def run(self, argv):
        command = tuple(argv)
        self.commands.append(command)
        if "show" in command:
            return self.observations.pop(0)
        if self.apply_error is not None:
            raise self.apply_error
        return ""


class WireGuardPeerOwnershipTests(unittest.TestCase):
    def test_exact_state_is_noop(self):
        runner = Runner(
            [dump("10.77.0.0/24,10.200.0.1/32", "10.200.0.2/32")]
        )
        result = WireGuardPeerOwnershipEnforcer(
            runner, "vpn-gate", BaseObserver()
        ).converge(desired())
        self.assertTrue(result.confirmed)
        self.assertFalse(result.changed)
        self.assertEqual(sum("set" in cmd for cmd in runner.commands), 0)

    def test_mismatch_applies_one_complete_state_then_fresh_confirms(self):
        runner = Runner(
            [
                dump("10.200.0.1/32", "10.77.0.0/24,10.200.0.2/32"),
                dump("10.77.0.0/24,10.200.0.1/32", "10.200.0.2/32"),
            ]
        )
        result = WireGuardPeerOwnershipEnforcer(
            runner, "vpn-gate", BaseObserver()
        ).converge(desired())
        self.assertTrue(result.confirmed)
        self.assertTrue(result.changed)
        apply = next(cmd for cmd in runner.commands if "set" in cmd)
        self.assertEqual(apply.count("peer"), 2)
        self.assertIn("10.77.0.0/24,10.200.0.1/32", apply)
        self.assertIn("10.200.0.2/32", apply)

    def test_apply_exception_can_still_end_confirmed_by_fresh_state(self):
        runner = Runner(
            [
                dump("10.200.0.1/32", "10.77.0.0/24,10.200.0.2/32"),
                dump("10.77.0.0/24,10.200.0.1/32", "10.200.0.2/32"),
            ],
            apply_error=RuntimeError("reported failure"),
        )
        result = WireGuardPeerOwnershipEnforcer(
            runner, "vpn-gate", BaseObserver()
        ).converge(desired())
        self.assertTrue(result.confirmed)

    def test_post_apply_mismatch_is_unconfirmed(self):
        runner = Runner(
            [
                dump("10.200.0.1/32", "10.77.0.0/24,10.200.0.2/32"),
                dump("10.200.0.1/32", "10.77.0.0/24,10.200.0.2/32"),
            ]
        )
        result = WireGuardPeerOwnershipEnforcer(
            runner, "vpn-gate", BaseObserver()
        ).converge(desired())
        self.assertFalse(result.confirmed)
        self.assertIn("not exact", result.diagnostic)

    def test_stale_base_interface_generation_blocks_mutation(self):
        runner = Runner([])
        result = WireGuardPeerOwnershipEnforcer(
            runner,
            "vpn-gate",
            BaseObserver(InterfaceIdentity("wg0", 18)),
        ).converge(desired())
        self.assertFalse(result.confirmed)
        self.assertFalse(result.changed)
        self.assertEqual(runner.commands, [])


if __name__ == "__main__":
    unittest.main()
