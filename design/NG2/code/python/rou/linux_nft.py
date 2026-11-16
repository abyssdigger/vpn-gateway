from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json

from .interface_identity import InterfaceIdentity
from .network_rules import (
    EndpointKind,
    FlowInitiationAllowSpec,
    NetworkEndpoint,
    PortRange,
    PredicateKind,
    TrafficAllowSpec,
    TrafficPredicate,
    SourceNatTarget,
    TrafficProtocol,
    TrafficSelector,
)
from .network_rules_composition import (
    ComposedNetworkRules,
    OwnedNetworkRules,
    OwnerToken,
)


FILTER_TABLE = "vpng2_filter"
NAT_TABLE = "vpng2_nat"
MAX_DNF_CLAUSES = 4096


class LinuxNftError(ValueError):
    pass


class InterfaceRefKind(str, Enum):
    IIF = "iif"
    OIF = "oif"


@dataclass(frozen=True, order=True)
class NftInterfaceRef:
    kind: InterfaceRefKind
    ifindex: int

    def __post_init__(self) -> None:
        if type(self.ifindex) is not int or self.ifindex <= 0:
            raise LinuxNftError("nft interface reference requires positive ifindex")


@dataclass(frozen=True, order=True)
class NftRuleMarker:
    comment: str
    owner: OwnerToken
    policy: str
    interface_ref: NftInterfaceRef


@dataclass(frozen=True)
class NftFilterDesired:
    family: str
    table: str
    definition: str
    canonical: str
    markers: tuple[NftRuleMarker, ...]
    interface_identities: tuple[InterfaceIdentity, ...]


@dataclass(frozen=True)
class NftNatDesired:
    family: str
    table: str
    definition: str
    canonical: str
    markers: tuple[NftRuleMarker, ...]
    interface_identities: tuple[InterfaceIdentity, ...]


@dataclass(frozen=True)
class _Atom:
    positive: str
    negative: str


@dataclass(frozen=True)
class _Literal:
    atom: _Atom
    negated: bool = False

    @property
    def text(self) -> str:
        return self.atom.negative if self.negated else self.atom.positive


Clause = tuple[_Literal, ...]
Dnf = tuple[Clause, ...]


@dataclass(frozen=True)
class _EndpointMatch:
    terms: tuple[str, ...]
    interface_ref: NftInterfaceRef


def _register_identity(
    identity: InterfaceIdentity,
    *,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> None:
    previous_name = by_name.get(identity.ifname)
    if (
        previous_name is not None
        and previous_name.ifindex != identity.ifindex
    ):
        raise LinuxNftError(
            "multiple interface generations with the same name cannot "
            "coexist in one nft desired state: "
            f"{previous_name!r} vs {identity!r}"
        )

    previous_index = by_index.get(identity.ifindex)
    if (
        previous_index is not None
        and previous_index.ifname != identity.ifname
    ):
        raise LinuxNftError(
            "one ifindex cannot identify multiple interface names: "
            f"{previous_index!r} vs {identity!r}"
        )

    by_name[identity.ifname] = identity
    by_index[identity.ifindex] = identity


def _interface_identities(
    composed: ComposedNetworkRules,
    *,
    include_nat: bool,
) -> tuple[InterfaceIdentity, ...]:
    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}

    def visit(endpoint: NetworkEndpoint) -> None:
        if endpoint.kind is EndpointKind.INTERFACE:
            assert endpoint.interface is not None
            _register_identity(
                endpoint.interface,
                by_name=by_name,
                by_index=by_index,
            )

    for owned in composed.owners:
        for rule in owned.rules.traffic_allows:
            visit(rule.source)
            visit(rule.destination)
        for rule in owned.rules.flow_initiation_allows:
            visit(rule.source)
            visit(rule.destination)
        if include_nat:
            for rule in owned.rules.source_nat:
                visit(rule.source)
                visit(rule.egress)

    return tuple(
        sorted(
            by_index.values(),
            key=lambda item: (item.ifindex, item.ifname),
        )
    )


