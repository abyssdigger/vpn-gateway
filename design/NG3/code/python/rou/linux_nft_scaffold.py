from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Protocol, Sequence

from .nft_namespace_inventory import (
    LinuxNftNamespaceReader,
    NftNamespaceObservation,
)
from .nft_payload_scaffold import (
    PAYLOAD_NFT_SCAFFOLD,
    NftBaseChainSpec,
)


class NftScriptRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one command or raise; return stdout."""

    def run_script(
        self,
        argv: Sequence[str],
        script: str,
    ) -> str:
        """Run one stdin-fed command or raise; return stdout."""


class SubprocessNftRunner:
    def run(self, argv: Sequence[str]) -> str:
        completed = subprocess.run(
            tuple(argv),
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout

    def run_script(
        self,
        argv: Sequence[str],
        script: str,
    ) -> str:
        completed = subprocess.run(
            tuple(argv),
            input=script,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout


@dataclass(slots=True)
class LinuxNftScaffoldDriver:
    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def observe_nft_namespace(self) -> NftNamespaceObservation:
        return LinuxNftNamespaceReader(
            self.runner,
            self.namespace,
        ).observe_nft_namespace()

    def create_payload_scaffold(self) -> None:
        self.runner.run_script(
            self._script_command(),
            _full_scaffold_script(),
        )

    def add_payload_scaffold_chains(
        self,
        missing: tuple[NftBaseChainSpec, ...],
    ) -> None:
        if not isinstance(missing, tuple) or not missing:
            raise ValueError("missing must be a non-empty tuple")
        known = set(PAYLOAD_NFT_SCAFFOLD)
        if any(spec not in known for spec in missing):
            raise ValueError(
                "missing contains a chain outside the invariant payload scaffold"
            )
        if len(set(missing)) != len(missing):
            raise ValueError("missing contains duplicate chain specs")

        script = "".join(
            _add_chain_statement(spec)
            for spec in PAYLOAD_NFT_SCAFFOLD
            if spec in set(missing)
        )
        self.runner.run_script(
            self._script_command(),
            script,
        )

    def _script_command(self) -> tuple[str, ...]:
        return (
            "ip",
            "netns",
            "exec",
            self.namespace,
            "nft",
            "-f",
            "-",
        )


def _full_scaffold_script() -> str:
    lines = [
        "table ip vpn_gate {",
        '    comment "vpn-gate:ng3:owner-v1"',
    ]
    for spec in PAYLOAD_NFT_SCAFFOLD:
        lines.extend(
            (
                f"    chain {spec.name} {{",
                (
                    f"        type {spec.chain_type} hook {spec.hook} "
                    f"priority {spec.priority}; policy {spec.policy};"
                ),
                f'        comment "{spec.comment}"',
                "    }",
            )
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def _add_chain_statement(spec: NftBaseChainSpec) -> str:
    return (
        f"add chain ip vpn_gate {spec.name} {{ "
        f"type {spec.chain_type} hook {spec.hook} priority {spec.priority}; "
        f"policy {spec.policy}; comment \"{spec.comment}\"; }}\n"
    )


# Historical executable-evidence compatibility alias.
LinuxNftScaffoldBackend = LinuxNftScaffoldDriver
