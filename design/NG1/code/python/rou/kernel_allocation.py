from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .dispatch import compile_profile_dispatch
from .domain import ActiveConfig


RT_TABLE_UNSPEC = 0
RT_TABLE_COMPAT = 252
RT_TABLE_DEFAULT = 253
RT_TABLE_MAIN = 254
RT_TABLE_LOCAL = 255
MAX_TABLE_ID = (1 << 32) - 1

LOCAL_RULE_PRIORITY = 0
MAIN_RULE_PRIORITY = 32766
DEFAULT_RULE_PRIORITY = 32767
FIRST_OWNED_RULE_PRIORITY = LOCAL_RULE_PRIORITY + 1
MAX_OWNED_RULE_PRIORITY = MAIN_RULE_PRIORITY - 1

_RESERVED_TABLE_IDS = frozenset(
    {
        RT_TABLE_UNSPEC,
        RT_TABLE_COMPAT,
        RT_TABLE_DEFAULT,
        RT_TABLE_MAIN,
        RT_TABLE_LOCAL,
    }
)


class KernelAllocationError(ValueError):
    pass


@dataclass(frozen=True)
class ProfileTableAllocation:
    profile_name: str
    table_id: int


@dataclass(frozen=True)
class DispatchRuleAllocation:
    priority: int
    profile_name: str
    destination: IPv4Network
    table_id: int


@dataclass(frozen=True)
class KernelAllocation:
    profile_tables: tuple[ProfileTableAllocation, ...]
    dispatch_rules: tuple[DispatchRuleAllocation, ...]
    terminal_host0_priority: int

    @property
    def table_by_profile(self) -> dict[str, int]:
        return {item.profile_name: item.table_id for item in self.profile_tables}


def _usable_table_ids():
    table_id = 1
    while table_id <= MAX_TABLE_ID:
        if table_id not in _RESERVED_TABLE_IDS:
            yield table_id
        table_id += 1


def compile_kernel_allocation(config: ActiveConfig) -> KernelAllocation:
    """Allocate Profile tables and host0 RPDB priorities deterministically.

    Profile table IDs are assigned in canonical Profile-ID order. Configuration changes may
    therefore re-project numeric IDs; no table-ID stability promise spans ActiveConfig
    generations.

    RPDB priorities start immediately after the kernel local rule at priority 0. Profile
    dispatch follows normative longest-prefix ordering and the terminal host0 fail-close
    rule immediately follows the last dispatch rule, while remaining strictly before the
    conventional main-table rule at priority 32766.
    """

    enabled_profiles = sorted(
        (profile for profile in config.profiles.values() if profile.enabled),
        key=lambda profile: profile.name,
    )

    table_iter = _usable_table_ids()
    profile_tables: list[ProfileTableAllocation] = []
    table_by_profile: dict[str, int] = {}

    for profile in enabled_profiles:
        try:
            table_id = next(table_iter)
        except StopIteration:
            raise KernelAllocationError("routing-table ID space exhausted") from None
        profile_tables.append(ProfileTableAllocation(profile.name, table_id))
        table_by_profile[profile.name] = table_id

    dispatch = compile_profile_dispatch(config)
    required_rule_slots = len(dispatch) + 1
    available_rule_slots = (
        MAX_OWNED_RULE_PRIORITY - FIRST_OWNED_RULE_PRIORITY + 1
    )
    if required_rule_slots > available_rule_slots:
        raise KernelAllocationError(
            f"configuration requires {required_rule_slots} owned RPDB priorities "
            f"(including terminal host0 rule), but only {available_rule_slots} fit "
            f"between local priority {LOCAL_RULE_PRIORITY} and main priority "
            f"{MAIN_RULE_PRIORITY}"
        )

    rules: list[DispatchRuleAllocation] = []
    seen_destinations: set[IPv4Network] = set()
    priority = FIRST_OWNED_RULE_PRIORITY

    for item in dispatch:
        if item.destination in seen_destinations:
            raise KernelAllocationError(
                f"duplicate enabled Profile destination {item.destination} cannot be "
                "allocated deterministically"
            )
        seen_destinations.add(item.destination)
        table_id = table_by_profile.get(item.profile_name)
        if table_id is None:
            raise KernelAllocationError(
                f"dispatch references unallocated Profile {item.profile_name!r}"
            )
        rules.append(
            DispatchRuleAllocation(
                priority=priority,
                profile_name=item.profile_name,
                destination=item.destination,
                table_id=table_id,
            )
        )
        priority += 1

    return KernelAllocation(
        profile_tables=tuple(profile_tables),
        dispatch_rules=tuple(rules),
        terminal_host0_priority=priority,
    )