def normalize_nft_text(
    text: str,
    interface_identities: tuple[InterfaceIdentity, ...],
) -> str:
    """Normalize nft list output while preserving generation semantics."""

    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        line = line.replace(
            "ct state established,related",
            "ct state 0x2,0x4",
        )
        line = line.replace(
            "ct state related,established",
            "ct state 0x2,0x4",
        )
        line = line.replace("ct state invalid", "ct state 0x1")
        line = line.replace("ct state new", "ct state 0x8")

        for identity in interface_identities:
            line = line.replace(
                f'iif "{identity.ifname}"',
                f"iif {identity.ifindex}",
            )
            line = line.replace(
                f'oif "{identity.ifname}"',
                f"oif {identity.ifindex}",
            )

        lines.append(line)

    return "\n".join(lines)


def parse_nft_rule_comments(text: str) -> tuple[str, ...]:
    try:
        root = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LinuxNftError(
            f"invalid nft JSON output: {exc}"
        ) from None

    items = root.get("nftables")
    if not isinstance(items, list):
        raise LinuxNftError("nft JSON root lacks nftables array")

    comments: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rule = item.get("rule")
        if not isinstance(rule, dict):
            continue
        comment = rule.get("comment")
        if comment is None:
            continue
        if not isinstance(comment, str):
            raise LinuxNftError("nft rule comment is not a string")
        comments.append(comment)

    return tuple(sorted(comments))


@dataclass(frozen=True, order=True)
class NftTableIdentity:
    family: str
    name: str

    def __post_init__(self) -> None:
        if not self.family or not self.name:
            raise LinuxNftError("nft table identity must be non-empty")


def parse_nft_tables(text: str) -> tuple[NftTableIdentity, ...]:
    try:
        root = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LinuxNftError(
            f"invalid nft table-list JSON: {exc}"
        ) from None

    items = root.get("nftables")
    if not isinstance(items, list):
        raise LinuxNftError("nft table-list JSON lacks nftables array")

    out: list[NftTableIdentity] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        table = item.get("table")
        if not isinstance(table, dict):
            continue
        family = table.get("family")
        name = table.get("name")
        if not isinstance(family, str) or not isinstance(name, str):
            raise LinuxNftError("invalid nft table identity in JSON")
        out.append(NftTableIdentity(family, name))

    if len(set(out)) != len(out):
        raise LinuxNftError("duplicate nft table identity in JSON")
    return tuple(sorted(out))


@dataclass(frozen=True)
class NftTableObservation:
    canonical: str
    comments: tuple[str, ...]


@dataclass(frozen=True)
class NftTableVerification:
    ok: bool
    errors: tuple[str, ...]


def verify_nft_table(
    desired: NftFilterDesired | NftNatDesired,
    observed: NftTableObservation | None,
) -> NftTableVerification:
    if observed is None:
        return NftTableVerification(
            False,
            (f"nft table {desired.family} {desired.table} is absent",),
        )

    errors: list[str] = []
    if observed.canonical != desired.canonical:
        errors.append(
            f"nft table {desired.table} canonical policy differs"
        )

    expected_comments = tuple(
        sorted(marker.comment for marker in desired.markers)
    )
    if observed.comments != expected_comments:
        errors.append(
            f"nft table {desired.table} rule-marker multiset differs"
        )

    return NftTableVerification(not errors, tuple(errors))


def _quote_token(value: str) -> str:
    if not value:
        raise LinuxNftError("nft token must be non-empty")
    if any(
        ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"
        for ch in value
    ):
        raise LinuxNftError(f"unsupported nft token {value!r}")
    return f'"{value}"'


def _ports_text(ranges: tuple[PortRange, ...]) -> str:
    parts = [
        str(item.start)
        if item.start == item.end
        else f"{item.start}-{item.end}"
        for item in ranges
    ]
    if len(parts) == 1:
        return parts[0]
    return "{ " + ", ".join(parts) + " }"


