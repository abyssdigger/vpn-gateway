from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandResult, NamespaceBackend
from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import ActiveConfig, Availability
from rou.nat_kernel import apply_nat_state, verify_nat_state
from rou.nat_state import (
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


class NatStateTests(unittest.TestCase):
    def test_unresolved_provider_blocks_production_inference(self):
        with self.assertRaisesRegex(NatPolicyBlocked, "unresolved"):
            UnresolvedNatProvider().compile(
                ActiveConfig({}, {}),
                DeviceBindingSnapshot((), ()),
            )

    def test_explicit_no_nat_owns_empty_nat_table(self):
        state = ExplicitNoNatProvider().compile(
            ActiveConfig({}, {}),
            DeviceBindingSnapshot((), ()),
        )
        self.assertIn(":POSTROUTING ACCEPT [0:0]", state.restore_text)
        self.assertNotIn("MASQUERADE", state.restore_text)

    def test_experimental_masquerade_expands_only_bound_interfaces(self):
        bindings = DeviceBindingSnapshot(
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
        state = ExperimentalMasqueradeAllBoundProvider().compile(
            ActiveConfig({}, {}),
            bindings,
        )
        self.assertIn("-o vpns00", state.restore_text)
        self.assertNotIn("vpns01", state.restore_text)

    def test_nat_apply_and_verify_use_owned_nat_table(self):
        state = ExplicitNoNatProvider().compile(
            ActiveConfig({}, {}),
            DeviceBindingSnapshot((), ()),
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
