from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network
import re
from typing import Iterable

from .binding import LogicalPathId
from .payload_profile import PayloadProfileRequest
from .route_priority_realization import RoutePriorityMetricSpace


_U32_LIMIT = 0x1_0000_0000
_LINUX_RESERVED_TABLE_IDS = frozenset((0, 253, 254, 255))
_NFT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class NetworkPolicyLayoutError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NumericResourcePool:
    """Ordered half-open integer pool used only by lower platform allocation."""

    first: int
    stop: int

    def __post_init__(self) -> None:
        if (
            type(self.first) is not int
            or type(self.stop) is not int
            or not 0 <= self.first < self.stop <= _U32_LIMIT
        ):
            raise NetworkPolicyLayoutError(
                "numeric resource pool must satisfy 0 <= first < stop <= 2^32"
            )

    @property
    def capacity(self) -> int:
        return self.stop - self.first

    def contains(self, value: int) -> bool:
        return type(value) is int and self.first <= value < self.stop

    def value_at(self, index: int) -> int:
        if type(index) is not int or not 0 <= index < self.capacity:
            raise NetworkPolicyLayoutError("resource-pool index is out of range")
        return self.first + index

    def take(self, count: int) -> tuple[int, ...]:
        if type(count) is not int or count < 0:
            raise NetworkPolicyLayoutError(
                "resource-pool allocation count must be a non-negative integer"
            )
        if count > self.capacity:
            raise NetworkPolicyLayoutError(
                f"resource-pool capacity {self.capacity} is insufficient for {count} allocations"
            )
        return tuple(range(self.first, self.first + count))

    def overlaps(self, other: "NumericResourcePool") -> bool:
        return self.first < other.stop and other.first < self.stop


@dataclass(frozen=True, slots=True)
class RouteMetricPlatformSpace:
    first_preference_metric: int
    terminal_guard_metric: int

    def __post_init__(self) -> None:
        if (
            type(self.first_preference_metric) is not int
            or type(self.terminal_guard_metric) is not int
            or not 0 <= self.first_preference_metric < self.terminal_guard_metric < _U32_LIMIT
        ):
            raise NetworkPolicyLayoutError(
                "route metric platform space must satisfy "
                "0 <= first_preference_metric < terminal_guard_metric < 2^32"
            )

    def allocate(
        self,
        path_count: int,
    ) -> RoutePriorityMetricSpace | None:
        if type(path_count) is not int or path_count < 0:
            raise NetworkPolicyLayoutError(
                "path_count must be a non-negative integer"
            )
        if path_count == 0:
            return None

        scratch_count = 1 if path_count > 1 else 0
        end = self.first_preference_metric + path_count + scratch_count
        if end > self.terminal_guard_metric:
            raise NetworkPolicyLayoutError(
                "route metric space cannot fit preference/scratch metrics below terminal guard"
            )

        preference_slots = tuple(
            range(
                self.first_preference_metric,
                self.first_preference_metric + path_count,
            )
        )
        scratch_metrics = (
            (self.first_preference_metric + path_count,)
            if scratch_count
            else ()
        )
        return RoutePriorityMetricSpace(
            preference_slots=preference_slots,
            scratch_metrics=scratch_metrics,
        )


