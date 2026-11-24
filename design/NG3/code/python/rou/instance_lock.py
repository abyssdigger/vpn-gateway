"""Controller lifetime lock and runtime-directory integrity for NG3."""

from __future__ import annotations

from dataclasses import dataclass
import errno
import fcntl
import os
from pathlib import Path
import stat


_LOCK_FILENAME = "vpn-gate.lock"


class ControllerInstanceLockError(RuntimeError):
    pass


class ControllerInstanceBusyError(ControllerInstanceLockError):
    pass


@dataclass(frozen=True, slots=True)
class InstanceLockSpec:
    runtime_directory: Path
    expected_owner_uid: int

    def __post_init__(self) -> None:
        path = self.runtime_directory
        if isinstance(path, str):
            path = Path(path)
            object.__setattr__(self, "runtime_directory", path)
        if not isinstance(path, Path):
            raise ValueError("runtime_directory must be pathlib.Path or string")
        if not path.is_absolute():
            raise ValueError("runtime_directory must be absolute")
        if type(self.expected_owner_uid) is not int or self.expected_owner_uid < 0:
            raise ValueError("expected_owner_uid must be a non-negative integer")

    @property
    def lock_path(self) -> Path:
        return self.runtime_directory / _LOCK_FILENAME


class ControllerInstanceLock:
    def __init__(self, spec: InstanceLockSpec, fd: int) -> None:
        self.spec = spec
        self._fd = fd

    @property
    def acquired(self) -> bool:
        return self._fd >= 0

    def release(self) -> None:
        if self._fd < 0:
            return
        fd = self._fd
        self._fd = -1
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self) -> "ControllerInstanceLock":
        if not self.acquired:
            raise ControllerInstanceLockError(
                "controller instance lock is already released"
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def acquire_controller_instance_lock(
    spec: InstanceLockSpec,
) -> ControllerInstanceLock:
    if not isinstance(spec, InstanceLockSpec):
        raise ValueError("spec must be InstanceLockSpec")

    _ensure_runtime_directory(spec)

    flags = (
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        fd = os.open(spec.lock_path, flags, 0o600)
    except OSError as exc:
        raise ControllerInstanceLockError(
            f"cannot safely open controller lock {spec.lock_path}: {exc}"
        ) from exc

    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ControllerInstanceLockError(
                "controller lock object is not a regular file"
            )
        mode = stat.S_IMODE(info.st_mode)
        if mode != 0o600:
            raise ControllerInstanceLockError(
                f"controller lock mode is {mode:04o}; expected 0600"
            )
        if info.st_uid != spec.expected_owner_uid:
            raise ControllerInstanceLockError(
                "controller lock owner UID does not match expected service identity"
            )

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {
                errno.EACCES,
                errno.EAGAIN,
                getattr(errno, "EWOULDBLOCK", errno.EAGAIN),
            }:
                raise ControllerInstanceBusyError(
                    "another VPN-GATE controller instance is running"
                ) from exc
            raise ControllerInstanceLockError(
                f"cannot acquire controller instance lock: {exc}"
            ) from exc

        return ControllerInstanceLock(spec, fd)
    except Exception:
        os.close(fd)
        raise


def _ensure_runtime_directory(spec: InstanceLockSpec) -> None:
    path = spec.runtime_directory
    try:
        info = path.lstat()
    except FileNotFoundError:
        try:
            os.mkdir(path, 0o700)
        except OSError as exc:
            raise ControllerInstanceLockError(
                f"cannot create runtime directory {path}: {exc}"
            ) from exc
        try:
            info = path.lstat()
        except OSError as exc:
            raise ControllerInstanceLockError(
                f"cannot verify created runtime directory {path}: {exc}"
            ) from exc
    except OSError as exc:
        raise ControllerInstanceLockError(
            f"cannot inspect runtime directory {path}: {exc}"
        ) from exc

    if stat.S_ISLNK(info.st_mode):
        raise ControllerInstanceLockError(
            f"runtime directory {path} must not be a symlink"
        )
    if not stat.S_ISDIR(info.st_mode):
        raise ControllerInstanceLockError(
            f"runtime path {path} is not a directory"
        )
    mode = stat.S_IMODE(info.st_mode)
    if mode != 0o700:
        raise ControllerInstanceLockError(
            f"runtime directory mode is {mode:04o}; expected 0700"
        )
    if info.st_uid != spec.expected_owner_uid:
        raise ControllerInstanceLockError(
            "runtime directory owner UID does not match expected service identity"
        )
