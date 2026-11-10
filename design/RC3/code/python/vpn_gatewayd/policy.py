from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network
from typing import Mapping

from .interfaces import ProfileInterfaceState
from .models import GatewayConfig, VpnProfileConfig

_REJECT = "REJECT --reject-with icmp-host-prohibited"


@dataclass(slots=True, frozen=True)
class PolicyChain:
    name: str
    rules: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class FilterPolicy:
    input_jumps: tuple[str, ...]
    forward_jumps: tuple[str, ...]
    chains: tuple[PolicyChain, ...]

    def chain(self, name: str) -> PolicyChain:
        for chain in self.chains:
            if chain.name == name:
                return chain
        raise KeyError(name)


@dataclass(slots=True, frozen=True)
class NatPolicy:
    postrouting_jumps: tuple[str, ...]
    chains: tuple[PolicyChain, ...]

    def chain(self, name: str) -> PolicyChain:
        for chain in self.chains:
            if chain.name == name:
                return chain
        raise KeyError(name)


@dataclass(slots=True, frozen=True)
class FirewallNatPolicy:
    filter: FilterPolicy
    nat: NatPolicy


def _profile_ids(config: GatewayConfig) -> tuple[str, ...]:
    return tuple(sorted(config.vpns, key=lambda item: item.upper()))


def _effective_sources(
    config: GatewayConfig,
    profile: VpnProfileConfig,
) -> tuple[IPv4Network, ...]:
    merged = set(config.common_allowed_sources)
    merged.update(profile.allowed_sources)
    return tuple(
        sorted(merged, key=lambda net: (int(net.network_address), net.prefixlen))
    )


def _require_complete_interface_state(
    config: GatewayConfig,
    state_by_profile: Mapping[str, ProfileInterfaceState],
) -> None:
    expected = frozenset(config.vpns)
    actual = frozenset(state_by_profile)
    if actual != expected:
        raise ValueError(
            "incomplete interface-state mapping: "
            f"missing={sorted(expected - actual)!r}, "
            f"unexpected={sorted(actual - expected)!r}"
        )


def _selector_guard_rules(
    chain: str,
    profile: VpnProfileConfig,
) -> tuple[str, ...]:
    return tuple(
        f"-A {chain} -i {interface} -j {_REJECT}"
        for interface in profile.interface.guard_interfaces()
    )


def _input_guard_rules(
    config: GatewayConfig,
    profile_ids: tuple[str, ...],
) -> tuple[str, ...]:
    rules: list[str] = []
    for profile_id in profile_ids:
        rules.extend(
            _selector_guard_rules("VPNG-INPUT-GUARD", config.vpns[profile_id])
        )
    rules.append("-A VPNG-INPUT-GUARD -j RETURN")
    return tuple(rules)


def _ingress_guard_rules(
    config: GatewayConfig,
    profile_ids: tuple[str, ...],
) -> tuple[str, ...]:
    rules: list[str] = []
    for profile_id in profile_ids:
        rules.extend(
            _selector_guard_rules("VPNG-INGRESS", config.vpns[profile_id])
        )
    rules.append("-A VPNG-INGRESS -j RETURN")
    return tuple(rules)


def _reserved_rules(
    config: GatewayConfig,
    profile_ids: tuple[str, ...],
) -> tuple[str, ...]:
    rules = [
        f"-A VPNG-RESERVED -d {config.vpns[profile_id].network} -j {_REJECT}"
        for profile_id in profile_ids
    ]
    rules.append("-A VPNG-RESERVED -j RETURN")
    return tuple(rules)


def _forward_deny_rules() -> tuple[str, ...]:
    return (
        "-A VPNG-FORWARD-DENY -m conntrack --ctstate INVALID -j DROP",
        f"-A VPNG-FORWARD-DENY -j {_REJECT}",
    )


