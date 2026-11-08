from __future__ import annotations

import errno
import fcntl
import os
import socket
from pathlib import Path

from .constants import DEFAULT_LOCK_PATH, LOG
from .errors import InstanceLockError

class InstanceLock:
    """Exclusive lifetime flock.  --check-config never constructs this."""

    def __init__(self, path: Path = DEFAULT_LOCK_PATH) -> None:
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> "InstanceLock":
        fd = os.open(
            self.path,
            os.O_RDWR
            | os.O_CREAT
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if exc.errno in (errno.EACCES, errno.EAGAIN):
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

    Event-loop scheduling of WATCHDOG=1 remains an implementation task.
    """

    def __init__(self) -> None:
        self._notify_socket = os.environ.get("NOTIFY_SOCKET")

    @property
    def enabled(self) -> bool:
        return bool(self._notify_socket)

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


