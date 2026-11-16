import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandResult, NamespaceBackend
from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import (
    ActiveConfig,
    Availability,
    Device,
    Direction,
    NatMode,
    Profile,
)
from rou.nat_kernel import apply_nat_state, verify_nat_state
from rou.nat_state import (
    ConfigNatProvider,
    ExplicitNoNatProvider,
    ExperimentalMasqueradeAllBoundProvider,
    NatPolicyBlocked,
    UnresolvedNatProvider,
)


class FakeHostBackend:
    def __init__(self, save_text=""):
        self.save_text = save_text
        self.calls = []

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append((argv, input_text))
        stdout = (
            self.save_text
            if argv[-4:] == ("iptables-legacy-save", "-c", "-t", "nat")
            else ""
        )
        return CommandResult(argv, 0, stdout, "")


def config(nat: NatMode) -> ActiveConfig:
    return ActiveConfig(
        devices={
            "oc": Device("oc", True, nat=nat),
        },
        profiles={
            "broad": Profile(
                "broad",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("10.0.0.0/8"),),
                ("oc",),
            ),
            "specific": Profile(
                "specific",
                True,
                Direction.INBOUND,
                (ipaddress.IPv4Network("10.20.0.0/16"),),
                ("oc",),
            ),
        },
    )


def bindings() -> DeviceBindingSnapshot:
    return DeviceBindingSnapshot(
        (
            BoundInterface(
                "oc",
                0,
                InterfaceIdentity("vpns00", 10),
                Availability.UNKNOWN,
            ),
        ),
        (
            BoundInterface(
                "oc",
                0,
                InterfaceIdentity("vpns01", 11),
                Availability.UNKNOWN,
            ),
        ),
    )


class NatStateTests(unittest.TestCase):
    def test_config_none_owns_empty_nat_table(self):
        state = ConfigNatProvider().compile(
            config(NatMode.NONE),
            bindings(),
        )
        self.assertIn(":POSTROUTING ACCEPT [0:0]", state.restore_text)
        self.assertNotIn("MASQUERADE", state.restore_text)

    def test_config_masquerade_is_bound_and_profile_prefix_scoped(self):
        state = ConfigNatProvider().compile(
            config(NatMode.MASQUERADE),
            bindings(),
        )
        rules = [
            line
            for line in state.restore_text.splitlines()
            if "MASQUERADE" in line
        ]
        self.assertEqual(
            rules,
            [
                "-A POSTROUTING -o vpns00 -d 10.20.0.0/16 "
                "-m addrtype ! --dst-type LOCAL -j MASQUERADE",
                "-A POSTROUTING -o vpns00 -d 10.0.0.0/8 "
                "-m addrtype ! --dst-type LOCAL -j MASQUERADE",
            ],
        )
        self.assertTrue(all("vpns01" not in line for line in rules))

    def test_unresolved_provider_remains_only_historical_gate(self):
        with self.assertRaisesRegex(NatPolicyBlocked, "Draft 4"):
            UnresolvedNatProvider().compile(
                ActiveConfig({}, {}),
                DeviceBindingSnapshot((), ()),
            )

    def test_explicit_no_nat_test_provider_owns_empty_nat_table(self):
        state = ExplicitNoNatProvider().compile(
            ActiveConfig({}, {}),
            DeviceBindingSnapshot((), ()),
        )
        self.assertNotIn("MASQUERADE", state.restore_text)

    def test_experimental_masquerade_expands_only_bound_interfaces(self):
        state = ExperimentalMasqueradeAllBoundProvider().compile(
            ActiveConfig({}, {}),
            bindings(),
        )
        self.assertIn("-o vpns00", state.restore_text)
        self.assertNotIn("vpns01", state.restore_text)

    def test_nat_apply_and_verify_use_owned_nat_table(self):
        state = ConfigNatProvider().compile(
            config(NatMode.NONE),
            bindings(),
        )
        host = FakeHostBackend(state.canonical_save + "\n")
        backend = NamespaceBackend("rou0", host)

        apply_nat_state(state, backend)
        result = verify_nat_state(state, backend)
        self.assertTrue(result.ok, (result.actual, result.expected))
        self.assertEqual(
            host.calls[0][0],
            ("ip", "netns", "exec", "rou0", "iptables-legacy-restore"),
        )


if __name__ == "__main__":
    unittest.main()
