"""Linux nft Driver for supported-integration local transport rules."""

from __future__ import annotations

from dataclasses import dataclass

from .local_integration_mutation import IntegrationLocalMutationStep
from .local_integration_observation import LOCAL_INTEGRATION_RULE_COMMENT
from .local_integration_policy import IntegrationLocalHook, IntegrationLocalRuleSpec
from .linux_nft_scaffold import NftScriptRunner


@dataclass(slots=True)
class LinuxIntegrationLocalBackend:
    runner: NftScriptRunner
    namespace: str

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)

    def apply_integration_local_step(self, step: IntegrationLocalMutationStep) -> None:
        lines: list[str] = []
        for ref in step.delete_rules:
            chain = "stack_input" if ref.hook is IntegrationLocalHook.INPUT else "stack_output"
            lines.append(
                f"delete rule ip vpn_gate {chain} handle {ref.handle}"
            )
        for rule in step.add_rules:
            lines.append(_render_add(rule))
        if not lines:
            raise ValueError("integration-local transaction is empty")
        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            "\n".join(lines) + "\n",
        )


def _render_add(rule: IntegrationLocalRuleSpec) -> str:
    proto = rule.protocol.value
    if rule.hook is IntegrationLocalHook.OUTPUT:
        parts = [
            "add rule ip vpn_gate stack_output",
            f"meta oif {rule.host_boundary.ifindex}",
            f"ip saddr {rule.local_address}",
            f"ip daddr {rule.remote_address}",
            f"{proto} dport {rule.remote_port}",
        ]
        if rule.local_port is not None:
            parts.append(f"{proto} sport {rule.local_port}")
    elif rule.hook is IntegrationLocalHook.INPUT:
        parts = [
            "add rule ip vpn_gate stack_input",
            f"meta iif {rule.host_boundary.ifindex}",
            f"ip saddr {rule.remote_address}",
            f"ip daddr {rule.local_address}",
            f"{proto} sport {rule.remote_port}",
        ]
        if rule.local_port is not None:
            parts.append(f"{proto} dport {rule.local_port}")
        else:
            parts.append("ct state established,related")
    else:
        raise ValueError("unsupported integration-local hook")
    parts.extend(("accept", f'comment "{LOCAL_INTEGRATION_RULE_COMMENT}"'))
    return " ".join(parts)
