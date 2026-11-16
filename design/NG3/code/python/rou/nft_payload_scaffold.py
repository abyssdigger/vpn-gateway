from __future__ import annotations

from dataclasses import dataclass
import json

from .nft_namespace_inventory import (
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
)


STACK_INPUT_CHAIN = "stack_input"
STACK_INPUT_COMMENT = "vpn-gate:ng3:stack-input-v1"
PAYLOAD_FORWARD_CHAIN = "payload_forward"
PAYLOAD_FORWARD_COMMENT = "vpn-gate:ng3:payload-forward-v1"
STACK_OUTPUT_CHAIN = "stack_output"
STACK_OUTPUT_COMMENT = "vpn-gate:ng3:stack-output-v1"
PAYLOAD_POSTROUTING_CHAIN = "payload_postrouting"
PAYLOAD_POSTROUTING_COMMENT = "vpn-gate:ng3:payload-postrouting-v1"


class NftPayloadScaffoldError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class NftBaseChainSpec:
    name: str
    chain_type: str
    hook: str
    priority: int
    policy: str
    comment: str


PAYLOAD_NFT_SCAFFOLD = (
    NftBaseChainSpec(
        name=STACK_INPUT_CHAIN,
        chain_type="filter",
        hook="input",
        priority=0,
        policy="drop",
        comment=STACK_INPUT_COMMENT,
    ),
    NftBaseChainSpec(
        name=PAYLOAD_FORWARD_CHAIN,
        chain_type="filter",
        hook="forward",
        priority=0,
        policy="drop",
        comment=PAYLOAD_FORWARD_COMMENT,
    ),
    NftBaseChainSpec(
        name=STACK_OUTPUT_CHAIN,
        chain_type="filter",
        hook="output",
        priority=0,
        policy="drop",
        comment=STACK_OUTPUT_COMMENT,
    ),
    NftBaseChainSpec(
        name=PAYLOAD_POSTROUTING_CHAIN,
        chain_type="nat",
        hook="postrouting",
        priority=100,
        policy="accept",
        comment=PAYLOAD_POSTROUTING_COMMENT,
    ),
)


@dataclass(frozen=True, slots=True)
class NftPayloadScaffoldConflict:
    chain_name: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class NftPayloadScaffoldComparison:
    namespace_status: NftNamespaceStatus
    confirmed_chains: tuple[NftBaseChainSpec, ...]
    missing_chains: tuple[NftBaseChainSpec, ...]
    conflicts: tuple[NftPayloadScaffoldConflict, ...]
    unclassified_objects: tuple[NftNamespaceObject, ...]

    @property
    def scaffold_confirmed(self) -> bool:
        return (
            self.namespace_status is NftNamespaceStatus.OWNED
            and not self.missing_chains
            and not self.conflicts
        )

    @property
    def full_policy_classified(self) -> bool:
        return self.scaffold_confirmed and not self.unclassified_objects


def compare_payload_nft_scaffold(
    observation: NftNamespaceObservation,
) -> NftPayloadScaffoldComparison:
    if not isinstance(observation, NftNamespaceObservation):
        raise NftPayloadScaffoldError(
            "observation must be NftNamespaceObservation"
        )

    if observation.status is NftNamespaceStatus.ABSENT:
        return NftPayloadScaffoldComparison(
            namespace_status=observation.status,
            confirmed_chains=(),
            missing_chains=PAYLOAD_NFT_SCAFFOLD,
            conflicts=(),
            unclassified_objects=(),
        )

    if observation.status is NftNamespaceStatus.CONFLICT:
        return NftPayloadScaffoldComparison(
            namespace_status=observation.status,
            confirmed_chains=(),
            missing_chains=PAYLOAD_NFT_SCAFFOLD,
            conflicts=(
                NftPayloadScaffoldConflict(
                    chain_name=None,
                    reason=(
                        observation.conflict_reason
                        or "reserved nft table ownership conflict"
                    ),
                ),
            ),
            unclassified_objects=observation.objects,
        )

    expected = {
        spec.name: spec
        for spec in PAYLOAD_NFT_SCAFFOLD
    }
    seen: dict[str, NftBaseChainSpec] = {}
    conflicts: list[NftPayloadScaffoldConflict] = []
    unclassified: list[NftNamespaceObject] = []

    for item in observation.objects:
        if item.kind != "chain":
            unclassified.append(item)
            continue

        payload = _chain_payload(item)
        name = payload.get("name")
        if not isinstance(name, str) or name not in expected:
            unclassified.append(item)
            continue

        if name in seen:
            conflicts.append(
                NftPayloadScaffoldConflict(
                    chain_name=name,
                    reason="duplicate invariant scaffold chain",
                )
            )
            continue

        spec = expected[name]
        mismatch = _chain_mismatch(payload, spec)
        if mismatch is not None:
            conflicts.append(
                NftPayloadScaffoldConflict(
                    chain_name=name,
                    reason=mismatch,
                )
            )
            continue

        seen[name] = spec

    confirmed = tuple(
        spec
        for spec in PAYLOAD_NFT_SCAFFOLD
        if spec.name in seen
    )
    missing = tuple(
        spec
        for spec in PAYLOAD_NFT_SCAFFOLD
        if spec.name not in seen
    )

    return NftPayloadScaffoldComparison(
        namespace_status=observation.status,
        confirmed_chains=confirmed,
        missing_chains=missing,
        conflicts=tuple(conflicts),
        unclassified_objects=tuple(sorted(unclassified)),
    )


def _chain_payload(item: NftNamespaceObject) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except json.JSONDecodeError as exc:
        raise NftPayloadScaffoldError(
            f"invalid canonical chain JSON: {exc}"
        ) from None

    if (
        not isinstance(row, dict)
        or set(row) != {"chain"}
        or not isinstance(row["chain"], dict)
    ):
        raise NftPayloadScaffoldError(
            "canonical chain object has unexpected structure"
        )
    return row["chain"]


def _chain_mismatch(
    payload: dict,
    expected: NftBaseChainSpec,
) -> str | None:
    allowed_fields = {
        "family",
        "table",
        "name",
        "handle",
        "type",
        "hook",
        "prio",
        "policy",
        "comment",
    }
    extras = sorted(set(payload) - allowed_fields)
    if extras:
        return f"scaffold chain has unsupported fields {extras!r}"

    handle = payload.get("handle")
    if handle is not None and (
        type(handle) is not int or handle < 0
    ):
        return "scaffold chain handle is invalid"

    checks = (
        ("family", payload.get("family"), "ip"),
        ("table", payload.get("table"), "vpn_gate"),
        ("name", payload.get("name"), expected.name),
        ("type", payload.get("type"), expected.chain_type),
        ("hook", payload.get("hook"), expected.hook),
        ("prio", payload.get("prio"), expected.priority),
        ("policy", payload.get("policy"), expected.policy),
        ("comment", payload.get("comment"), expected.comment),
    )
    for field, observed, desired in checks:
        if observed != desired:
            return (
                f"scaffold chain field {field!r} mismatch: "
                f"observed={observed!r}, desired={desired!r}"
            )
    return None
