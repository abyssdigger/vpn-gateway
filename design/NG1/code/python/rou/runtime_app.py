from __future__ import annotations

from dataclasses import dataclass
import fcntl
import logging
import os
from pathlib import Path
import signal
import threading
from typing import Callable

from .command_backend import CommandBackend, NamespaceBackend, SubprocessBackend
from .config import load_active_config
from .event_source import IpMonitorWakeupSource
from .instance_config import (
    InstanceFileConfig,
    load_instance_file_config,
    validate_instance_id,
)
from .instance_lifecycle import verify_instance
from .publication import PublicationSupervisor, compile_publication_endpoints
from .runtime import RuntimeLoopConfig, RuntimeLoopResult, run_runtime_loop
from .state_store import JsonRuntimeStateStore


LOG = logging.getLogger(__name__)


class RuntimeAppError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimePaths:
    lock_file: Path

    @classmethod
    def for_instance(
        cls,
        instance_id: str,
        *,
        runtime_dir: Path = Path("/run/vpn-gateway"),
    ) -> "RuntimePaths":
        validate_instance_id(instance_id)
        return cls(lock_file=runtime_dir / f"{instance_id}.lock")


class RuntimeLock:
    def __init__(self, path: Path):
        self.path = path
        self._fd: int | None = None

    def acquire(self) -> None:
        if self._fd is not None:
            raise RuntimeAppError("runtime lock is already held by this object")

        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            info = self.path.parent.lstat()
        except OSError as exc:
            raise RuntimeAppError(
                f"cannot stat runtime directory: {exc}"
            ) from exc
        if not self.path.parent.is_dir() or self.path.parent.is_symlink():
            raise RuntimeAppError("runtime directory must be a real directory")
        if info.st_uid != os.geteuid() or (info.st_mode & 0o022):
            raise RuntimeAppError(
                "runtime directory must be owned by current effective user "
                "and not group/world writable"
            )

        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            fd = os.open(self.path, flags, 0o600)
        except OSError as exc:
            raise RuntimeAppError(f"cannot open runtime lock: {exc}") from exc

        try:
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise RuntimeAppError(
                f"another runtime already holds {self.path}"
            ) from None
        except OSError as exc:
            os.close(fd)
            raise RuntimeAppError(f"cannot lock runtime file: {exc}") from exc

        self._fd = fd

    def close(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "RuntimeLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class SignalStop:
    def __init__(self):
        self._event = threading.Event()
        self._previous: dict[int, signal.Handlers] = {}

    def install(self) -> None:
        for signum in (signal.SIGTERM, signal.SIGINT):
            self._previous[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle)

    def _handle(self, signum, _frame) -> None:
        LOG.info("received signal %s; stopping runtime", signum)
        self._event.set()

    def should_stop(self) -> bool:
        return self._event.is_set()

    def restore(self) -> None:
        for signum, handler in self._previous.items():
            signal.signal(signum, handler)
        self._previous.clear()

    def __enter__(self) -> "SignalStop":
        self.install()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.restore()


def run_instance_runtime(
    instance_id: str,
    instance_file: str | Path,
    *,
    host_backend: CommandBackend | None = None,
    runtime_paths: RuntimePaths | None = None,
    loop_config: RuntimeLoopConfig = RuntimeLoopConfig(),
) -> RuntimeLoopResult:
    """Compose and run one complete production ROU runtime.

    The instance must already exist. This function never creates/adopts network namespace
    infrastructure; lifecycle remains the responsibility of `rou up/down`.
    """

    validate_instance_id(instance_id)
    instance_cfg: InstanceFileConfig = load_instance_file_config(instance_file)
    router_cfg = load_active_config(instance_cfg.router_config)
    backend = host_backend or SubprocessBackend()
    paths = runtime_paths or RuntimePaths.for_instance(instance_id)

    # Crash recovery must not depend on the previous process having executed its finally.
    # Close forwarding before appliance verification so SIGKILL/power-loss restart can
    # safely recover an otherwise intact namespace.
    NamespaceBackend(instance_cfg.instance.namespace, backend).run(
        ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
        check=False,
    )

    verification = verify_instance(instance_cfg.instance, backend)
    if not verification.ok:
        raise RuntimeAppError(
            "refusing to run on unverified instance: "
            + "; ".join(verification.errors)
        )

    endpoints = compile_publication_endpoints(
        router_cfg,
        listen_address=instance_cfg.publication_bind_address,
        source_address=instance_cfg.instance.host_address.ip,
        target_address=instance_cfg.instance.inner_address.ip,
    )
    supervisor = PublicationSupervisor(endpoints)
    store = JsonRuntimeStateStore(instance_cfg.state_file)

    with RuntimeLock(paths.lock_file):
        supervisor.start()
        try:
            with IpMonitorWakeupSource(instance_cfg.instance.namespace) as wakeups:
                with SignalStop() as stop:
                    result = run_runtime_loop(
                        router_cfg,
                        instance_cfg.instance.namespace,
                        backend,
                        store,
                        wakeups,
                        loop_config=loop_config,
                        should_stop=stop.should_stop,
                        health_check=supervisor.check_health,
                        local_publication_address=(
                            instance_cfg.instance.inner_address.ip
                        ),
                    )
        except BaseException:
            try:
                supervisor.close()
            except Exception:
                LOG.exception(
                    "publication teardown also failed while propagating runtime failure"
                )
            raise
        else:
            supervisor.close()
            return result