def _filter_jumps(
    config: GatewayConfig,
    profile_ids: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    input_jumps = tuple(
        [
            *(
                f"-A INPUT -j {config.vpns[profile_id].chain_input}"
                for profile_id in profile_ids
            ),
            "-A INPUT -j VPNG-INPUT-GUARD",
        ]
    )
    forward_jumps = tuple(
        [
            "-A FORWARD -j VPNG-INGRESS",
            "-A FORWARD -j VPNG-RESERVED",
            *(
                f"-A FORWARD -j {config.vpns[profile_id].chain_forward}"
                for profile_id in profile_ids
            ),
            "-A FORWARD -j VPNG-FORWARD-DENY",
        ]
    )
    return input_jumps, forward_jumps


def _binding_input_rules(chain: str, interface: str) -> tuple[str, ...]:
    return (
        f"-A {chain} -i {interface} -m conntrack --ctstate INVALID -j DROP",
        f"-A {chain} -i {interface} -m conntrack "
        "--ctstate RELATED,ESTABLISHED -j ACCEPT",
        f"-A {chain} -i {interface} -j {_REJECT}",
    )


def _build_filter_policy(
    config: GatewayConfig,
    *,
    state_by_profile: Mapping[str, ProfileInterfaceState] | None,
) -> FilterPolicy:
    profile_ids = _profile_ids(config)
    input_jumps, forward_jumps = _filter_jumps(config, profile_ids)
    full = state_by_profile is not None
    if full:
        assert state_by_profile is not None
        _require_complete_interface_state(config, state_by_profile)

    chains: list[PolicyChain] = []

    ingress_rules: list[str] = []
    if full:
        assert state_by_profile is not None
        for profile_id in profile_ids:
            for binding in state_by_profile[profile_id].active_bindings:
                ingress_rules.extend(
                    _binding_input_rules("VPNG-INGRESS", binding.name)
                )
    ingress_rules.extend(_ingress_guard_rules(config, profile_ids)[:-1])
    ingress_rules.append("-A VPNG-INGRESS -j RETURN")
    chains.append(PolicyChain("VPNG-INGRESS", tuple(ingress_rules)))
    chains.append(
        PolicyChain(
            "VPNG-RESERVED",
            _reserved_rules(config, profile_ids),
        )
    )

    for profile_id in profile_ids:
        profile = config.vpns[profile_id]
        state = (
            None
            if state_by_profile is None
            else state_by_profile[profile_id]
        )

        input_rules: list[str] = []
        if state is not None:
            for binding in state.active_bindings:
                input_rules.extend(
                    _binding_input_rules(profile.chain_input, binding.name)
                )
        input_rules.append(f"-A {profile.chain_input} -j RETURN")
        chains.append(PolicyChain(profile.chain_input, tuple(input_rules)))

        forward_rules: list[str] = []
        for destination in profile.routes:
            if state is not None:
                for binding in state.active_bindings:
                    interface = binding.name
                    forward_rules.append(
                        f"-A {profile.chain_forward} -d {destination} "
                        f"-o {interface} -m conntrack "
                        "--ctstate INVALID -j DROP"
                    )
                    for source in _effective_sources(config, profile):
                        forward_rules.append(
                            f"-A {profile.chain_forward} -s {source} "
                            f"-d {destination} -o {interface} -j ACCEPT"
                        )
            forward_rules.append(
                f"-A {profile.chain_forward} -d {destination} -j {_REJECT}"
            )
        forward_rules.append(f"-A {profile.chain_forward} -j RETURN")
        chains.append(
            PolicyChain(profile.chain_forward, tuple(forward_rules))
        )

    chains.append(
        PolicyChain(
            "VPNG-INPUT-GUARD",
            _input_guard_rules(config, profile_ids),
        )
    )
    chains.append(
        PolicyChain("VPNG-FORWARD-DENY", _forward_deny_rules())
    )
    return FilterPolicy(
        input_jumps=input_jumps,
        forward_jumps=forward_jumps,
        chains=tuple(chains),
    )


def desired_isolation_filter(config: GatewayConfig) -> FilterPolicy:
    return _build_filter_policy(config, state_by_profile=None)


def desired_full_policy(
    config: GatewayConfig,
    state_by_profile: Mapping[str, ProfileInterfaceState],
) -> FirewallNatPolicy:
    _require_complete_interface_state(config, state_by_profile)
    profile_ids = _profile_ids(config)
    filter_policy = _build_filter_policy(
        config,
        state_by_profile=state_by_profile,
    )

    postrouting_jumps = tuple(
        f"-A POSTROUTING -j {config.vpns[profile_id].chain_nat}"
        for profile_id in profile_ids
    )
    nat_chains: list[PolicyChain] = []
    for profile_id in profile_ids:
        profile = config.vpns[profile_id]
        rules = [
            f"-A {profile.chain_nat} -o {binding.name} "
            "-m addrtype ! --src-type LOCAL -j MASQUERADE"
            for binding in state_by_profile[profile_id].active_bindings
        ]
        rules.append(f"-A {profile.chain_nat} -j RETURN")
        nat_chains.append(
            PolicyChain(profile.chain_nat, tuple(rules))
        )

    return FirewallNatPolicy(
        filter=filter_policy,
        nat=NatPolicy(
            postrouting_jumps=postrouting_jumps,
            chains=tuple(nat_chains),
        ),
    )
