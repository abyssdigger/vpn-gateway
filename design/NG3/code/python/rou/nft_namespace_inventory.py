from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Protocol, Sequence


NG3_NFT_FAMILY = "ip"
NG3_NFT_TABLE = "vpn_gate"
NG3_NFT_OWNER_COMMENT = "vpn-gate:ng3:owner-v1"


class NftNamespaceInventoryError(ValueError):
    pass


class NftNamespaceStatus(str, Enum):
    ABSENT = "absent"
    OWNED = "owned"
    CONFLICT = "conflict"


@dataclass(frozen=True, order=True, slots=True)
class NftNamespaceObject:
    kind: str
    canonical_json: str
    source_order: int = field(default=0, compare=False)


@dataclass(frozen=True, slots=True)
class NftNamespaceObservation:
    status: NftNamespaceStatus
    objects: tuple[NftNamespaceObject, ...] = ()
    observed_comment: str | None = None
    conflict_reason: str | None = None

    @property
    def marker_confirmed(self) -> bool:
        return self.status is NftNamespaceStatus.OWNED


class NftRulesetCommandRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one command or raise; return stdout text."""


@dataclass(slots=True)
class LinuxNftNamespaceBackend:
    runner: NftRulesetCommandRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def observe_nft_namespace(self) -> NftNamespaceObservation:
        stdout = self.runner.run(
            (
                "ip",
                "netns",
                "exec",
                self.namespace,
                "nft",
                "-j",
                "list",
                "ruleset",
            )
        )
        return parse_nft_namespace_ruleset(stdout)


def parse_nft_namespace_ruleset(
    text: str,
) -> NftNamespaceObservation:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NftNamespaceInventoryError(
            f"invalid nft ruleset JSON: {exc}"
        ) from None

    if not isinstance(document, dict):
        raise NftNamespaceInventoryError(
            "nft ruleset JSON root must be an object"
        )
    rows = document.get("nftables")
    if not isinstance(rows, list):
        raise NftNamespaceInventoryError(
            "nft ruleset JSON must contain nftables array"
        )

    table_records: list[dict] = []
    objects: list[NftNamespaceObject] = []

    for index, row in enumerate(rows):
        if not isinstance(row, dict) or len(row) != 1:
            raise NftNamespaceInventoryError(
                f"nftables row {index} must be a single-key object"
            )
        kind, payload = next(iter(row.items()))

        if kind == "metainfo":
            if not isinstance(payload, dict):
                raise NftNamespaceInventoryError(
                    "nft metainfo must be an object"
                )
            continue

        if not isinstance(payload, dict):
            raise NftNamespaceInventoryError(
                f"nft {kind!r} payload must be an object"
            )

        if kind == "table":
            if (
                payload.get("family") == NG3_NFT_FAMILY
                and payload.get("name") == NG3_NFT_TABLE
            ):
                table_records.append(payload)
            continue

        if (
            payload.get("family") == NG3_NFT_FAMILY
            and payload.get("table") == NG3_NFT_TABLE
        ):
            objects.append(
                NftNamespaceObject(
                    kind=kind,
                    canonical_json=json.dumps(
                        row,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    source_order=index,
                )
            )

    if len(table_records) > 1:
        raise NftNamespaceInventoryError(
            "ruleset contains duplicate reserved nft table declarations"
        )

    if not table_records:
        if objects:
            raise NftNamespaceInventoryError(
                "reserved nft objects exist without reserved table declaration"
            )
        return NftNamespaceObservation(
            status=NftNamespaceStatus.ABSENT,
        )

    table = table_records[0]
    allowed_table_fields = {
        "family",
        "name",
        "handle",
        "comment",
    }
    extras = sorted(set(table) - allowed_table_fields)
    if extras:
        return NftNamespaceObservation(
            status=NftNamespaceStatus.CONFLICT,
            objects=tuple(sorted(objects)),
            observed_comment=(
                table.get("comment")
                if isinstance(table.get("comment"), str)
                else None
            ),
            conflict_reason=(
                f"reserved nft table has unsupported fields {extras!r}"
            ),
        )

    handle = table.get("handle")
    if handle is not None and (
        type(handle) is not int or handle < 0
    ):
        raise NftNamespaceInventoryError(
            "reserved nft table handle must be a non-negative integer"
        )

    comment = table.get("comment")
    if comment != NG3_NFT_OWNER_COMMENT:
        if comment is not None and not isinstance(comment, str):
            raise NftNamespaceInventoryError(
                "reserved nft table comment must be text when present"
            )
        return NftNamespaceObservation(
            status=NftNamespaceStatus.CONFLICT,
            objects=tuple(sorted(objects)),
            observed_comment=comment,
            conflict_reason="reserved nft table owner marker is absent or different",
        )

    return NftNamespaceObservation(
        status=NftNamespaceStatus.OWNED,
        objects=tuple(sorted(objects)),
        observed_comment=comment,
    )