def _selector_atoms(selector: TrafficSelector) -> tuple[_Atom, ...]:
    atoms: list[_Atom] = []

    if selector.source is not None:
        value = selector.source.with_prefixlen
        atoms.append(
            _Atom(
                f"ip saddr {value}",
                f"ip saddr != {value}",
            )
        )

    if selector.destination is not None:
        value = selector.destination.with_prefixlen
        atoms.append(
            _Atom(
                f"ip daddr {value}",
                f"ip daddr != {value}",
            )
        )

    if selector.protocol is not None:
        protocol = selector.protocol.value
        atoms.append(
            _Atom(
                f"ip protocol {protocol}",
                f"ip protocol != {protocol}",
            )
        )

    if selector.source_ports:
        assert selector.protocol in {
            TrafficProtocol.TCP,
            TrafficProtocol.UDP,
        }
        protocol = selector.protocol.value
        ports = _ports_text(selector.source_ports)
        atoms.append(
            _Atom(
                f"{protocol} sport {ports}",
                f"{protocol} sport != {ports}",
            )
        )

    if selector.destination_ports:
        assert selector.protocol in {
            TrafficProtocol.TCP,
            TrafficProtocol.UDP,
        }
        protocol = selector.protocol.value
        ports = _ports_text(selector.destination_ports)
        atoms.append(
            _Atom(
                f"{protocol} dport {ports}",
                f"{protocol} dport != {ports}",
            )
        )

    if selector.icmp_types:
        values = tuple(sorted(item.value for item in selector.icmp_types))
        rendered = (
            str(values[0])
            if len(values) == 1
            else "{ " + ", ".join(str(item) for item in values) + " }"
        )
        atoms.append(
            _Atom(
                f"icmp type {rendered}",
                f"icmp type != {rendered}",
            )
        )

    return tuple(atoms)


def _normalize_clause(items: tuple[_Literal, ...]) -> Clause | None:
    by_atom: dict[_Atom, bool] = {}
    for item in items:
        previous = by_atom.get(item.atom)
        if previous is not None and previous != item.negated:
            return None
        by_atom[item.atom] = item.negated

    return tuple(
        sorted(
            (_Literal(atom, negated) for atom, negated in by_atom.items()),
            key=lambda item: item.text,
        )
    )


def _dedupe_dnf(clauses: list[Clause]) -> Dnf:
    unique: dict[Clause, None] = {}
    for clause in clauses:
        normalized = _normalize_clause(clause)
        if normalized is None:
            continue
        unique[normalized] = None
        if len(unique) > MAX_DNF_CLAUSES:
            raise LinuxNftError(
                f"predicate expansion exceeds {MAX_DNF_CLAUSES} DNF clauses"
            )
    return tuple(unique)


def _and_dnf(left: Dnf, right: Dnf) -> Dnf:
    if not left or not right:
        return ()

    out: list[Clause] = []
    for left_clause in left:
        for right_clause in right:
            out.append(left_clause + right_clause)
            if len(out) > MAX_DNF_CLAUSES * 2:
                # Normalize/deduplicate before an avoidable combinatorial blow-up.
                out = list(_dedupe_dnf(out))
    return _dedupe_dnf(out)


def _predicate_dnf(
    predicate: TrafficPredicate,
    *,
    inverted: bool = False,
) -> Dnf:
    kind = predicate.kind

    if kind is PredicateKind.ALWAYS:
        return () if inverted else ((),)

    if kind is PredicateKind.NEVER:
        return ((),) if inverted else ()

    if kind is PredicateKind.MATCH:
        assert predicate.selector is not None
        atoms = _selector_atoms(predicate.selector)
        if not inverted:
            return (tuple(_Literal(atom) for atom in atoms),)
        return tuple((_Literal(atom, True),) for atom in atoms)

    if kind is PredicateKind.NOT:
        return _predicate_dnf(
            predicate.children[0],
            inverted=not inverted,
        )

    children = predicate.children
    if kind is PredicateKind.ALL:
        effective_any = inverted
    elif kind is PredicateKind.ANY:
        effective_any = not inverted
    else:
        raise LinuxNftError(f"unsupported predicate kind {kind!r}")

    if effective_any:
        out: list[Clause] = []
        for child in children:
            out.extend(
                _predicate_dnf(child, inverted=inverted)
            )
            if len(out) > MAX_DNF_CLAUSES * 2:
                out = list(_dedupe_dnf(out))
        return _dedupe_dnf(out)

    result: Dnf = ((),)
    for child in children:
        result = _and_dnf(
            result,
            _predicate_dnf(child, inverted=inverted),
        )
        if not result:
            break
    return result


