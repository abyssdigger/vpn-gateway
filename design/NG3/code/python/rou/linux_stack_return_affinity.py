"""EXP-061-backed Linux lower Driver for managed-stack return affinity.

This module deliberately owns a separate nft table. It does not merge affinity
state into payload_forward permission and does not yet provide a drift-repair
executor; create/delete are bounded lower primitives for a future guarded owner.
"""

from __future__ import annotations

from dataclasses import dataclass

from .linux_nft_scaffold import NftScriptRunner
from .stack_return_affinity import (
    StackReturnAffinityDesired,
    StackReturnRuleSpec,
)


STACK_RETURN_TABLE = "vpn_gate_return_affinity"
STACK_RETURN_CHAIN = "prerouting"
STACK_RETURN_TABLE_COMMENT = "vpn-gate:ng3:stack-return-affinity-owner-v1"
STACK_RETURN_CHAIN_COMMENT = "vpn-gate:ng3:stack-return-affinity-prerouting-v1"
STACK_RETURN_CLASSIFIER_COMMENT = "vpn-gate:ng3:stack-return-affinity-classifier-v1"
STACK_RETURN_RESTORE_COMMENT = "vpn-gate:ng3:stack-return-affinity-restore-v1"


@dataclass(slots=True)
class LinuxStackReturnAffinityBackend:
    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be non-empty text")

    def create_nft(self, desired: StackReturnAffinityDesired) -> None:
        if not isinstance(desired, StackReturnAffinityDesired):
            raise ValueError("desired must be StackReturnAffinityDesired")
        if not desired.classifiers:
            return
        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            render_stack_return_affinity_nft(desired),
        )

    def delete_nft(self) -> None:
        self.runner.run(
            self._cmd("nft", "delete", "table", "ip", STACK_RETURN_TABLE)
        )

    def add_rule(self, rule: StackReturnRuleSpec) -> None:
        if not isinstance(rule, StackReturnRuleSpec):
            raise ValueError("rule must be StackReturnRuleSpec")
        self.runner.run(
            self._cmd(
                "ip", "-4", "rule", "add",
                "priority", str(rule.priority),
                "fwmark", hex(rule.mark),
                "lookup", str(rule.table),
            )
        )

    def delete_rule(self, rule: StackReturnRuleSpec) -> None:
        if not isinstance(rule, StackReturnRuleSpec):
            raise ValueError("rule must be StackReturnRuleSpec")
        self.runner.run(
            self._cmd(
                "ip", "-4", "rule", "del",
                "priority", str(rule.priority),
                "fwmark", hex(rule.mark),
                "lookup", str(rule.table),
            )
        )

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)


def render_stack_return_affinity_nft(
    desired: StackReturnAffinityDesired,
) -> str:
    if not isinstance(desired, StackReturnAffinityDesired):
        raise ValueError("desired must be StackReturnAffinityDesired")
    if not desired.classifiers:
        raise ValueError("cannot render empty stack return-affinity owner")

    lines = [
        f"table ip {STACK_RETURN_TABLE} {{",
        f'  comment "{STACK_RETURN_TABLE_COMMENT}"',
        f"  chain {STACK_RETURN_CHAIN} {{",
        "    type filter hook prerouting priority mangle; policy accept;",
        f'    comment "{STACK_RETURN_CHAIN_COMMENT}"',
    ]

    for item in desired.classifiers:
        lines.append(
            "    "
            f"meta iif {item.ingress.ifindex} "
            f"ip saddr {item.remote_prefix.with_prefixlen} "
            "ct state new "
            f"ct mark set {hex(item.mark)} "
            f'comment "{STACK_RETURN_CLASSIFIER_COMMENT}"'
        )

    for rule in desired.rules:
        lines.append(
            "    "
            f"meta iif {desired.host_boundary.ifindex} "
            f"ct mark {hex(rule.mark)} "
            "meta mark set ct mark "
            f'comment "{STACK_RETURN_RESTORE_COMMENT}"'
        )

    lines.extend(("  }", "}", ""))
    return "\n".join(lines)
