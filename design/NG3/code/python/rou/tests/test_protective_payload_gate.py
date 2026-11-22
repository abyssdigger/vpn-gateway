from __future__ import annotations

import json
import unittest

from rou.protective_payload_gate import (
    ProtectivePayloadGateDesired,
    ProtectivePayloadGateEnforcementStatus,
    ProtectivePayloadGateObservation,
    ProtectivePayloadGateObservationStatus,
    ProtectivePayloadGateState,
    converge_protective_payload_gate_once,
)
from rou.linux_protective_payload_gate import (
    PROTECTIVE_NFT_FAMILY,
    PROTECTIVE_NFT_OWNER_COMMENT,
    PROTECTIVE_NFT_TABLE,
    LinuxProtectivePayloadGateDriver,
    parse_protective_payload_gate_ruleset,
)


def desired_enabled() -> ProtectivePayloadGateDesired:
    return ProtectivePayloadGateDesired(
        ProtectivePayloadGateState.ENABLED,
        "stack0",
    )


class FakeDriver:
    def __init__(self, observations, *, apply_error=None):
        self.observations = list(observations)
        self.apply_error = apply_error
        self.apply_calls = []

    def observe_protective_payload_gate(self, desired):
        value = self.observations.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def apply_protective_payload_gate(self, desired, initial):
        self.apply_calls.append((desired, initial))
        if self.apply_error is not None:
            raise self.apply_error


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.commands = []
        self.scripts = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def run_script(self, argv, script):
        self.commands.append(tuple(argv))
        self.scripts.append(script)


def obs(status, reason=None):
    return ProtectivePayloadGateObservation(status, reason)


def nft_doc(*rows):
    return json.dumps({"nftables": list(rows)})


def exact_doc(boundary="stack0"):
    table = {
        "table": {
            "family": "inet",
            "name": PROTECTIVE_NFT_TABLE,
            "handle": 1,
            "comment": PROTECTIVE_NFT_OWNER_COMMENT,
        }
    }
    chains = []
    for index, (name, hook) in enumerate(
        (
            ("protect_input", "input"),
            ("protect_output", "output"),
            ("protect_forward", "forward"),
        ),
        2,
    ):
        chains.append(
            {
                "chain": {
                    "family": "inet",
                    "table": PROTECTIVE_NFT_TABLE,
                    "name": name,
                    "handle": index,
                    "type": "filter",
                    "hook": hook,
                    "prio": -500,
                    "policy": "accept",
                }
            }
        )

    def match(key, value):
        return {
            "match": {
                "op": "==",
                "left": {"meta": {"key": key}},
                "right": value,
            }
        }

    rules = (
        {
            "rule": {
                "family": "inet",
                "table": PROTECTIVE_NFT_TABLE,
                "chain": "protect_input",
                "handle": 5,
                "expr": [
                    match("iifname", boundary),
                    match("nfproto", "ipv4"),
                    {"drop": None},
                ],
                "comment": "vpn-gate:ng3:protective-input-v1",
            }
        },
        {
            "rule": {
                "family": "inet",
                "table": PROTECTIVE_NFT_TABLE,
                "chain": "protect_output",
                "handle": 6,
                "expr": [
                    match("oifname", boundary),
                    match("nfproto", "ipv4"),
                    {"drop": None},
                ],
                "comment": "vpn-gate:ng3:protective-output-v1",
            }
        },
        {
            "rule": {
                "family": "inet",
                "table": PROTECTIVE_NFT_TABLE,
                "chain": "protect_forward",
                "handle": 7,
                "expr": [
                    match("nfproto", "ipv4"),
                    {"drop": None},
                ],
                "comment": "vpn-gate:ng3:protective-forward-v1",
            }
        },
    )
    return nft_doc({"metainfo": {}}, table, *chains, *rules)


