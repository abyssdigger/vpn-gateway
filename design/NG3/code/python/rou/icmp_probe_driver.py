"""EXP-067-backed one-shot Linux ICMP availability Driver."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Protocol, Sequence

from .probe_policy import AvailabilityProbeMechanism
from .probe_runtime import (
    ProbeObservationContext,
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)


class IcmpProbeDriverError(ValueError):
    pass


class ProbeCommandError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class IcmpProbeExecutionPolicy:
    """Lower runtime deadline policy, not user-facing availability config."""

    reply_timeout_seconds: int
    process_grace_seconds: int = 1

    def __post_init__(self) -> None:
        if (
            type(self.reply_timeout_seconds) is not int
            or self.reply_timeout_seconds <= 0
        ):
            raise IcmpProbeDriverError(
                "reply_timeout_seconds must be a positive integer"
            )
        if (
            type(self.process_grace_seconds) is not int
            or self.process_grace_seconds <= 0
        ):
            raise IcmpProbeDriverError(
                "process_grace_seconds must be a positive integer"
            )

    @property
    def process_timeout_seconds(self) -> int:
        return self.reply_timeout_seconds + self.process_grace_seconds


@dataclass(frozen=True, slots=True)
class ProbeCommandResult:
    returncode: int
    stdout: str
    stderr: str

    def __post_init__(self) -> None:
        if type(self.returncode) is not int:
            raise IcmpProbeDriverError("returncode must be an integer")
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise IcmpProbeDriverError("stdout/stderr must be text")


class ProbeCommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout_seconds: int,
    ) -> ProbeCommandResult:
        """Execute one bounded command or raise ProbeCommandError."""


@dataclass(slots=True)
class SubprocessProbeCommandRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout_seconds: int,
    ) -> ProbeCommandResult:
        try:
            value = subprocess.run(
                tuple(argv),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProbeCommandError(
                f"probe command exceeded {timeout_seconds}s process deadline"
            ) from exc
        except OSError as exc:
            raise ProbeCommandError(
                f"probe command could not execute: {exc}"
            ) from exc
        return ProbeCommandResult(
            value.returncode,
            value.stdout,
            value.stderr,
        )


@dataclass(slots=True)
class LinuxIcmpProbeDriver:
    runner: ProbeCommandRunner
    namespace: str
    process_uid: int
    execution_policy: IcmpProbeExecutionPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise IcmpProbeDriverError(
                "namespace must be non-empty text"
            )
        if (
            type(self.process_uid) is not int
            or not 1 <= self.process_uid <= 0xFFFFFFFE
        ):
            raise IcmpProbeDriverError(
                "process_uid must be a non-root Linux uid"
            )
        if not isinstance(
            self.execution_policy,
            IcmpProbeExecutionPolicy,
        ):
            raise IcmpProbeDriverError(
                "execution_policy must be IcmpProbeExecutionPolicy"
            )

    def check(
        self,
        context: ProbeObservationContext,
    ) -> ProbeTechnicalObservation:
        if not isinstance(context, ProbeObservationContext):
            raise IcmpProbeDriverError(
                "context must be ProbeObservationContext"
            )
        if context.intent.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise IcmpProbeDriverError(
                "LinuxIcmpProbeDriver supports only ICMP"
            )

        try:
            result = self.runner.run(
                self._command(context),
                timeout_seconds=(
                    self.execution_policy.process_timeout_seconds
                ),
            )
        except ProbeCommandError as exc:
            return ProbeTechnicalObservation(
                ProbeTechnicalOutcome.LOCAL_ERROR,
                _diagnostic(str(exc)),
            )

        if result.returncode == 0:
            return ProbeTechnicalObservation(
                ProbeTechnicalOutcome.REPLY
            )
        if result.returncode == 1:
            return ProbeTechnicalObservation(
                ProbeTechnicalOutcome.NO_REPLY
            )
        return ProbeTechnicalObservation(
            ProbeTechnicalOutcome.LOCAL_ERROR,
            _diagnostic(
                result.stderr
                or result.stdout
                or f"ping exited with status {result.returncode}"
            ),
        )

    def _command(
        self,
        context: ProbeObservationContext,
    ) -> tuple[str, ...]:
        return (
            "ip", "netns", "exec", self.namespace,
            "setpriv",
            "--reuid", str(self.process_uid),
            "--regid", str(self.process_uid),
            "--clear-groups",
            "ping",
            "-n",
            "-c", "1",
            "-W", str(
                self.execution_policy.reply_timeout_seconds
            ),
            str(context.intent.target),
        )


def _diagnostic(value: str) -> str:
    compact = " ".join(value.strip().split())
    if not compact:
        compact = "ICMP probe local execution failure"
    # Diagnostics are current status material, not an unbounded command-output store.
    return compact[:1024]