@dataclass(frozen=True, slots=True)
class NetworkPolicyPlatformSpace:
    payload_tables: NumericResourcePool
    probe_tables: NumericResourcePool
    probe_rule_priorities: NumericResourcePool
    payload_rule_priorities: NumericResourcePool
    ambient_main_rule_priority: int
    path_route_protocol: int
    guard_route_protocol: int
    route_metrics: RouteMetricPlatformSpace
    nft_family: str
    nft_table: str

    def __post_init__(self) -> None:
        if self.payload_tables.overlaps(self.probe_tables):
            raise NetworkPolicyLayoutError(
                "payload and probe table pools must be disjoint"
            )
        for pool_name, pool in (
            ("payload_tables", self.payload_tables),
            ("probe_tables", self.probe_tables),
        ):
            if any(pool.contains(value) for value in _LINUX_RESERVED_TABLE_IDS):
                raise NetworkPolicyLayoutError(
                    f"{pool_name} overlaps Linux reserved table IDs"
                )

        if self.probe_rule_priorities.overlaps(self.payload_rule_priorities):
            raise NetworkPolicyLayoutError(
                "probe and payload RPDB priority pools must be disjoint"
            )
        if (
            self.probe_rule_priorities.stop
            > self.payload_rule_priorities.first
        ):
            raise NetworkPolicyLayoutError(
                "probe RPDB pool must have higher precedence than payload pool"
            )
        if (
            type(self.ambient_main_rule_priority) is not int
            or not 1 <= self.ambient_main_rule_priority < _U32_LIMIT
        ):
            raise NetworkPolicyLayoutError(
                "ambient_main_rule_priority must be an integer in [1, 2^32-1]"
            )
        if self.payload_rule_priorities.stop > self.ambient_main_rule_priority:
            raise NetworkPolicyLayoutError(
                "payload RPDB pool must execute before ambient/main lookup"
            )

        for name, value in (
            ("path_route_protocol", self.path_route_protocol),
            ("guard_route_protocol", self.guard_route_protocol),
        ):
            if type(value) is not int or not 1 <= value <= 255:
                raise NetworkPolicyLayoutError(
                    f"{name} must be an integer in [1, 255]"
                )
        if self.path_route_protocol == self.guard_route_protocol:
            raise NetworkPolicyLayoutError(
                "path and guard route protocol markers must be distinct"
            )

        if self.nft_family not in ("ip", "inet"):
            raise NetworkPolicyLayoutError(
                "nft_family must be 'ip' or 'inet'"
            )
        if (
            not isinstance(self.nft_table, str)
            or _NFT_NAME_RE.fullmatch(self.nft_table) is None
        ):
            raise NetworkPolicyLayoutError(
                "nft_table must be a canonical lowercase nft identifier"
            )


@dataclass(frozen=True, order=True, slots=True)
class ProbePolicyOwner:
    profile_id: str
    path_id: LogicalPathId

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise NetworkPolicyLayoutError(
                "ProbePolicyOwner.profile_id must be non-empty"
            )
        if not isinstance(self.path_id, LogicalPathId):
            raise NetworkPolicyLayoutError(
                "ProbePolicyOwner.path_id must be LogicalPathId"
            )


@dataclass(frozen=True, slots=True)
class ProbeRoutingDemand:
    owner: ProbePolicyOwner


@dataclass(frozen=True, slots=True)
class PayloadDispatchRule:
    profile_id: str
    destination: IPv4Network
    priority: int
    table: int


@dataclass(frozen=True, slots=True)
class PayloadPolicyAllocation:
    profile_id: str
    table: int
    metric_space: RoutePriorityMetricSpace | None
    terminal_guard_metric: int
    path_route_protocol: int
    guard_route_protocol: int


@dataclass(frozen=True, slots=True)
class ProbePolicyAllocation:
    owner: ProbePolicyOwner
    table: int
    rule_priority: int


@dataclass(frozen=True, slots=True)
class NetworkPolicyLayout:
    payload: tuple[PayloadPolicyAllocation, ...]
    probe: tuple[ProbePolicyAllocation, ...]
    dispatch_rules: tuple[PayloadDispatchRule, ...]
    nft_family: str
    nft_table: str