class ProtectivePayloadGateTests(unittest.TestCase):
    def test_enabled_desired_requires_boundary(self):
        with self.assertRaisesRegex(ValueError, "boundary_interface"):
            ProtectivePayloadGateDesired(
                ProtectivePayloadGateState.ENABLED
            )

    def test_absent_to_enabled_mutates_and_requires_final_exact(self):
        driver = FakeDriver(
            (
                obs(ProtectivePayloadGateObservationStatus.ABSENT),
                obs(ProtectivePayloadGateObservationStatus.EXACT),
            )
        )
        result = converge_protective_payload_gate_once(
            driver,
            desired_enabled(),
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(len(driver.apply_calls), 1)

    def test_conflict_never_mutates(self):
        driver = FakeDriver(
            (
                obs(
                    ProtectivePayloadGateObservationStatus.CONFLICT,
                    "foreign table",
                ),
            )
        )
        result = converge_protective_payload_gate_once(
            driver,
            desired_enabled(),
        )
        self.assertEqual(
            result.status,
            ProtectivePayloadGateEnforcementStatus.CONFLICT,
        )
        self.assertEqual(driver.apply_calls, [])

    def test_noop_still_requires_fresh_final_observation(self):
        driver = FakeDriver(
            (
                obs(ProtectivePayloadGateObservationStatus.EXACT),
                obs(ProtectivePayloadGateObservationStatus.OWNED_DRIFT),
            )
        )
        result = converge_protective_payload_gate_once(
            driver,
            desired_enabled(),
        )
        self.assertEqual(
            result.status,
            ProtectivePayloadGateEnforcementStatus.POSTCONDITION_FAILED,
        )
        self.assertFalse(result.confirmed)

    def test_owned_drift_is_repairable(self):
        driver = FakeDriver(
            (
                obs(ProtectivePayloadGateObservationStatus.OWNED_DRIFT),
                obs(ProtectivePayloadGateObservationStatus.EXACT),
            )
        )
        result = converge_protective_payload_gate_once(
            driver,
            desired_enabled(),
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(len(driver.apply_calls), 1)

    def test_parser_distinguishes_absent_exact_drift_and_conflict(self):
        desired = desired_enabled()
        absent = parse_protective_payload_gate_ruleset(
            nft_doc({"metainfo": {}}),
            desired,
        )
        exact = parse_protective_payload_gate_ruleset(
            exact_doc(),
            desired,
        )
        drift_doc = json.loads(exact_doc())
        drift_doc["nftables"] = drift_doc["nftables"][:-1]
        drift = parse_protective_payload_gate_ruleset(
            json.dumps(drift_doc),
            desired,
        )
        foreign_doc = json.loads(exact_doc())
        foreign_doc["nftables"][1]["table"]["comment"] = "foreign"
        conflict = parse_protective_payload_gate_ruleset(
            json.dumps(foreign_doc),
            desired,
        )
        self.assertEqual(
            absent.status,
            ProtectivePayloadGateObservationStatus.ABSENT,
        )
        self.assertEqual(
            exact.status,
            ProtectivePayloadGateObservationStatus.EXACT,
        )
        self.assertEqual(
            drift.status,
            ProtectivePayloadGateObservationStatus.OWNED_DRIFT,
        )
        self.assertEqual(
            conflict.status,
            ProtectivePayloadGateObservationStatus.CONFLICT,
        )

    def test_linux_driver_uses_one_owned_transaction_for_repair(self):
        runner = FakeRunner((exact_doc(),))
        driver = LinuxProtectivePayloadGateDriver(runner, "managed")
        initial = obs(ProtectivePayloadGateObservationStatus.OWNED_DRIFT)
        driver.apply_protective_payload_gate(desired_enabled(), initial)
        self.assertEqual(
            runner.commands[-1],
            (
                "ip",
                "netns",
                "exec",
                "managed",
                "nft",
                "-f",
                "-",
            ),
        )
        self.assertIn(
            "delete table inet vpn_gate_protective",
            runner.scripts[0],
        )
        self.assertIn("table inet vpn_gate_protective", runner.scripts[0])

    def test_disabled_observation_treats_owned_table_as_removable_drift(self):
        disabled = ProtectivePayloadGateDesired(
            ProtectivePayloadGateState.DISABLED
        )
        value = parse_protective_payload_gate_ruleset(
            exact_doc(),
            disabled,
        )
        self.assertEqual(
            value.status,
            ProtectivePayloadGateObservationStatus.OWNED_DRIFT,
        )


if __name__ == "__main__":
    unittest.main()
