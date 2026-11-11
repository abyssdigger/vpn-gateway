from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import logging
import selectors
import socket
import threading
import time
from typing import Iterable

from .domain import ActiveConfig, TransportProtocol


LOG = logging.getLogger(__name__)


class PublicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublicationEndpoint:
    device_name: str
    protocol: TransportProtocol
    listen_address: IPv4Address
    external_port: int
    source_address: IPv4Address
    target_address: IPv4Address
    target_port: int

    def __post_init__(self) -> None:
        for label, port in (
            ("external_port", self.external_port),
            ("target_port", self.target_port),
        ):
            if not 1 <= port <= 65535:
                raise ValueError(f"{label} must be 1..65535")


def compile_publication_endpoints(
    config: ActiveConfig,
    *,
    listen_address: IPv4Address,
    source_address: IPv4Address,
    target_address: IPv4Address,
) -> tuple[PublicationEndpoint, ...]:
    """Expand active Device publication ranges into concrete socket endpoints."""

    endpoints: list[PublicationEndpoint] = []
    for device_name in sorted(config.active_device_names):
        device = config.devices[device_name]
        for publication in device.publications:
            for offset in range(publication.external.size):
                endpoints.append(
                    PublicationEndpoint(
                        device_name=device_name,
                        protocol=publication.protocol,
                        listen_address=listen_address,
                        external_port=publication.external.start + offset,
                        source_address=source_address,
                        target_address=target_address,
                        target_port=publication.internal.start + offset,
                    )
                )
    return tuple(endpoints)


class _Worker:
    def __init__(
        self,
        endpoint: PublicationEndpoint,
        external: socket.socket,
        stop: threading.Event,
    ):
        self.endpoint = endpoint
        self.external = external
        self.stop = stop
        self.error: BaseException | None = None
        self.thread = threading.Thread(
            target=self._run_guarded,
            name=(
                f"rou-pub-{endpoint.protocol.value}-"
                f"{endpoint.external_port}"
            ),
            daemon=True,
        )

    def _run_guarded(self) -> None:
        try:
            self.run()
        except BaseException as exc:
            if not self.stop.is_set():
                self.error = exc
                LOG.exception(
                    "publication worker failed device=%s protocol=%s port=%d",
                    self.endpoint.device_name,
                    self.endpoint.protocol.value,
                    self.endpoint.external_port,
                )

    def run(self) -> None:
        raise NotImplementedError

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        try:
            self.external.close()
        except OSError:
            pass

    def join(self, timeout: float) -> None:
        self.thread.join(timeout)


class _TcpWorker(_Worker):
    def __init__(
        self,
        endpoint: PublicationEndpoint,
        external: socket.socket,
        stop: threading.Event,
    ):
        super().__init__(endpoint, external, stop)
        self._sessions: set[socket.socket] = set()
        self._sessions_lock = threading.Lock()

    def _track(self, sock: socket.socket) -> None:
        with self._sessions_lock:
            self._sessions.add(sock)

    def _untrack(self, sock: socket.socket) -> None:
        with self._sessions_lock:
            self._sessions.discard(sock)

    @staticmethod
    def _pump(src: socket.socket, dst: socket.socket) -> None:
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def _session(self, client: socket.socket) -> None:
        upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._track(client)
        self._track(upstream)
        try:
            upstream.settimeout(10)
            upstream.connect(
                (
                    str(self.endpoint.target_address),
                    self.endpoint.target_port,
                )
            )
            upstream.settimeout(None)
            left = threading.Thread(
                target=self._pump,
                args=(client, upstream),
                daemon=True,
            )
            right = threading.Thread(
                target=self._pump,
                args=(upstream, client),
                daemon=True,
            )
            left.start()
            right.start()
            left.join()
            right.join()
        except OSError:
            LOG.debug(
                "publication TCP session failed device=%s external_port=%d",
                self.endpoint.device_name,
                self.endpoint.external_port,
                exc_info=True,
            )
        finally:
            for sock in (client, upstream):
                self._untrack(sock)
                try:
                    sock.close()
                except OSError:
                    pass

    def run(self) -> None:
        self.external.settimeout(0.5)
        while not self.stop.is_set():
            try:
                client, _peer = self.external.accept()
            except socket.timeout:
                continue
            except OSError:
                if self.stop.is_set():
                    return
                raise
            threading.Thread(
                target=self._session,
                args=(client,),
                daemon=True,
            ).start()

    def close(self) -> None:
        super().close()
        with self._sessions_lock:
            sessions = tuple(self._sessions)
        for sock in sessions:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass


@dataclass
class _UdpAssociation:
    sock: socket.socket
    peer: tuple[str, int]
    last_seen: float