def allocate_network_policy_layout(
    payload_profiles: Iterable[PayloadProfileRequest],
    probe_routing_demands: Iterable[ProbeRoutingDemand],
    platform: NetworkPolicyPlatformSpace,
) -> NetworkPolicyLayout:
    profiles = tuple(
        sorted(
            payload_profiles,
            key=lambda profile: profile.profile_id,
        )
    )
    probes = tuple(
        sorted(
            probe_routing_demands,
            key=lambda demand: demand.owner,
        )
    )
    _validate_semantic_inputs(profiles, probes)

    payload_tables = platform.payload_tables.take(len(profiles))
    probe_tables = platform.probe_tables.take(len(probes))
    probe_priorities = platform.probe_rule_priorities.take(len(probes))

    payload_allocations = tuple(
        PayloadPolicyAllocation(
            profile_id=profile.profile_id,
            table=payload_tables[index],
            metric_space=platform.route_metrics.allocate(
                len(profile.ordered_paths)
            ),
            terminal_guard_metric=platform.route_metrics.terminal_guard_metric,
            path_route_protocol=platform.path_route_protocol,
            guard_route_protocol=platform.guard_route_protocol,
        )
        for index, profile in enumerate(profiles)
    )
    table_by_profile = {
        allocation.profile_id: allocation.table
        for allocation in payload_allocations
    }

    dispatch_entries = sorted(
        (
            profile.profile_id,
            destination,
        )
        for profile in profiles
        for destination in profile.destinations
    )
    dispatch_entries.sort(
        key=lambda item: (
            -item[1].prefixlen,
            int(item[1].network_address),
            item[0],
        )
    )
    dispatch_priorities = platform.payload_rule_priorities.take(
        len(dispatch_entries)
    )
    dispatch_rules = tuple(
        PayloadDispatchRule(
            profile_id=profile_id,
            destination=destination,
            priority=dispatch_priorities[index],
            table=table_by_profile[profile_id],
        )
        for index, (profile_id, destination) in enumerate(dispatch_entries)
    )

    probe_allocations = tuple(
        ProbePolicyAllocation(
            owner=demand.owner,
            table=probe_tables[index],
            rule_priority=probe_priorities[index],
        )
        for index, demand in enumerate(probes)
    )

    return NetworkPolicyLayout(
        payload=payload_allocations,
        probe=probe_allocations,
        dispatch_rules=dispatch_rules,
        nft_family=platform.nft_family,
        nft_table=platform.nft_table,
    )


def _validate_semantic_inputs(
    profiles: tuple[PayloadProfileRequest, ...],
    probes: tuple[ProbeRoutingDemand, ...],
) -> None:
    profile_ids: set[str] = set()
    destinations: set[IPv4Network] = set()

    for profile in profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise NetworkPolicyLayoutError(
                "payload_profiles must contain PayloadProfileRequest"
            )
        if profile.profile_id in profile_ids:
            raise NetworkPolicyLayoutError(
                f"duplicate payload Profile {profile.profile_id!r}"
            )
        profile_ids.add(profile.profile_id)
        if not profile.destinations:
            raise NetworkPolicyLayoutError(
                f"payload Profile {profile.profile_id!r} has no destinations"
            )
        if len(set(profile.ordered_paths)) != len(profile.ordered_paths):
            raise NetworkPolicyLayoutError(
                f"payload Profile {profile.profile_id!r} repeats a logical path"
            )

        for destination in profile.destinations:
            if not isinstance(destination, IPv4Network):
                raise NetworkPolicyLayoutError(
                    "payload destinations must be IPv4Network"
                )
            if destination in destinations:
                raise NetworkPolicyLayoutError(
                    f"duplicate exact destination ownership {destination}"
                )
            destinations.add(destination)

    seen_probe_owners: set[ProbePolicyOwner] = set()
    for demand in probes:
        if not isinstance(demand, ProbeRoutingDemand):
            raise NetworkPolicyLayoutError(
                "probe_routing_demands must contain ProbeRoutingDemand"
            )
        if demand.owner in seen_probe_owners:
            raise NetworkPolicyLayoutError(
                f"duplicate probe routing demand {demand.owner!r}"
            )
        seen_probe_owners.add(demand.owner)
