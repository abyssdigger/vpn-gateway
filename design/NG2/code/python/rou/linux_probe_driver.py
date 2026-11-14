from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address

from .interface_identity import InterfaceIdentity
from .linux_driver import LinuxCommandRunner
from .linux_local_process import LinuxLocalProcessConfig
from .linux_observation import parse_link_json
from . import probe_attempt


class LinuxProbeDriverError(ValueError):
    pass


@dataclass(frozen=True)
class LinuxIcmpProbeDriverConfig:
    local_process: LinuxLocalProcessConfig
    gid: int
    ping_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.local_process, LinuxLocalProcessConfig):
            raise LinuxProbeDriverError(
                "probe driver requires LinuxLocalProcessConfig"
            )
        if type(self.gid) is not int or not 1 <= self.gid < (1 << 32) - 1:
            raise LinuxProbeDriverError(
                "probe gid must be a non-root 32-bit gid other than UINT32_MAX"
            )
        if (
            not isinstance(self.ping_path, str)
            or not self.ping_path.startswith("/")
        ):
            raise LinuxProbeDriverError(
                "probe ping executable path must be absolute"
            )


class LinuxIcmpProbeDriver:
    """Standalone diagnostic single-shot ICMP worker.

    This class preserves proven capability-free/generation-bound process mechanics. It is
    not a production AvailabilityProbeManager dependency and does not define availability
    cadence, hysteresis or routing verdict semantics.
    """

    def __init__(
        self,
        runner: LinuxCommandRunner,
        config: LinuxIcmpProbeDriverConfig,
    ) -> None:
        self._runner = runner
        self._config = config

    def execute(
        self,
        path: InterfaceIdentity,
        target: IPv4Address,
        *,
        timeout_seconds: int,
    ) -> probe_attempt.ProbeAttemptResult:
        if not isinstance(path, InterfaceIdentity):
            raise LinuxProbeDriverError(
                "probe driver requires InterfaceIdentity"
            )
        if not isinstance(target, IPv4Address):
            raise LinuxProbeDriverError(
                "probe driver requires IPv4Address target"
            )
        if (
            type(timeout_seconds) is not int
            or timeout_seconds <= 0
        ):
            raise LinuxProbeDriverError(
                "probe timeout_seconds must be a positive integer"
            )

        try:
            if not self._generation_is_current(path):
                return probe_attempt.ProbeAttemptResult(
                    probe_attempt.ProbeAttemptOutcome.ERROR,
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
                    path.ifname,
                    str(target),
                ),
                check=False,
            )
        except Exception as exc:
            return probe_attempt.ProbeAttemptResult(
                probe_attempt.ProbeAttemptOutcome.ERROR,
                str(exc),
            )

        if completed.returncode == 0:
            return probe_attempt.ProbeAttemptResult(probe_attempt.ProbeAttemptOutcome.REPLY)
        if completed.returncode == 1:
            return probe_attempt.ProbeAttemptResult(probe_attempt.ProbeAttemptOutcome.NO_REPLY)

        detail = completed.stderr.strip() or completed.stdout.strip()
        return probe_attempt.ProbeAttemptResult(
            probe_attempt.ProbeAttemptOutcome.ERROR,
            (
                f"ping exited rc={completed.returncode}"
                + (f": {detail}" if detail else "")
            ),
        )

    def _generation_is_current(
        self,
        path: InterfaceIdentity,
    ) -> bool:
        result = self._runner.run(
            (
                "ip",
                "-j",
                "link",
                "show",
                "dev",
                path.ifname,
            ),
            check=False,
        )
        if result.returncode != 0:
            return False
        interfaces = parse_link_json(result.stdout)
        return interfaces == (path,)

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
        fields = observed.split()
        if fields != [gid, gid]:
            raise RuntimeError(
                "cannot verify probe ping_group_range: "
                f"expected {expected!r}, observed {observed!r}"
            )
