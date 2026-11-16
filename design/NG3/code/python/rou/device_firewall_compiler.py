"""Pure semantic compiler for ordinary Release-1 Device firewall rules.

External grammar, endpoint-scoped rules, physical mutation and final REJECT
realization are intentionally outside this unit.
"""

from __future__ import annotations

import json
from ipaddress import IPv4Network

from .device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallDesiredState,
    DeviceFirewallRuleSpec,
)
from .device_firewall_structure import DeviceFirewallRuleAction
from .device_policy import (
    DeviceFirewallAction,
    DeviceFirewallDirection,
    DeviceFirewallPolicyIntent,
    DeviceFirewallRuleIntent,
)
from .interface_identity import InterfaceIdentity


class DeviceFirewallCompileError(ValueError):
    pass


def compile_device_firewall_policy(
    policy: DeviceFirewallPolicyIntent,
    host_boundary: InterfaceIdentity,
    path: InterfaceIdentity,
    *,
    out_chain_name: str,
    in_chain_name: str,
) -> DeviceFirewallDesiredState:
    """Compile one Device/path policy into exact lower child-chain desired data.

    Two direction-specific child chains are used. IN and OUT packet domains are
    disjoint, so removing opposite-direction rules from each chain preserves
    the accepted first-match semantics while avoiding redundant interface
    predicates on every explicit rule.

    REJECT remains behind its separate lower-realization gate.
    """
    if not isinstance(policy, DeviceFirewallPolicyIntent):
        raise DeviceFirewallCompileError(
            "policy must be DeviceFirewallPolicyIntent"
        )
    if not isinstance(host_boundary, InterfaceIdentity):
        raise DeviceFirewallCompileError(
            "host_boundary must be InterfaceIdentity"
        )
    if not isinstance(path, InterfaceIdentity):
        raise DeviceFirewallCompileError(
            "path must be InterfaceIdentity"
        )
    for label, name in (
        ("out_chain_name", out_chain_name),
        ("in_chain_name", in_chain_name),
    ):
        if not isinstance(name, str) or not name:
            raise DeviceFirewallCompileError(
                f"{label} must be non-empty text"
            )
    if out_chain_name == in_chain_name:
        raise DeviceFirewallCompileError(
            "IN and OUT child chain names must be distinct"
        )

    if policy.rules is None:
        return DeviceFirewallDesiredState(chains=())

    out_rules = tuple(
        _compile_rule(rule)
        for rule in policy.rules
        if rule.direction is DeviceFirewallDirection.OUT
    )
    in_rules = tuple(
        _compile_rule(rule)
        for rule in policy.rules
        if rule.direction is DeviceFirewallDirection.IN
    )

    terminal = DeviceFirewallRuleSpec(
        match_expr_json=(),
        action=DeviceFirewallRuleAction.DROP,
        action_json='{"drop":null}',
        terminal_fallthrough=True,
    )

    return DeviceFirewallDesiredState(
        chains=(
            DeviceFirewallChainSpec(
                ingress=host_boundary,
                egress=path,
                child_chain_name=out_chain_name,
                rules=out_rules + (terminal,),
            ),
            DeviceFirewallChainSpec(
                ingress=path,
                egress=host_boundary,
                child_chain_name=in_chain_name,
                rules=in_rules + (terminal,),
            ),
        )
    )


def _compile_rule(
    rule: DeviceFirewallRuleIntent,
) -> DeviceFirewallRuleSpec:
    if rule.action is DeviceFirewallAction.REJECT:
        raise DeviceFirewallCompileError(
            "Device firewall REJECT lower realization is not accepted yet"
        )

    matches: list[str] = []
    if rule.source_ipv4_cidr is not None:
        matches.append(
            _match_json(
                {"payload": {"protocol": "ip", "field": "saddr"}},
                _ipv4_operand(rule.source_ipv4_cidr),
            )
        )
    if rule.destination_ipv4_cidr is not None:
        matches.append(
            _match_json(
                {"payload": {"protocol": "ip", "field": "daddr"}},
                _ipv4_operand(rule.destination_ipv4_cidr),
            )
        )

    protocol = rule.protocol
    has_ports = (
        rule.source_port is not None
        or rule.destination_port is not None
    )

    if has_ports:
        if protocol not in {"tcp", "udp"}:
            raise DeviceFirewallCompileError(
                "port predicates require normalized tcp or udp protocol"
            )
        if rule.source_port is not None:
            matches.append(
                _match_json(
                    {
                        "payload": {
                            "protocol": protocol,
                            "field": "sport",
                        }
                    },
                    rule.source_port,
                )
            )
        if rule.destination_port is not None:
            matches.append(
                _match_json(
                    {
                        "payload": {
                            "protocol": protocol,
                            "field": "dport",
                        }
                    },
                    rule.destination_port,
                )
            )
        # EXP-042: nft canonicalization removes redundant meta l4proto
        # when protocol-specific TCP/UDP port expressions are present.
    elif protocol is not None:
        if protocol not in {"tcp", "udp", "icmp"}:
            raise DeviceFirewallCompileError(
                "normalized protocol is not proven by the current lower gate"
            )
        matches.append(
            _match_json(
                {"meta": {"key": "l4proto"}},
                protocol,
            )
        )

    if rule.action is DeviceFirewallAction.ALLOW:
        lower_action = DeviceFirewallRuleAction.RETURN
        action_json = '{"return":null}'
    elif rule.action is DeviceFirewallAction.DENY:
        lower_action = DeviceFirewallRuleAction.DROP
        action_json = '{"drop":null}'
    else:
        raise DeviceFirewallCompileError(
            f"unsupported Device firewall action {rule.action!r}"
        )

    return DeviceFirewallRuleSpec(
        match_expr_json=tuple(matches),
        action=lower_action,
        action_json=action_json,
    )


def _ipv4_operand(network: IPv4Network) -> object:
    if network.prefixlen == 32:
        return str(network.network_address)
    return {
        "prefix": {
            "addr": str(network.network_address),
            "len": network.prefixlen,
        }
    }


def _match_json(left: dict, right: object) -> str:
    return json.dumps(
        {
            "match": {
                "op": "==",
                "left": left,
                "right": right,
            }
        },
        sort_keys=True,
        separators=(",", ":"),
    )
