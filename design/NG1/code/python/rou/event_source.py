from __future__ import annotations

import os
import selectors
import subprocess
from typing import Callable


class EventSourceError(RuntimeError):
    pass


PopenFactory = Callable[..., subprocess.Popen]
SelectorFactory = Callable[[], selectors.BaseSelector]


class IpMonitorWakeupSource:
    """RTNETLINK wakeup source backed by iproute2 `ip monitor`.

    Event text is deliberately opaque. Any readable monitor output only wakes the runtime;
    the Planner always makes decisions from a separately collected fresh snapshot.

    The monitor covers link/address/route/rule changes. Periodic runtime audits remain
    mandatory because sysctl and iptables mutations are not RTNETLINK events.
    """

    def __init__(
        self,
        namespace: str,
        *,
        popen_factory: PopenFactory = subprocess.Popen,
        selector_factory: SelectorFactory = selectors.DefaultSelector,
    ):
        if not namespace:
            raise ValueError("namespace must be non-empty")
        self._namespace = namespace
        self._popen_factory = popen_factory
        self._selector_factory = selector_factory
        self._process: subprocess.Popen | None = None
        self._selector: selectors.BaseSelector | None = None

    def _start(self) -> None:
        if self._process is not None:
            return

        argv = (
            "ip",
            "netns",
            "exec",
            self._namespace,
            "ip",
            "monitor",
            "link",
            "address",
            "route",
            "rule",
        )
        try:
            process = self._popen_factory(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                close_fds=True,
            )
        except OSError as exc:
            raise EventSourceError(
                f"failed to start ip monitor: {exc}"
            ) from exc

        if process.stdout is None:
            process.terminate()
            raise EventSourceError("ip monitor stdout pipe was not created")

        os.set_blocking(process.stdout.fileno(), False)
        selector = self._selector_factory()
        selector.register(process.stdout, selectors.EVENT_READ)

        self._process = process
        self._selector = selector

    def _exit_error(self) -> EventSourceError:
        process = self._process
        if process is None:
            return EventSourceError("ip monitor is not running")
        returncode = process.poll()
        stderr = b""
        if returncode is not None and process.stderr is not None:
            try:
                stderr = process.stderr.read() or b""
            except OSError:
                stderr = b""
        detail = stderr.decode("utf-8", errors="replace").strip()
        if detail:
            return EventSourceError(
                f"ip monitor exited with return code {returncode}: {detail}"
            )
        return EventSourceError(
            f"ip monitor exited with return code {returncode}"
        )

    def wait(self, timeout: float | None) -> bool:
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative or None")

        self._start()
        assert self._process is not None
        assert self._selector is not None
        assert self._process.stdout is not None

        if self._process.poll() is not None:
            raise self._exit_error()

        events = self._selector.select(timeout)
        if not events:
            if self._process.poll() is not None:
                raise self._exit_error()
            return False

        try:
            data = os.read(self._process.stdout.fileno(), 65536)
        except BlockingIOError:
            return False
        except OSError as exc:
            raise EventSourceError(
                f"failed reading ip monitor output: {exc}"
            ) from exc

        if data:
            return True

        raise self._exit_error()

    def close(self) -> None:
        selector = self._selector
        process = self._process
        self._selector = None
        self._process = None

        if selector is not None:
            selector.close()

        if process is None:
            return

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

    def __enter__(self) -> "IpMonitorWakeupSource":
        self._start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
