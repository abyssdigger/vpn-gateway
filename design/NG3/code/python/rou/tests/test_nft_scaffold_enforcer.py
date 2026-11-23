from __future__ import annotations

import json
import unittest

from rou.forwarding_gate import (
    ForwardingGateExecutionStatus,
    ForwardingGateState,
)
from rou.nft_namespace_inventory import (
    NG3_NFT_OWNER_COMMENT,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)
from rou.nft_payload_scaffold import (
    PAYLOAD_FORWARD_CHAIN,
    PAYLOAD_NFT_SCAFFOLD,
    PAYLOAD_POSTROUTING_CHAIN,
)
from rou.nft_scaffold_enforcer import (
    PayloadNftScaffoldPrepareStatus,
    prepare_payload_nft_scaffold_once,
)
from rou.linux_nft_scaffold import LinuxNftScaffoldBackend


class FakeGate:
    def __init__(self, states, *, set_error=None):
        self.states = list(states)
        self.set_error = set_error
        self.set_calls = []

    def observe_forwarding_gate(self):
        value = self.states.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def set_forwarding_gate(self, desired):
        self.set_calls.append(desired)
        if self.set_error is not None:
            raise self.set_error


class FakeNftBackend:
    def __init__(self, observations, *, create_error=None, add_error=None):
        self.observations = list(observations)
        self.create_error = create_error
        self.add_error = add_error
        self.create_calls = 0
        self.add_calls = []

    def observe_nft_namespace(self):
        value = self.observations.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def create_payload_scaffold(self):
        self.create_calls += 1
        if self.create_error is not None:
            raise self.create_error

    def add_payload_scaffold_chains(self, missing):
        self.add_calls.append(missing)
        if self.add_error is not None:
            raise self.add_error


class FakeRunner:
    def __init__(self, outputs=None):
        self.outputs = list(outputs or ())
        self.commands = []
        self.scripts = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        if not self.outputs:
            return '{"nftables":[]}'
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def run_script(self, argv, script):
        self.commands.append(tuple(argv))
        self.scripts.append(script)
        return ""


