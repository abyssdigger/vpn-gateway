"""Release-1 control/timer realization of A.011 ProtectiveModeManager.

Architecture: A.011 ProtectiveModeManager.

The Unix socket is a replaceable deployment mechanism. Protective-mode semantics and
source-scoped state remain owned by ProtectiveModeManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import json
from pathlib import Path
import re
import socket
import stat
from threading import Event, RLock, Thread
from time import monotonic
from typing import Callable, Mapping

from .operational_log import OperationalLogAdapter, OperationalLogLevel
from .protective_mode_manager import (
    ProtectiveModeActionResult,
    ProtectiveModeManager,
    ProtectiveModeProjection,
    ProtectiveModeStatus,
)
from .protective_payload_gate import ProtectivePayloadGateDriver


LOG_TAG = "prot"
DEFAULT_CONTROL_PATH = Path("/run/vpn-gate-alpha/control.sock")
_MAX_REQUEST_BYTES = 4096
_SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


class ProtectiveModeControlError(RuntimeError):
    pass


@dataclass(slots=True)
class ProtectiveModeControlService:
    """Serialize operator control with finite-cadence A.011 reconciliation."""

    manager: ProtectiveModeManager
    driver: ProtectivePayloadGateDriver
    boundary_interface: str
    normal_release_confirmed: Callable[[], bool]
    normal_operation_lock: RLock
    socket_path: Path = DEFAULT_CONTROL_PATH
    audit_interval_seconds: float = 1.0
    logger: OperationalLogAdapter | None = None
    _stop: Event = field(default_factory=Event, init=False, repr=False)
    _control_thread: Thread | None = field(default=None, init=False, repr=False)
    _audit_thread: Thread | None = field(default=None, init=False, repr=False)
    _server: socket.socket | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.manager, ProtectiveModeManager):
            raise ValueError("manager must be ProtectiveModeManager")
        if not isinstance(self.boundary_interface, str) or not self.boundary_interface:
            raise ValueError("boundary_interface must be non-empty text")
        if not callable(self.normal_release_confirmed):
            raise ValueError("normal_release_confirmed must be callable")
        if not isinstance(self.socket_path, Path):
            raise ValueError("socket_path must be pathlib.Path")
        if (
            not isinstance(self.audit_interval_seconds, (int, float))
            or isinstance(self.audit_interval_seconds, bool)
            or self.audit_interval_seconds <= 0
        ):
            raise ValueError("audit_interval_seconds must be positive")
        if self.logger is not None and not isinstance(
            self.logger, OperationalLogAdapter
        ):
            raise ValueError("logger must be OperationalLogAdapter or None")

    def start(self) -> None:
        if (
            self._control_thread is not None
            and self._control_thread.is_alive()
        ) or (
            self._audit_thread is not None
            and self._audit_thread.is_alive()
        ):
            raise ProtectiveModeControlError(
                "protective-mode control service is already running"
            )

        # Runtime composition calls this only after ordinary desired state has
        # already been confirmed. Freshly reconcile the reserved lower gate to
        # inactive before exposing operator control, so current_state cannot
        # report inactive over stale owned containment.
        initial = self.manager.confirm_inactive(
            self.boundary_interface,
            normal_release_confirmed=True,
            driver=self.driver,
        )
        if not initial.confirmed_inactive:
            raise ProtectiveModeControlError(
                initial.projection.diagnostic
                or "initial protective inactive state is not confirmed"
            )

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            mode = self.socket_path.lstat().st_mode
            if not stat.S_ISSOCK(mode):
                raise ProtectiveModeControlError(
                    f"refusing to replace non-socket control path {self.socket_path}"
                )
            self.socket_path.unlink()

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(str(self.socket_path))
            self.socket_path.chmod(0o600)
            server.listen(8)
        except Exception:
            server.close()
            self.socket_path.unlink(missing_ok=True)
            raise

        self._server = server
        self._stop.clear()
        self._control_thread = Thread(
            target=self._serve,
            name="vpn-gate-protective-control",
            daemon=True,
        )
        self._audit_thread = Thread(
            target=self._audit_loop,
            name="vpn-gate-protective-audit",
            daemon=True,
        )
        self._control_thread.start()
        self._audit_thread.start()
        self._emit(
            OperationalLogLevel.INFO,
            "control_ready",
            socket=str(self.socket_path),
        )

    def stop(self) -> None:
        self._stop.set()
        server = self._server
        if server is not None:
            try:
                server.close()
            except OSError:
                pass
        for thread in (self._control_thread, self._audit_thread):
            if thread is not None and thread.is_alive():
                thread.join(
                    timeout=max(1.0, self.audit_interval_seconds * 2.0)
                )
        self._control_thread = None
        self._audit_thread = None
        self._server = None
        self.socket_path.unlink(missing_ok=True)

    def _serve(self) -> None:
        server = self._server
        assert server is not None
        server.settimeout(0.25)

        while not self._stop.is_set():
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            except OSError as exc:
                if self._stop.is_set():
                    break
                self._emit(
                    OperationalLogLevel.ERROR,
                    "control_accept_failed",
                    diagnostic=f"{type(exc).__name__}: {exc}",
                )
                continue

            # A malformed/abandoned root-side request must not hold the control
            # worker forever. Periodic safety audit is independent below.
            connection.settimeout(max(1.0, self.audit_interval_seconds * 2.0))
            try:
                self._handle_connection(connection)
            except Exception as exc:
                self._emit(
                    OperationalLogLevel.ERROR,
                    "control_connection_failed",
                    diagnostic=f"{type(exc).__name__}: {exc}",
                )

    def _audit_loop(self) -> None:
        while not self._stop.wait(self.audit_interval_seconds):
            try:
                self._audit_once()
            except Exception as exc:
                self._emit(
                    OperationalLogLevel.ERROR,
                    "audit_worker_failed",
                    diagnostic=f"{type(exc).__name__}: {exc}",
                )

    def _handle_connection(self, connection: socket.socket) -> None:
        with connection:
            try:
                request = _read_request(connection)
                response = self._dispatch(request)
            except Exception as exc:
                self._emit(
                    OperationalLogLevel.WARNING,
                    "control_request_failed",
                    diagnostic=f"{type(exc).__name__}: {exc}",
                )
                response = {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "protective": _projection_payload(
                        self.manager.current_state()
                    ),
                }
            connection.sendall(
                (json.dumps(response, sort_keys=True) + "\n").encode("utf-8")
            )

    def _dispatch(self, request: Mapping[str, object]) -> dict[str, object]:
        action = request.get("action")
        if action == "status":
            return {
                "ok": True,
                "protective": _projection_payload(
                    self.manager.current_state()
                ),
            }

        source = request.get("source", "operator")
        if not isinstance(source, str) or not _SOURCE_PATTERN.fullmatch(source):
            raise ValueError(
                "source must match [A-Za-z0-9_.:-]{1,64}"
            )

        before = self.manager.current_state()
        if action == "active":
            result = self.manager.request_active(
                source,
                self.boundary_interface,
                self.driver,
            )
            ok = result.confirmed_active
        elif action == "inactive":
            with self.normal_operation_lock:
                normal_ready = self._normal_release_ready()
                result = self.manager.request_inactive(
                    source,
                    self.boundary_interface,
                    normal_release_confirmed=normal_ready,
                    driver=self.driver,
                )
            ok = result.confirmed_inactive
        else:
            raise ValueError("action must be status, active or inactive")

        self._emit_transition(before, result.projection, f"request_{action}")
        return _action_payload(ok, result)

    def _audit_once(self) -> None:
        before = self.manager.current_state()
        if (
            before.status is ProtectiveModeStatus.INACTIVE
            and not before.request_sources
        ):
            return

        try:
            if before.request_sources:
                result = self.manager.reconcile_once(
                    self.boundary_interface,
                    normal_release_confirmed=False,
                    driver=self.driver,
                )
            else:
                with self.normal_operation_lock:
                    normal_ready = self._normal_release_ready()
                    result = self.manager.reconcile_once(
                        self.boundary_interface,
                        normal_release_confirmed=normal_ready,
                        driver=self.driver,
                    )
        except Exception as exc:
            self._emit(
                OperationalLogLevel.ERROR,
                "audit_failed",
                diagnostic=f"{type(exc).__name__}: {exc}",
            )
            return

        self._emit_transition(before, result.projection, "audit")

    def _normal_release_ready(self) -> bool:
        try:
            return bool(self.normal_release_confirmed())
        except Exception as exc:
            self._emit(
                OperationalLogLevel.ERROR,
                "normal_release_check_failed",
                diagnostic=f"{type(exc).__name__}: {exc}",
            )
            return False

    def _emit_transition(
        self,
        previous: ProtectiveModeProjection,
        current: ProtectiveModeProjection,
        event: str,
    ) -> None:
        if previous == current:
            return
        level = (
            OperationalLogLevel.ERROR
            if current.status is ProtectiveModeStatus.PROBLEM
            else OperationalLogLevel.INFO
        )
        self._emit(
            level,
            event,
            status=current.status.value,
            sources=",".join(sorted(current.request_sources)) or "-",
            diagnostic=current.diagnostic,
        )

    def _emit(self, level, event, **context) -> None:
        if self.logger is None:
            return
        self.logger.emit(level, LOG_TAG, event, **context)


def _projection_payload(
    projection: ProtectiveModeProjection,
) -> dict[str, object]:
    return {
        "status": projection.status.value,
        "request_sources": sorted(projection.request_sources),
        "diagnostic": projection.diagnostic,
    }


def _action_payload(
    ok: bool,
    result: ProtectiveModeActionResult,
) -> dict[str, object]:
    return {
        "ok": ok,
        "action_status": result.action_status.value,
        "protective": _projection_payload(result.projection),
    }


def _read_request(connection: socket.socket) -> Mapping[str, object]:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = connection.recv(1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_REQUEST_BYTES:
            raise ValueError("control request is too large")
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    raw = b"".join(chunks)
    line = raw.split(b"\n", 1)[0]
    if not line:
        raise ValueError("control request is empty")
    decoded = json.loads(line.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("control request must be a JSON object")
    return decoded


def request_protective_control(
    socket_path: Path,
    action: str,
    *,
    source: str = "operator",
) -> dict[str, object]:
    if not isinstance(socket_path, Path):
        raise ValueError("socket_path must be pathlib.Path")
    if action not in {"status", "active", "inactive"}:
        raise ValueError("unsupported protective action")
    request: dict[str, object] = {"action": action}
    if action != "status":
        if not isinstance(source, str) or not _SOURCE_PATTERN.fullmatch(source):
            raise ValueError(
                "source must match [A-Za-z0-9_.:-]{1,64}"
            )
        request["source"] = source

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.sendall(
            (json.dumps(request, sort_keys=True) + "\n").encode("utf-8")
        )
        client.shutdown(socket.SHUT_WR)
        response = _read_request(client)
    return dict(response)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="vpn-gate-control")
    sub = parser.add_subparsers(dest="area", required=True)
    protective = sub.add_parser("protective")
    protective.add_argument("operation", choices=("status", "enter", "leave"))
    protective.add_argument("--source", default="operator")
    protective.add_argument(
        "--socket",
        type=Path,
        default=DEFAULT_CONTROL_PATH,
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    action = {
        "status": "status",
        "enter": "active",
        "leave": "inactive",
    }[args.operation]
    try:
        response = request_protective_control(
            args.socket,
            action,
            source=args.source,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(response, sort_keys=True))
    return 0 if response.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