def _endpoint_match(
    source: NetworkEndpoint,
    destination: NetworkEndpoint,
    *,
    local_interface: str,
) -> _EndpointMatch:
    local = _quote_token(local_interface)

    if (
        source.kind is EndpointKind.LOCAL_NETWORK
        and destination.kind is EndpointKind.INTERFACE
    ):
        assert destination.interface is not None
        ref = NftInterfaceRef(
            InterfaceRefKind.OIF,
            destination.interface.ifindex,
        )
        return _EndpointMatch(
            (
                f"iifname {local}",
                f"oif {ref.ifindex}",
            ),
            ref,
        )

    if (
        source.kind is EndpointKind.INTERFACE
        and destination.kind is EndpointKind.LOCAL_NETWORK
    ):
        assert source.interface is not None
        ref = NftInterfaceRef(
            InterfaceRefKind.IIF,
            source.interface.ifindex,
        )
        return _EndpointMatch(
            (
                f"iif {ref.ifindex}",
                f"oifname {local}",
            ),
            ref,
        )

    raise LinuxNftError(
        "current nft backend supports only LOCAL_NETWORK <-> INTERFACE "
        "traffic endpoint pairs"
    )


def _comment(
    owner: OwnerToken,
    policy: str,
    rule_id: str,
    clause_index: int,
    ref: NftInterfaceRef,
) -> str:
    return (
        f"vpng2:o{owner.value}:{policy}:{rule_id}:"
        f"c{clause_index}:{ref.kind.value}:{ref.ifindex}"
    )


def _rule_lines(
    *,
    owner: OwnerToken,
    policy: str,
    rule_id: str,
    source: NetworkEndpoint,
    destination: NetworkEndpoint,
    predicate: TrafficPredicate,
    local_interface: str,
) -> tuple[tuple[str, NftRuleMarker], ...]:
    endpoint = _endpoint_match(
        source,
        destination,
        local_interface=local_interface,
    )
    dnf = _predicate_dnf(predicate)

    out: list[tuple[str, NftRuleMarker]] = []
    for index, clause in enumerate(dnf):
        comment = _comment(
            owner,
            policy,
            rule_id,
            index,
            endpoint.interface_ref,
        )
        terms = list(endpoint.terms)
        terms.extend(item.text for item in clause)
        terms.extend(
            [
                "return",
                f'comment "{comment}"',
            ]
        )
        out.append(
            (
                " ".join(terms),
                NftRuleMarker(
                    comment,
                    owner,
                    policy,
                    endpoint.interface_ref,
                ),
            )
        )
    return tuple(out)


def _same_endpoints(
    traffic: TrafficAllowSpec,
    flow: FlowInitiationAllowSpec,
) -> bool:
    return (
        traffic.source == flow.source
        and traffic.destination == flow.destination
    )


def _owner_new_flow_rules(
    owned: OwnedNetworkRules,
    *,
    local_interface: str,
) -> tuple[tuple[str, NftRuleMarker], ...]:
    out: list[tuple[str, NftRuleMarker]] = []

    for traffic_index, traffic in enumerate(owned.rules.traffic_allows):
        for flow_index, flow in enumerate(
            owned.rules.flow_initiation_allows
        ):
            if not _same_endpoints(traffic, flow):
                continue

            predicate = TrafficPredicate.all_of(
                traffic.predicate,
                flow.predicate,
            )
            out.extend(
                _rule_lines(
                    owner=owned.owner,
                    policy="new",
                    rule_id=f"t{traffic_index}f{flow_index}",
                    source=traffic.source,
                    destination=traffic.destination,
                    predicate=predicate,
                    local_interface=local_interface,
                )
            )

    return tuple(out)


