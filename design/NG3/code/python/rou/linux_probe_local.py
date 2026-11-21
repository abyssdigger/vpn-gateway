"""Linux nft Driver for EXP-066-backed probe-local rules."""

from __future__ import annotations

from dataclasses import dataclass

from .linux_nft_scaffold import NftScriptRunner
from .probe_local_mutation import ProbeLocalMutationStep
from .probe_local_observation import PROBE_LOCAL_RULE_COMMENT
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeLocalHook,
    ProbeLocalRuleSpec,
)


@dataclass(slots=True)
class LinuxProbeLocalDriver:
    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)

    def apply_probe_local_step(self, step: ProbeLocalMutationStep) -> None:
        if not isinstance(step, ProbeLocalMutationStep):
            raise ValueError("step must be ProbeLocalMutationStep")

        lines: list[str] = []
        for ref in step.delete_rules:
            lines.append(
                " ".join(
                    (
                        "delete rule ip vpn_gate",
                        _chain(ref.hook),
                        "handle",
                        str(ref.handle),
                    )
                )
            )
        for rule in step.add_rules:
            lines.append(_render_add(rule))

        if not lines:
            raise ValueError("probe-local transaction is empty")

        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            "\n".join(lines) + "\n",
        )


def _chain(hook: ProbeLocalHook) -> str:
    if hook is ProbeLocalHook.INPUT:
        return "stack_input"
    if hook is ProbeLocalHook.OUTPUT:
        return "stack_output"
    raise ValueError("unsupported probe-local hook")


def _render_add(rule: ProbeLocalRuleSpec) -> str:
    if not isinstance(rule, ProbeLocalRuleSpec):
        raise ValueError("rule must be ProbeLocalRuleSpec")
    if rule.mechanism is not AvailabilityProbeMechanism.ICMP:
        raise ValueError("Release 1 probe-local rule must be ICMP")

    if rule.hook is ProbeLocalHook.OUTPUT:
        return " ".join(
            (
                "add rule ip vpn_gate stack_output",
                f"meta skuid {rule.process_uid}",
                f"meta oif {rule.endpoint.ifindex}",
                f"ip daddr {rule.target}",
                "ip protocol icmp",
                f"ct mark set {hex(rule.conntrack_mark)}",
                "accept",
                f'comment "{PROBE_LOCAL_RULE_COMMENT}"',
            )
        )
    if rule.hook is ProbeLocalHook.INPUT:
        return " ".join(
            (
                "add rule ip vpn_gate stack_input",
                f"meta iif {rule.endpoint.ifindex}",
                f"ip saddr {rule.target}",
                "ip protocol icmp",
                f"ct mark {hex(rule.conntrack_mark)}",
                "accept",
                f'comment "{PROBE_LOCAL_RULE_COMMENT}"',
            )
        )
    raise ValueError("unsupported probe-local hook")


# Historical executable-evidence compatibility alias.
LinuxProbeLocalBackend = LinuxProbeLocalDriver