def canonical(kind, payload):
    return NftNamespaceObject(
        kind=kind,
        canonical_json=json.dumps(
            {kind: payload},
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def chain(name):
    specs = {spec.name: spec for spec in PAYLOAD_NFT_SCAFFOLD}
    spec = specs[name]
    handle = next(
        index
        for index, candidate in enumerate(PAYLOAD_NFT_SCAFFOLD, start=1)
        if candidate.name == name
    )
    payload = {
        "family": "ip",
        "table": "vpn_gate",
        "name": name,
        "handle": handle,
        "type": spec.chain_type,
        "hook": spec.hook,
        "prio": spec.priority,
        "policy": spec.policy,
        "comment": spec.comment,
    }
    return canonical("chain", payload)


def owned(*objects):
    return NftNamespaceObservation(
        status=NftNamespaceStatus.OWNED,
        objects=tuple(objects),
        observed_comment=NG3_NFT_OWNER_COMMENT,
    )


EXACT = owned(
    *(chain(spec.name) for spec in PAYLOAD_NFT_SCAFFOLD)
)
ABSENT = NftNamespaceObservation(status=NftNamespaceStatus.ABSENT)


class NftScaffoldExecutorTests(unittest.TestCase):
    def test_barrier_failure_prevents_nft_observation_and_mutation(self):
        gate = FakeGate((RuntimeError("cannot observe"),))
        nft = FakeNftBackend((ABSENT,))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertEqual(
            result.status,
            PayloadNftScaffoldPrepareStatus.BARRIER_FAILED,
        )
        self.assertEqual(nft.create_calls, 0)
        self.assertEqual(nft.add_calls, [])

    def test_absent_namespace_is_created_only_behind_disabled_barrier(self):
        gate = FakeGate(
            (
                ForwardingGateState.ENABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        nft = FakeNftBackend((ABSENT, EXACT))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertTrue(result.confirmed)
        self.assertEqual(nft.create_calls, 1)
        self.assertEqual(
            gate.set_calls,
            [ForwardingGateState.DISABLED],
        )
        self.assertTrue(result.mutation_attempted)

    def test_missing_chain_is_repaired_without_replacing_table(self):
        partial = owned(
            *(
                chain(spec.name)
                for spec in PAYLOAD_NFT_SCAFFOLD
                if spec.name != PAYLOAD_POSTROUTING_CHAIN
            )
        )
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        nft = FakeNftBackend((partial, EXACT))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertTrue(result.confirmed)
        self.assertEqual(nft.create_calls, 0)
        self.assertEqual(len(nft.add_calls), 1)
        self.assertEqual(
            [spec.name for spec in nft.add_calls[0]],
            [PAYLOAD_POSTROUTING_CHAIN],
        )

    def test_unclassified_object_blocks_repair(self):
        rule = canonical(
            "rule",
            {
                "family": "ip",
                "table": "vpn_gate",
                "chain": "payload_forward",
                "handle": 7,
                "expr": [{"accept": None}],
            },
        )
        partial = owned(chain(PAYLOAD_FORWARD_CHAIN), rule)
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        nft = FakeNftBackend((partial,))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertEqual(
            result.status,
            PayloadNftScaffoldPrepareStatus.CONFLICT,
        )
        self.assertEqual(nft.add_calls, [])

    def test_table_conflict_blocks_mutation(self):
        conflict = NftNamespaceObservation(
            status=NftNamespaceStatus.CONFLICT,
            observed_comment="foreign",
            conflict_reason="wrong marker",
        )
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        nft = FakeNftBackend((conflict,))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertEqual(
            result.status,
            PayloadNftScaffoldPrepareStatus.CONFLICT,
        )
        self.assertEqual(nft.create_calls, 0)

    def test_barrier_lost_immediately_before_mutation_blocks_apply(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.ENABLED,
            )
        )
        nft = FakeNftBackend((ABSENT,))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertEqual(
            result.status,
            PayloadNftScaffoldPrepareStatus.BARRIER_LOST,
        )
        self.assertEqual(nft.create_calls, 0)

    def test_barrier_lost_after_apply_is_not_success(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.ENABLED,
            )
        )
        nft = FakeNftBackend((ABSENT, EXACT))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertEqual(
            result.status,
            PayloadNftScaffoldPrepareStatus.BARRIER_LOST,
        )
        self.assertFalse(result.confirmed)

    def test_apply_exception_can_still_end_confirmed(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        nft = FakeNftBackend(
            (ABSENT, EXACT),
            create_error=RuntimeError("wrapper failed"),
        )
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertTrue(result.confirmed)
        self.assertIn("independently confirmed", result.diagnostic)

    def test_noop_still_reobserves_nft_and_barrier(self):
        gate = FakeGate(
            (
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
                ForwardingGateState.DISABLED,
            )
        )
        nft = FakeNftBackend((EXACT, EXACT))
        result = prepare_payload_nft_scaffold_once(gate, nft)
        self.assertTrue(result.confirmed)
        self.assertFalse(result.mutation_attempted)

    def test_linux_backend_generates_only_fixed_scaffold_scripts(self):
        runner = FakeRunner()
        backend = LinuxNftScaffoldBackend(runner, "managed")
        backend.create_payload_scaffold()
        self.assertEqual(len(runner.scripts), 1)
        self.assertIn('comment "vpn-gate:ng3:owner-v1"', runner.scripts[0])
        self.assertIn("policy drop", runner.scripts[0])

        postrouting = next(
            spec
            for spec in PAYLOAD_NFT_SCAFFOLD
            if spec.name == PAYLOAD_POSTROUTING_CHAIN
        )
        backend.add_payload_scaffold_chains((postrouting,))
        self.assertEqual(len(runner.scripts), 2)
        self.assertIn("payload_postrouting", runner.scripts[1])
        for spec in PAYLOAD_NFT_SCAFFOLD:
            if spec.name != PAYLOAD_POSTROUTING_CHAIN:
                self.assertNotIn(spec.name, runner.scripts[1])


if __name__ == "__main__":
    unittest.main()