def compile_nft_filter_desired(
    composed: ComposedNetworkRules,
    *,
    local_interface: str,
) -> NftFilterDesired:
    """Compile owner-composed allow policy into one stateful nft filter table."""

    _quote_token(local_interface)

    traffic_lines: list[str] = []
    new_lines: list[str] = []
    markers: list[NftRuleMarker] = []

    for owned in composed.owners:
        for index, rule in enumerate(owned.rules.traffic_allows):
            for line, marker in _rule_lines(
                owner=owned.owner,
                policy="traffic",
                rule_id=str(index),
                source=rule.source,
                destination=rule.destination,
                predicate=rule.predicate,
                local_interface=local_interface,
            ):
                traffic_lines.append(line)
                markers.append(marker)

        for line, marker in _owner_new_flow_rules(
            owned,
            local_interface=local_interface,
        ):
            new_lines.append(line)
            markers.append(marker)

    lines = [
        f"table ip {FILTER_TABLE} {{",
        "chain traffic_bytes {",
        *traffic_lines,
        "drop",
        "}",
        "chain new_flows {",
        *new_lines,
        "drop",
        "}",
        "chain forward {",
        "type filter hook forward priority 0; policy drop;",
        "ct state invalid drop",
        "ct state established,related jump traffic_bytes",
        "ct state established,related accept",
        "ct state new jump new_flows",
        "ct state new accept",
        "}",
        "}",
        "",
    ]

    definition = "\n".join(lines)
    identities = _interface_identities(
        composed,
        include_nat=False,
    )
    return NftFilterDesired(
        family="ip",
        table=FILTER_TABLE,
        definition=definition,
        canonical=normalize_nft_text(definition, identities),
        markers=tuple(markers),
        interface_identities=identities,
    )


def compile_nft_nat_desired(
    composed: ComposedNetworkRules,
    *,
    local_interface: str,
) -> NftNatDesired:
    """Compile semantic source NAT into one owner-provenance nft table."""

    local = _quote_token(local_interface)
    lines = [
        f"table ip {NAT_TABLE} {{",
        "chain postrouting {",
        "type nat hook postrouting priority 100; policy accept;",
    ]
    markers: list[NftRuleMarker] = []

    for owned in composed.owners:
        for rule_index, rule in enumerate(owned.rules.source_nat):
            if rule.source.kind is not EndpointKind.LOCAL_NETWORK:
                raise LinuxNftError(
                    "current nft NAT backend supports source NAT only from "
                    "LOCAL_NETWORK"
                )
            if rule.egress.kind is not EndpointKind.INTERFACE:
                raise LinuxNftError(
                    "source NAT requires concrete interface egress"
                )
            if rule.target is not SourceNatTarget.EGRESS_ADDRESS:
                raise LinuxNftError(
                    f"unsupported source NAT target {rule.target!r}"
                )

            assert rule.egress.interface is not None
            ref = NftInterfaceRef(
                InterfaceRefKind.OIF,
                rule.egress.interface.ifindex,
            )

            for clause_index, clause in enumerate(
                _predicate_dnf(rule.predicate)
            ):
                comment = _comment(
                    owned.owner,
                    "nat",
                    str(rule_index),
                    clause_index,
                    ref,
                )
                terms = [
                    f"iifname {local}",
                    f"oif {ref.ifindex}",
                    *(item.text for item in clause),
                    "masquerade",
                    f'comment "{comment}"',
                ]
                lines.append(" ".join(terms))
                markers.append(
                    NftRuleMarker(
                        comment,
                        owned.owner,
                        "nat",
                        ref,
                    )
                )

    lines.extend(["}", "}", ""])
    definition = "\n".join(lines)
    identities = _interface_identities(
        composed,
        include_nat=True,
    )
    return NftNatDesired(
        family="ip",
        table=NAT_TABLE,
        definition=definition,
        canonical=normalize_nft_text(definition, identities),
        markers=tuple(markers),
        interface_identities=identities,
    )