class _UdpWorker(_Worker):
    def __init__(
        self,
        endpoint: PublicationEndpoint,
        external: socket.socket,
        stop: threading.Event,
        *,
        idle_seconds: float,
    ):
        super().__init__(endpoint, external, stop)
        self.idle_seconds = idle_seconds
        self._selector: selectors.BaseSelector | None = None
        self._associations: dict[tuple[str, int], _UdpAssociation] = {}

    def _create_association(
        self,
        selector: selectors.BaseSelector,
        peer: tuple[str, int],
        now: float,
    ) -> _UdpAssociation:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((str(self.endpoint.source_address), 0))
        sock.connect(
            (
                str(self.endpoint.target_address),
                self.endpoint.target_port,
            )
        )
        sock.setblocking(False)
        association = _UdpAssociation(sock, peer, now)
        self._associations[peer] = association
        selector.register(sock, selectors.EVENT_READ, association)
        return association

    def _drop_association(
        self,
        selector: selectors.BaseSelector,
        association: _UdpAssociation,
    ) -> None:
        self._associations.pop(association.peer, None)
        try:
            selector.unregister(association.sock)
        except Exception:
            pass
        association.sock.close()

    def _expire(
        self,
        selector: selectors.BaseSelector,
        now: float,
    ) -> None:
        for association in tuple(self._associations.values()):
            if now - association.last_seen >= self.idle_seconds:
                self._drop_association(selector, association)

    def run(self) -> None:
        self.external.setblocking(False)
        selector = selectors.DefaultSelector()
        self._selector = selector
        selector.register(self.external, selectors.EVENT_READ, None)
        try:
            while not self.stop.is_set():
                events = selector.select(timeout=min(1.0, self.idle_seconds))
                now = time.monotonic()
                for key, _mask in events:
                    if key.data is None:
                        try:
                            data, peer = self.external.recvfrom(65535)
                        except OSError:
                            if self.stop.is_set():
                                return
                            raise
                        association = self._associations.get(peer)
                        if association is None:
                            association = self._create_association(
                                selector,
                                peer,
                                now,
                            )
                        association.last_seen = now
                        association.sock.send(data)
                    else:
                        association = key.data
                        try:
                            data = association.sock.recv(65535)
                        except OSError:
                            self._drop_association(selector, association)
                            continue
                        association.last_seen = now
                        self.external.sendto(data, association.peer)
                self._expire(selector, now)
        finally:
            for association in tuple(self._associations.values()):
                self._drop_association(selector, association)
            try:
                selector.unregister(self.external)
            except Exception:
                pass
            selector.close()
            self._selector = None

    def close(self) -> None:
        super().close()
        selector = self._selector
        if selector is not None:
            # Closing association sockets makes any active select wake promptly.
            for association in tuple(self._associations.values()):
                try:
                    association.sock.close()
                except OSError:
                    pass


class PublicationSupervisor:
    """Own all active host-side publication sockets and relay workers."""

    def __init__(
        self,
        endpoints: Iterable[PublicationEndpoint],
        *,
        udp_idle_seconds: float = 600.0,
    ):
        if udp_idle_seconds <= 0:
            raise ValueError("udp_idle_seconds must be positive")
        self.endpoints = tuple(endpoints)
        self.udp_idle_seconds = udp_idle_seconds
        self._stop = threading.Event()
        self._workers: list[_Worker] = []
        self._started = False

    @staticmethod
    def _bind(endpoint: PublicationEndpoint) -> socket.socket:
        sock_type = (
            socket.SOCK_STREAM
            if endpoint.protocol is TransportProtocol.TCP
            else socket.SOCK_DGRAM
        )
        sock = socket.socket(socket.AF_INET, sock_type)
        try:
            if endpoint.protocol is TransportProtocol.TCP:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(
                (
                    str(endpoint.listen_address),
                    endpoint.external_port,
                )
            )
            if endpoint.protocol is TransportProtocol.TCP:
                sock.listen(128)
            return sock
        except Exception:
            sock.close()
            raise

    def start(self) -> None:
        if self._started:
            raise PublicationError("publication supervisor already started")

        workers: list[_Worker] = []
        try:
            for endpoint in self.endpoints:
                external = self._bind(endpoint)
                if endpoint.protocol is TransportProtocol.TCP:
                    worker: _Worker = _TcpWorker(
                        endpoint,
                        external,
                        self._stop,
                    )
                else:
                    worker = _UdpWorker(
                        endpoint,
                        external,
                        self._stop,
                        idle_seconds=self.udp_idle_seconds,
                    )
                workers.append(worker)
        except OSError as exc:
            for worker in workers:
                worker.close()
            raise PublicationError(
                f"cannot bind publication socket: {exc}"
            ) from exc

        self._workers = workers
        self._started = True
        for worker in self._workers:
            worker.start()

    def check_health(self) -> None:
        if not self._started:
            raise PublicationError("publication supervisor is not started")
        for worker in self._workers:
            if worker.error is not None:
                raise PublicationError(
                    "publication worker failed: "
                    f"device={worker.endpoint.device_name} "
                    f"protocol={worker.endpoint.protocol.value} "
                    f"port={worker.endpoint.external_port}: "
                    f"{worker.error}"
                )
            if not worker.thread.is_alive():
                raise PublicationError(
                    "publication worker stopped unexpectedly: "
                    f"device={worker.endpoint.device_name} "
                    f"protocol={worker.endpoint.protocol.value} "
                    f"port={worker.endpoint.external_port}"
                )

    def close(self) -> None:
        if not self._started:
            return
        self._stop.set()
        for worker in self._workers:
            worker.close()
        for worker in self._workers:
            worker.join(3.0)
        self._workers = []
        self._started = False

    def __enter__(self) -> "PublicationSupervisor":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
