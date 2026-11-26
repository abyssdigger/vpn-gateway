"""Deterministic D.001 exact-observation and retirement evidence."""

from __future__ import annotations

import base64
from collections import deque
from copy import deepcopy
import hashlib
import ipaddress
import json
from pathlib import Path
import tempfile
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.managed_wireguard_adapter import (
    LinuxManagedWireGuardAdapter,
    ManagedWireGuardError,
    ManagedWireGuardState,
)
from rou.release1_config import (
    ManagedVpnKind,
    ManagedWireGuardConfig,
    ManagedWireGuardPeerConfig,
)


DEVICE = "wg-main"
IDENTITY = InterfaceIdentity("wg0", 7)
MARKER = "vpn-gate:managed-vpn:" + hashlib.sha256(DEVICE.encode()).hexdigest()
PRIVATE, PUBLIC, PEER = (
    base64.b64encode(bytes([n]) * 32).decode("ascii") for n in (1, 2, 3)
)
ADDRESS = [{"addr_info": [{"family": "inet", "local": "10.200.0.1", "prefixlen": 32}]}]
DUMP = (
    f"{PRIVATE}\t{PUBLIC}\t51820\toff\n"
    f"{PEER}\t(none)\t198.51.100.10:51820\t10.201.0.1/32,10.77.0.0/24\t0\t0\t0\t0\n"
)


def owned(**changes):
    row = {
        "ifname": "wg0", "ifindex": 7, "ifalias": MARKER,
        "linkinfo": {"info_kind": "wireguard"}, "flags": ["UP"],
    }
    row.update(changes)
    return row


class FakeRunner:
    def __init__(self, inventories, *, addresses=(), dumps=(), delete_error=False):
        self.inventories = deque(deepcopy(inventories))
        self.addresses = deque(deepcopy(addresses))
        self.dumps = deque(dumps)
        self.delete_error = delete_error
        self.commands = []
        self.mutations = []
        self.prepares = 0

    @staticmethod
    def _read(queue, fallback=None):
        if queue:
            value = queue.popleft()
        elif fallback is not None:
            value = fallback
        else:
            raise AssertionError("unexpected inventory read")
        if isinstance(value, Exception):
            raise value
        return value

    def run(self, argv):
        argv = tuple(argv)
        self.commands.append(argv)
        if argv == ("ip", "-n", "test-ns", "-d", "-j", "link", "show"):
            return json.dumps(self._read(self.inventories))
        if argv == ("ip", "-n", "test-ns", "-j", "addr", "show", "dev", "wg0"):
            return json.dumps(self._read(self.addresses, ADDRESS))
        if argv == ("ip", "netns", "exec", "test-ns", "wg", "show", "wg0", "dump"):
            return self._read(self.dumps, DUMP)
        self.mutations.append(argv)
        if argv == ("ip", "-n", "test-ns", "link", "del", "wg0"):
            if self.delete_error:
                raise OSError("injected delete failure")
            return ""
        raise AssertionError("unexpected mutation")

    def run_script(self, argv, script):
        if tuple(argv) == ("wg", "pubkey") and script == PRIVATE + "\n":
            self.prepares += 1
            return PUBLIC + "\n"
        self.mutations.append(tuple(argv))
        raise AssertionError("unexpected script mutation")


class ExactManagedWireGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        private = Path(tmp.name) / "private"
        private.write_text(PRIVATE + "\n", encoding="ascii")
        private.chmod(0o600)
        self.desired = ManagedWireGuardConfig(
            kind=ManagedVpnKind.WIREGUARD, interface="wg0",
            address=ipaddress.IPv4Interface("10.200.0.1/32"),
            private_key_file=str(private), listen_port=51820,
            peers=(ManagedWireGuardPeerConfig(
                "edge", PEER, ipaddress.IPv4Address("198.51.100.10"),
                51820, ipaddress.IPv4Address("10.201.0.1"),
            ),),
        )
        generation_runner = FakeRunner([])
        self.generation = LinuxManagedWireGuardAdapter(
            generation_runner, "test-ns"
        ).desired_generation(DEVICE, self.desired)

    def make(self, inventories, **kwargs):
        runner = FakeRunner(inventories, **kwargs)
        return LinuxManagedWireGuardAdapter(runner, "test-ns"), runner

    def retire(self, adapter, generation=None, identity=IDENTITY):
        return adapter.retire_exact(
            DEVICE, identity, self.generation if generation is None else generation,
            self.desired,
        )

    def assert_pre_mutation_failure(self, inventories, *, confirm=False, **kwargs):
        adapter, runner = self.make(inventories, **kwargs)
        with self.assertRaises(ManagedWireGuardError):
            if confirm:
                adapter.confirm_present(DEVICE, self.desired)
            else:
                self.retire(adapter)
        self.assertEqual(runner.mutations, [])
        self.assertEqual(runner.prepares, 1)

    def test_confirm_exact(self):
        adapter, runner = self.make([[owned()], [owned(stats64={"rx": 123})]])
        result = adapter.confirm_present(DEVICE, self.desired)
        self.assertEqual(result.state, ManagedWireGuardState.PRESENT)
        self.assertEqual(result.interface, IDENTITY)
        self.assertEqual(result.confirmed_generation, self.generation)
        self.assertEqual(runner.prepares, 1)
        self.assertEqual(runner.mutations, [])
        self.assertEqual(len(runner.commands), 6)

    def test_confirm_refuses_absence_and_related_drift(self):
        for rows in (
            [], [owned(ifalias=None)], [owned(ifname="renamed")],
            [owned(linkinfo={"info_kind": "dummy"})], [owned(flags=[])],
            [owned(ifalias="foreign", ifindex=8)],
            [owned(), owned(ifname="other", ifindex=8)],
        ):
            with self.subTest(rows=rows):
                self.assert_pre_mutation_failure([rows], confirm=True)

    def test_full_inventory_validation_before_relation_or_absence(self):
        unrelated = {"ifname": "other", "ifindex": 8}
        malformed = [
            [None], [{"ifname": "other"}], [{"ifname": "", "ifindex": 8}],
            [{"ifname": "a" * 16, "ifindex": 8}],
            [{"ifname": "\ud800", "ifindex": 8}],
            [{"ifname": "other", "ifindex": True}],
            [{"ifname": "other", "ifindex": 0}],
            [dict(unrelated, ifalias=123)],
            [unrelated, dict(unrelated, ifindex=9)],
            [unrelated, dict(unrelated, ifname="other2")],
        ]
        for rows in malformed:
            with self.subTest(rows=rows):
                self.assert_pre_mutation_failure([rows])
                self.assert_pre_mutation_failure([[owned(), *rows]], confirm=True)

    def test_second_read_drift(self):
        for rows in (
            [], [owned(ifindex=8)], [owned(flags=[])], [owned(ifalias=None)],
            [owned(ifname="renamed")], [owned(linkinfo={"info_kind": "dummy"})],
            [owned(), {"ifname": "other", "ifindex": 8, "ifalias": False}],
        ):
            for confirm in (True, False):
                with self.subTest(rows=rows, confirm=confirm):
                    self.assert_pre_mutation_failure([[owned()], rows], confirm=confirm)

    def test_base_drift(self):
        wrong_address = [{"addr_info": []}]
        for confirm in (True, False):
            for addresses, dumps in (
                ([wrong_address], []), ([ADDRESS, wrong_address], []),
                ([], ["wrong"]), ([], [DUMP, DUMP.replace("51820", "51821", 1)]),
            ):
                with self.subTest(confirm=confirm, addresses=addresses, dumps=dumps):
                    self.assert_pre_mutation_failure(
                        [[owned()], [owned()]], confirm=confirm,
                        addresses=addresses, dumps=dumps,
                    )

    def test_malformed_address_row_is_typed_and_never_mutates(self):
        for malformed in ([None], [17], ["text"]):
            for confirm in (True, False):
                for addresses in ([malformed], [ADDRESS, malformed]):
                    with self.subTest(malformed=malformed, confirm=confirm, addresses=addresses):
                        self.assert_pre_mutation_failure(
                            [[owned()], [owned()]], confirm=confirm, addresses=addresses
                        )

    def test_retire_argument_and_generation_guards(self):
        adapter, runner = self.make([])
        for args in ((None, self.generation), (IDENTITY, ""), (IDENTITY, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                adapter.retire_exact(DEVICE, *args, self.desired)
        with self.assertRaises(ManagedWireGuardError):
            self.retire(adapter, generation="stale")
        with self.assertRaises(ManagedWireGuardError):
            self.retire(adapter, identity=InterfaceIdentity("other", 7))
        self.assertEqual(runner.commands, [])
        self.assertEqual(runner.mutations, [])

    def test_retire_already_absent(self):
        adapter, runner = self.make([[{"ifname": "other", "ifindex": 8}]])
        result = self.retire(adapter)
        self.assertEqual(result.state, ManagedWireGuardState.ABSENT)
        self.assertIsNone(result.interface)
        self.assertIsNone(result.confirmed_generation)
        self.assertEqual(runner.mutations, [])
        self.assertEqual(runner.prepares, 1)
        self.assertEqual(len(runner.commands), 1)

    def test_retire_exact(self):
        adapter, runner = self.make(
            [[owned()], [owned(stats64={"rx": 123})], [owned()], []]
        )
        result = self.retire(adapter)
        self.assertEqual(result.state, ManagedWireGuardState.ABSENT)
        self.assertIsNone(result.interface)
        self.assertIsNone(result.confirmed_generation)
        self.assertEqual(runner.mutations, [("ip", "-n", "test-ns", "link", "del", "wg0")])
        self.assertEqual(runner.prepares, 1)
        self.assertEqual(len(runner.commands), 9)

    def test_retire_refuses_related_replacements(self):
        for rows in (
            [owned(ifalias=None)], [owned(ifname="renamed")],
            [owned(ifalias="foreign", ifindex=8, linkinfo={"info_kind": "dummy"})],
            [owned(ifalias="foreign", ifname="other")],
            [owned(ifindex=8)], [owned(), owned(ifname="other", ifindex=8)],
        ):
            with self.subTest(rows=rows):
                self.assert_pre_mutation_failure([rows])

    def test_final_by_name_guard_refuses_drift(self):
        for rows in ([], [owned(ifindex=8)], [owned(ifalias=None)]):
            with self.subTest(rows=rows):
                self.assert_pre_mutation_failure([[owned()], [owned()], rows])

    def test_retire_delete_error_and_uncertain_postcondition_no_retry(self):
        for post, error in (
            ([], True), ([owned()], False), ([owned(ifindex=8)], False),
            ([owned(ifalias="foreign", ifname="other")], False),
            ([{"ifname": "other"}], False), (OSError("read failed"), False),
        ):
            with self.subTest(post=post, error=error):
                adapter, runner = self.make(
                    [[owned()], [owned()], [owned()], post], delete_error=error,
                )
                with self.assertRaises(ManagedWireGuardError):
                    self.retire(adapter)
                self.assertEqual(
                    runner.mutations, [("ip", "-n", "test-ns", "link", "del", "wg0")]
                )
                self.assertEqual(runner.prepares, 1)

    def test_exact_inventory_read_failure(self):
        for confirm in (True, False):
            with self.subTest(confirm=confirm):
                self.assert_pre_mutation_failure([OSError("read failed")], confirm=confirm)
                self.assert_pre_mutation_failure(
                    [[owned()], OSError("read failed")], confirm=confirm
                )


if __name__ == "__main__":
    unittest.main()
