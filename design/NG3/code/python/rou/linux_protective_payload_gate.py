"""Linux realization of the dedicated protective payload gate.

Architecture: C.010 ProtectivePayloadGate.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from .linux_nft_scaffold import NftScriptRunner
from .protective_payload_gate import (
    ProtectivePayloadGateDesired,
    ProtectivePayloadGateObservation,
    ProtectivePayloadGateObservationStatus,
    ProtectivePayloadGateState,
)


PROTECTIVE_NFT_FAMILY = "inet"
PROTECTIVE_NFT_TABLE = "vpn_gate_protective"
PROTECTIVE_NFT_OWNER_COMMENT = "vpn-gate:ng3:protective-v1"
_INPUT_RULE_COMMENT = "vpn-gate:ng3:protective-input-v1"
_OUTPUT_RULE_COMMENT = "vpn-gate:ng3:protective-output-v1"
_FORWARD_RULE_COMMENT = "vpn-gate:ng3:protective-forward-v1"


class LinuxProtectivePayloadGateError(ValueError):
    pass


@dataclass(slots=True)
class LinuxProtectivePayloadGateDriver:
    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def observe_protective_payload_gate(
        self,
        desired: ProtectivePayloadGateDesired,
    ) -> ProtectivePayloadGateObservation:
        stdout = self.runner.run(self._cmd("nft", "-j", "list", "ruleset"))
        return parse_protective_payload_gate_ruleset(stdout, desired)

    def apply_protective_payload_gate(
        self,
        desired: ProtectivePayloadGateDesired,
        initial: ProtectivePayloadGateObservation,
    ) -> None:
        if not isinstance(desired, ProtectivePayloadGateDesired):
            raise ValueError("desired must be ProtectivePayloadGateDesired")
        if not isinstance(initial, ProtectivePayloadGateObservation):
            raise ValueError("initial must be ProtectivePayloadGateObservation")
        if initial.status is ProtectivePayloadGateObservationStatus.CONFLICT:
            raise LinuxProtectivePayloadGateError(
                "refusing to mutate conflicting protective table"
            )

        if desired.state is ProtectivePayloadGateState.DISABLED:
            if not initial.owned:
                raise LinuxProtectivePayloadGateError(
                    "disable mutation requires confirmed owned table"
                )
            script = (
                f"delete table {PROTECTIVE_NFT_FAMILY} "
                f"{PROTECTIVE_NFT_TABLE}\n"
            )
        else:
            prefix = ""
            if initial.owned:
                prefix = (
                    f"delete table {PROTECTIVE_NFT_FAMILY} "
                    f"{PROTECTIVE_NFT_TABLE}\n"
                )
            elif (
                initial.status
                is not ProtectivePayloadGateObservationStatus.ABSENT
            ):
                raise LinuxProtectivePayloadGateError(
                    "enable mutation requires absent or owned table"
                )
            script = prefix + _enabled_script(desired.boundary_interface)

        self.runner.run_script(self._cmd("nft", "-f", "-"), script)

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)


def parse_protective_payload_gate_ruleset(
    text: str,
    desired: ProtectivePayloadGateDesired,
) -> ProtectivePayloadGateObservation:
    if not isinstance(desired, ProtectivePayloadGateDesired):
        raise ValueError("desired must be ProtectivePayloadGateDesired")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LinuxProtectivePayloadGateError(
            f"invalid nft ruleset JSON: {exc}"
        ) from None
    if not isinstance(document, dict):
        raise LinuxProtectivePayloadGateError(
            "nft ruleset JSON root must be an object"
        )
    rows = document.get("nftables")
    if not isinstance(rows, list):
        raise LinuxProtectivePayloadGateError(
            "nft ruleset JSON must contain nftables array"
        )

    tables: list[dict] = []
    objects: list[tuple[str, dict]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or len(row) != 1:
            raise LinuxProtectivePayloadGateError(
                f"nftables row {index} must be a single-key object"
            )
        kind, payload = next(iter(row.items()))
        if kind == "metainfo":
            continue
        if not isinstance(payload, dict):
            raise LinuxProtectivePayloadGateError(
                f"nft {kind!r} payload must be an object"
            )
        if (
            kind == "table"
            and payload.get("family") == PROTECTIVE_NFT_FAMILY
            and payload.get("name") == PROTECTIVE_NFT_TABLE
        ):
            tables.append(payload)
        elif (
            payload.get("family") == PROTECTIVE_NFT_FAMILY
            and payload.get("table") == PROTECTIVE_NFT_TABLE
        ):
            objects.append((kind, payload))

    if len(tables) > 1:
        return _conflict("duplicate protective table declarations")
    if not tables:
        if objects:
            return _conflict(
                "protective objects exist without protective table declaration"
            )
        return ProtectivePayloadGateObservation(
            ProtectivePayloadGateObservationStatus.ABSENT
        )

    table = _without_handle(tables[0])
    expected_table = {
        "family": PROTECTIVE_NFT_FAMILY,
        "name": PROTECTIVE_NFT_TABLE,
        "comment": PROTECTIVE_NFT_OWNER_COMMENT,
    }
    if table.get("comment") != PROTECTIVE_NFT_OWNER_COMMENT:
        return _conflict("protective table owner marker is absent or different")
    if table != expected_table:
        return ProtectivePayloadGateObservation(
            ProtectivePayloadGateObservationStatus.OWNED_DRIFT
        )

    if desired.state is ProtectivePayloadGateState.DISABLED:
        return ProtectivePayloadGateObservation(
            ProtectivePayloadGateObservationStatus.OWNED_DRIFT
        )

    boundary = desired.boundary_interface
    assert boundary is not None

    chains: dict[str, dict] = {}
    rules: dict[str, dict] = {}
    for kind, payload in objects:
        normalized = _without_handle(payload)
        if kind == "chain":
            name = normalized.get("name")
            if not isinstance(name, str) or name in chains:
                return ProtectivePayloadGateObservation(
                    ProtectivePayloadGateObservationStatus.OWNED_DRIFT
                )
            chains[name] = normalized
        elif kind == "rule":
            comment = normalized.get("comment")
            if not isinstance(comment, str) or comment in rules:
                return ProtectivePayloadGateObservation(
                    ProtectivePayloadGateObservationStatus.OWNED_DRIFT
                )
            rules[comment] = normalized
        else:
            return ProtectivePayloadGateObservation(
                ProtectivePayloadGateObservationStatus.OWNED_DRIFT
            )

    expected_chains = {
        name: {
            "family": PROTECTIVE_NFT_FAMILY,
            "table": PROTECTIVE_NFT_TABLE,
            "name": name,
            "type": "filter",
            "hook": hook,
            "prio": -500,
            "policy": "accept",
        }
        for name, hook in (
            ("protect_input", "input"),
            ("protect_output", "output"),
            ("protect_forward", "forward"),
        )
    }
    if chains != expected_chains:
        return ProtectivePayloadGateObservation(
            ProtectivePayloadGateObservationStatus.OWNED_DRIFT
        )

    expected_rules = {
        _INPUT_RULE_COMMENT: _rule_payload(
            "protect_input",
            _INPUT_RULE_COMMENT,
            _meta_match("iifname", boundary),
            _meta_match("nfproto", "ipv4"),
        ),
        _OUTPUT_RULE_COMMENT: _rule_payload(
            "protect_output",
            _OUTPUT_RULE_COMMENT,
            _meta_match("oifname", boundary),
            _meta_match("nfproto", "ipv4"),
        ),
        _FORWARD_RULE_COMMENT: _rule_payload(
            "protect_forward",
            _FORWARD_RULE_COMMENT,
            _meta_match("nfproto", "ipv4"),
        ),
    }
    if rules != expected_rules:
        return ProtectivePayloadGateObservation(
            ProtectivePayloadGateObservationStatus.OWNED_DRIFT
        )

    return ProtectivePayloadGateObservation(
        ProtectivePayloadGateObservationStatus.EXACT
    )


def _without_handle(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "handle"}


def _conflict(reason: str) -> ProtectivePayloadGateObservation:
    return ProtectivePayloadGateObservation(
        ProtectivePayloadGateObservationStatus.CONFLICT,
        reason,
    )


def _meta_match(key: str, value: str) -> dict:
    return {
        "match": {
            "op": "==",
            "left": {"meta": {"key": key}},
            "right": value,
        }
    }


def _rule_payload(
    chain: str,
    comment: str,
    *matches: dict,
) -> dict:
    return {
        "family": PROTECTIVE_NFT_FAMILY,
        "table": PROTECTIVE_NFT_TABLE,
        "chain": chain,
        "expr": [*matches, {"drop": None}],
        "comment": comment,
    }


def _enabled_script(boundary_interface: str | None) -> str:
    if not isinstance(boundary_interface, str) or not boundary_interface:
        raise ValueError("boundary_interface must be non-empty text")
    quoted = json.dumps(boundary_interface)
    return f"""table inet {PROTECTIVE_NFT_TABLE} {{
    comment "{PROTECTIVE_NFT_OWNER_COMMENT}"
    chain protect_input {{
        type filter hook input priority -500; policy accept;
        meta iifname {quoted} meta nfproto ipv4 drop comment "{_INPUT_RULE_COMMENT}"
    }}
    chain protect_output {{
        type filter hook output priority -500; policy accept;
        meta oifname {quoted} meta nfproto ipv4 drop comment "{_OUTPUT_RULE_COMMENT}"
    }}
    chain protect_forward {{
        type filter hook forward priority -500; policy accept;
        meta nfproto ipv4 drop comment "{_FORWARD_RULE_COMMENT}"
    }}
}}
"""
