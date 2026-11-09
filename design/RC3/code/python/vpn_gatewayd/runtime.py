from __future__ import annotations

import errno
import fcntl
import os
import socket
import stat
from pathlib import Path

from .constants import DEFAULT_LOCK_PATH, LOG
from .errors import InstanceLockError

class InstanceLock:
    """Exclusive lifetime flock.  --check-config never constructs this."""

    def __init__(self, path: Path = DEFAULT_LOCK_PATH) -> None:
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> "InstanceLock":
        runtime_dir = self.path.parent
        expected_uid = os.geteuid()

        try:
            os.mkdir(runtime_dir, 0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise InstanceLockError(
                f"cannot create runtime directory {runtime_dir}: {exc}"
            ) from exc

        dir_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            dir_fd = os.open(runtime_dir, dir_flags)
        except OSError as exc:
            raise InstanceLockError(
                f"cannot safely open runtime directory {runtime_dir}: {exc}"
            ) from exc

        try:
            directory_stat = os.fstat(dir_fd)
            directory_mode = stat.S_IMODE(directory_stat.st_mode)
            if not stat.S_ISDIR(directory_stat.st_mode):
                raise InstanceLockError(
                    f"runtime path is not a directory: {runtime_dir}"
                )
            if directory_stat.st_uid != expected_uid:
                raise InstanceLockError(
                    f"runtime directory owner mismatch: {runtime_dir}: "
                    f"uid={directory_stat.st_uid} expected={expected_uid}"
                )
            if directory_mode != 0o700:
                raise InstanceLockError(
                    f"runtime directory mode mismatch: {runtime_dir}: "
                    f"mode={directory_mode:04o} expected=0700"
                )

            try:
                fd = os.open(
                    self.path.name,
                    os.O_RDWR
                    | os.O_CREAT
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=dir_fd,
                )
            except OSError as exc:
                raise InstanceLockError(
                    f"cannot safely open lock file {self.path}: {exc}"
                ) from exc
        finally:
            os.close(dir_fd)

        try:
            lock_stat = os.fstat(fd)
            lock_mode = stat.S_IMODE(lock_stat.st_mode)
            if not stat.S_ISREG(lock_stat.st_mode):
                raise InstanceLockError(
                    f"lock path is not a regular file: {self.path}"
                )
            if lock_stat.st_uid != expected_uid:
                raise InstanceLockError(
                    f"lock file owner mismatch: {self.path}: "
                    f"uid={lock_stat.st_uid} expected={expected_uid}"
                )
            if lock_mode != 0o600:
                raise InstanceLockError(
                    f"lock file mode mismatch: {self.path}: "
                    f"mode={lock_mode:04o} expected=0600"
                )

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            os.close(fd)
            if isinstance(exc, OSError) and exc.errno in (
                errno.EACCES,
                errno.EAGAIN,
            ):
                raise InstanceLockError(
                    f"another vpn-gatewayd instance is running "
                    f"(lock busy: {self.path})"
                ) from exc
            raise

        self._fd = fd
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


# ---------------------------------------------------------------------------
# Optional stdlib systemd notification helper
# ---------------------------------------------------------------------------


class SystemdNotifier:
    """
    Minimal optional sd_notify-compatible helper.

    WATCHDOG_USEC/WATCHDOG_PID are interpreted only as event-loop timing
    metadata. Notification transport failure never changes gateway policy.
    """

    def __init__(self) -> None:
        self._notify_socket = os.environ.get("NOTIFY_SOCKET")

    @property
    def enabled(self) -> bool:
        return bool(self._notify_socket)

    def watchdog_interval(self) -> float | None:
        """
        Return a conservative heartbeat cadence in seconds.

        systemd recommends notifying more often than WatchdogSec. Use half of
        WATCHDOG_USEC and honor WATCHDOG_PID when present.
        """
        if not self._notify_socket:
            return None

        watchdog_pid = os.environ.get("WATCHDOG_PID")
        if watchdog_pid:
            try:
                if int(watchdog_pid, 10) != os.getpid():
                    return None
            except ValueError:
                LOG.warning("invalid WATCHDOG_PID=%r; watchdog disabled", watchdog_pid)
                return None

        value = os.environ.get("WATCHDOG_USEC")
        if not value:
            return None
        try:
            usec = int(value, 10)
        except ValueError:
            LOG.warning("invalid WATCHDOG_USEC=%r; watchdog disabled", value)
            return None
        if usec <= 0:
            LOG.warning("non-positive WATCHDOG_USEC=%r; watchdog disabled", value)
            return None

        return usec / 2_000_000.0

    def notify(self, message: str) -> None:
        if not self._notify_socket:
            return

        address: str | bytes
        if self._notify_socket.startswith("@"):
            address = b"\0" + self._notify_socket[1:].encode()
        else:
            address = self._notify_socket

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(address)
            sock.sendall(message.encode())
        except OSError as exc:
            # Notification transport is operational metadata, not gateway
            # policy.  A stale/unavailable NOTIFY_SOCKET must not kill the
            # daemon or watchdog/event loop.
            LOG.warning("sd_notify failed: %s", exc)
        finally:
            sock.close()

    def ready(self) -> None:
        self.notify("READY=1")

    def watchdog(self) -> None:
        self.notify("WATCHDOG=1")

    def stopping(self) -> None:
        self.notify("STOPPING=1")


# ---------------------------------------------------------------------------
# Daemon orchestration
# ---------------------------------------------------------------------------


