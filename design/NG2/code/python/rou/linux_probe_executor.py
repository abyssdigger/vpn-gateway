from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .linux_driver import LinuxCommandRunner
from .linux_local_process import LinuxLocalProcessConfig
from .linux_observation import parse_link_json
from .probe_rules import AvailabilityProbeRequest, ProbeMechanism


class LinuxProbeExecutorError(ValueError):
    pass


class ProbeAttemptOutcome(str, Enum):
    REPLY = "reply"
    NO_REPLY = "no-reply"
    ERROR = "error"


@dataclass(frozen=True)
class ProbeAttemptResult:
    outcome: ProbeAttemptOutcome
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is ProbeAttemptOutcome.ERROR:
            if not self.diagnostic:
                raise LinuxProbeExecutorError(
                    "probe execution error requires diagnostic"
                )
        elif self.diagnostic is not None:
            raise LinuxProbeExecutorError(
                "non-error probe result must not carry diagnostic"
            )


@dataclass(frozen=True)
class LinuxIcmpProbeExecutorConfig:
    local_process: LinuxLocalProcessConfig
    gid: int
    ping_path: str

    def __post_init__(self) -> None:
        if type(self.gid) is not int or not 1 <= self.gid < (1 << 32) - 1:
            raise LinuxProbeExecutorError(
                "probe gid must be a non-root 32-bit gid other than UINT32_MAX"
            )
        if not self.ping_path.startswith("/"):
            raise LinuxProbeExecutorError(
                "probe ping executable path must be absolute"
            )


class LinuxIcmpProbeExecutor:
    """Execute one capability-free ICMP attempt inside an already scoped namespace."""

    def __init__(
        self,
        runner: LinuxCommandRunner,
        config: LinuxIcmpProbeExecutorConfig,
    ) -> None:
        self._runner = runner
        self._config = config

    def execute(
        self,
        request: AvailabilityProbeRequest,
        *,
        timeout_seconds: int,
    ) -> ProbeAttemptResult:
        if request.mechanism is not ProbeMechanism.ICMP:
            return ProbeAttemptResult(
                ProbeAttemptOutcome.ERROR,
                f"unsupported probe mechanism {request.mechanism!r}",
            )
        if (
            type(timeout_seconds) is not int
            or timeout_seconds <= 0
        ):
            raise LinuxProbeExecutorError(
                "probe timeout_seconds must be a positive integer"
            )

        try:
            if not self._generation_is_current(request):
                return ProbeAttemptResult(
                    ProbeAttemptOutcome.ERROR,
                    "requested probe interface generation is not current",
                )

            self._prepare_ping_socket_prerequisite()

            uid = str(self._config.local_process.uid)
            gid = str(self._config.gid)
            completed = self._runner.run(
                (
                    "setpriv",
                    f"--reuid={uid}",
                    f"--regid={gid}",
                    "--clear-groups",
                    "--bounding-set=-all",
                    "--no-new-privs",
                    self._config.ping_path,
                    "-n",
                    "-c",
                    "1",
                    "-W",
                    str(timeout_seconds),
                    "-I",
                    request.path.ifname,
                    str(request.target),
                ),
                check=False,
            )
        except Exception as exc:
            return ProbeAttemptResult(
                ProbeAttemptOutcome.ERROR,
                str(exc),
            )

        if completed.returncode == 0:
            return ProbeAttemptResult(ProbeAttemptOutcome.REPLY)
        if completed.returncode == 1:
            return ProbeAttemptResult(ProbeAttemptOutcome.NO_REPLY)

        detail = completed.stderr.strip() or completed.stdout.strip()
        return ProbeAttemptResult(
            ProbeAttemptOutcome.ERROR,
            (
                f"ping exited rc={completed.returncode}"
                + (f": {detail}" if detail else "")
            ),
        )

    def _generation_is_current(
        self,
        request: AvailabilityProbeRequest,
    ) -> bool:
        result = self._runner.run(
            (
                "ip",
                "-j",
                "link",
                "show",
                "dev",
                request.path.ifname,
            ),
            check=False,
        )
        if result.returncode != 0:
            return False
        interfaces = parse_link_json(result.stdout)
        return interfaces == (request.path,)

    def _prepare_ping_socket_prerequisite(self) -> None:
        gid = str(self._config.gid)
        expected = f"{gid} {gid}"
        self._runner.run(
            (
                "sysctl",
                "-q",
                "-w",
                f"net.ipv4.ping_group_range={expected}",
            )
        )
        observed = self._runner.run(
            ("sysctl", "-n", "net.ipv4.ping_group_range")
        ).stdout.strip()
        if observed != expected:
            raise RuntimeError(
                "cannot verify probe ping_group_range: "
                f"expected {expected!r}, observed {observed!r}"
            )
