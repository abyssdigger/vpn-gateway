"""Linux nft Driver for EXP-046/047-backed local publication rules."""

from __future__ import annotations

from dataclasses import dataclass

from .local_publication_mutation import LocalPublicationMutationStep
from .local_publication_observation import LOCAL_PUBLICATION_RULE_COMMENT
from .local_publication_policy import (
    LocalPublicationHook,
    LocalPublicationRuleSpec,
)
from .linux_nft_scaffold import NftScriptRunner


@dataclass(slots=True)
class LinuxLocalPublicationDriver:
    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)

    def apply_local_publication_step(
        self,
        step: LocalPublicationMutationStep,
    ) -> None:
        if not isinstance(step, LocalPublicationMutationStep):
            raise ValueError("step must be LocalPublicationMutationStep")

        lines: list[str] = []
        for ref in step.delete_rules:
            chain = _chain(ref.hook)
            lines.append(
                " ".join(
                    (
                        "delete rule ip vpn_gate",
                        chain,
                        "handle",
                        str(ref.handle),
                    )
                )
            )

        for rule in step.add_rules:
            lines.append(_render_add(rule))

        if not lines:
            raise ValueError("local publication transaction is empty")

        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            "\n".join(lines) + "\n",
        )


def _chain(hook: LocalPublicationHook) -> str:
    if hook is LocalPublicationHook.INPUT:
        return "stack_input"
    if hook is LocalPublicationHook.OUTPUT:
        return "stack_output"
    raise ValueError("unsupported local publication hook")


def _render_add(rule: LocalPublicationRuleSpec) -> str:
    if not isinstance(rule, LocalPublicationRuleSpec):
        raise ValueError("rule must be LocalPublicationRuleSpec")

    if rule.hook is LocalPublicationHook.INPUT:
        chain = "stack_input"
        interface = "iif"
        address = "daddr"
        port = "dport"
    elif rule.hook is LocalPublicationHook.OUTPUT:
        chain = "stack_output"
        interface = "oif"
        address = "saddr"
        port = "sport"
    else:
        raise ValueError("unsupported local publication hook")

    return " ".join(
        (
            "add rule ip vpn_gate",
            chain,
            f"meta {interface} {rule.host_boundary.ifindex}",
            f"ip {address} {rule.local_address}",
            f"{rule.protocol.value} {port} {rule.local_port}",
            "accept",
            f'comment "{LOCAL_PUBLICATION_RULE_COMMENT}"',
        )
    )


# Historical executable-evidence compatibility alias.
LinuxLocalPublicationBackend = LinuxLocalPublicationDriver
