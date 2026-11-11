from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Protocol

from .kernel_mutation import KernelMutationPlan


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class BackendLaunchError(RuntimeError):
    pass


class CommandExecutionError(RuntimeError):
    def __init__(self, result: CommandResult):
        self.result = result
        executable = result.argv[0] if result.argv else "<empty>"
        super().__init__(
            f"command {executable!r} failed with return code {result.returncode}"
            f"\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


class CommandBackend(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        ...


class SubprocessBackend:
    """Direct execve-style subprocess backend; shell expansion is never used."""

    def run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                argv,
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            executable = argv[0] if argv else "<empty>"
            raise BackendLaunchError(
                f"failed to execute {executable!r}: {exc}"
            ) from exc
        result = CommandResult(
            argv=argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and result.returncode != 0:
            raise CommandExecutionError(result)
        return result


@dataclass(frozen=True)
class NamespaceBackend:
    namespace: str
    host: CommandBackend

    def __post_init__(self) -> None:
        if not self.namespace:
            raise ValueError("namespace must be non-empty")

    def run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        return self.host.run(
            ("ip", "netns", "exec", self.namespace, *argv),
            input_text=input_text,
            check=check,
        )

    def read_text(self, argv: tuple[str, ...]) -> str:
        return self.run(argv).stdout


class KernelApplyError(RuntimeError):
    pass


def execute_kernel_mutation_plan(
    plan: KernelMutationPlan,
    backend: NamespaceBackend,
) -> tuple[CommandResult, ...]:
    """Execute a precompiled mutation plan in order.

    The plan itself is responsible for placing barrier-close first. Execution stops on the
    first failing command. There is deliberately no rollback and no forwarding reopen:
    after a mid-plan failure the namespace remains in its fail-closed state for later
    repair/reconciliation.
    """

    results: list[CommandResult] = []
    for mutation in plan.commands:
        try:
            result = backend.run(mutation.argv)
        except (CommandExecutionError, BackendLaunchError) as exc:
            raise KernelApplyError(
                f"kernel mutation phase {mutation.phase!r} failed: {exc}"
            ) from exc
        results.append(result)
    return tuple(results)
