from __future__ import annotations

from ipaddress import IPv4Address
from pathlib import Path
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.domain import (
    ActiveConfig,
    Device,
    Direction,
    NatMode,
    PortRange,
    Profile,
    Publication,
    TransportProtocol,
)
from rou.publication import (
    PublicationEndpoint,
    PublicationError,
    PublicationSupervisor,
    compile_publication_endpoints,
)


LOOPBACK = IPv4Address("127.0.0.1")


def free_port(sock_type: int) -> int:
    sock = socket.socket(socket.AF_INET, sock_type)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def start_tcp_echo(port: int):
    ready = threading.Event()
    stop = threading.Event()

    def run():
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(5)
        listener.settimeout(0.2)
        ready.set()
        try:
            while not stop.is_set():
                try:
                    client, _peer = listener.accept()
                except socket.timeout:
                    continue
                with client:
                    data = client.recv(65536)
                    if data:
                        client.sendall(data)
        finally:
            listener.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(2)
    return stop, thread


def start_udp_echo(port: int):
    ready = threading.Event()
    stop = threading.Event()

    def run():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", port))
        sock.settimeout(0.2)
        ready.set()
        try:
            while not stop.is_set():
                try:
                    data, peer = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                sock.sendto(data, peer)
        finally:
            sock.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(2)
    return stop, thread


def endpoint(protocol, external_port, target_port):
    return PublicationEndpoint(
        device_name="oc",
        protocol=protocol,
        listen_address=LOOPBACK,
        external_port=external_port,
        source_address=LOOPBACK,
        target_address=LOOPBACK,
        target_port=target_port,
    )


class PublicationTests(unittest.TestCase):
    def test_range_projection_is_positional_and_active_device_only(self):
        config = ActiveConfig(
            devices={
                "active": Device(
                    "active",
                    True,
                    nat=NatMode.NONE,
                    publications=(
                        Publication(
                            TransportProtocol.UDP,
                            PortRange(4000, 4002),
                            PortRange(5000, 5002),
                        ),
                    ),
                ),
                "inactive": Device(
                    "inactive",
                    True,
                    nat=NatMode.NONE,
                    publications=(
                        Publication(
                            TransportProtocol.TCP,
                            PortRange(6000, 6000),
                            PortRange(7000, 7000),
                        ),
                    ),
                ),
            },
            profiles={
                "corp": Profile(
                    "corp",
                    True,
                    Direction.OUTBOUND,
                    (),
                    ("active",),
                ),
            },
        )
        endpoints = compile_publication_endpoints(
            config,
            listen_address=LOOPBACK,
            source_address=LOOPBACK,
            target_address=LOOPBACK,
        )
        self.assertEqual(
            [
                (item.external_port, item.target_port)
                for item in endpoints
            ],
            [(4000, 5000), (4001, 5001), (4002, 5002)],
        )

    def test_tcp_relay_round_trip(self):
        target_port = free_port(socket.SOCK_STREAM)
        external_port = free_port(socket.SOCK_STREAM)
        stop, thread = start_tcp_echo(target_port)
        supervisor = PublicationSupervisor(
            (endpoint(TransportProtocol.TCP, external_port, target_port),)
        )
        try:
            supervisor.start()
            supervisor.check_health()
            with socket.create_connection(
                ("127.0.0.1", external_port),
                timeout=2,
            ) as client:
                client.sendall(b"hello")
                self.assertEqual(client.recv(5), b"hello")
            supervisor.check_health()
        finally:
            supervisor.close()
            stop.set()
            thread.join(2)

    def test_udp_relay_round_trip(self):
        target_port = free_port(socket.SOCK_DGRAM)
        external_port = free_port(socket.SOCK_DGRAM)
        stop, thread = start_udp_echo(target_port)
        supervisor = PublicationSupervisor(
            (endpoint(TransportProtocol.UDP, external_port, target_port),),
            udp_idle_seconds=1.0,
        )
        try:
            supervisor.start()
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(2)
            try:
                client.sendto(b"ping", ("127.0.0.1", external_port))
                data, _peer = client.recvfrom(65535)
                self.assertEqual(data, b"ping")
            finally:
                client.close()
            supervisor.check_health()
        finally:
            supervisor.close()
            stop.set()
            thread.join(2)

    def test_udp_target_absence_does_not_kill_publication_worker(self):
        target_port = free_port(socket.SOCK_DGRAM)
        external_port = free_port(socket.SOCK_DGRAM)
        supervisor = PublicationSupervisor(
            (endpoint(TransportProtocol.UDP, external_port, target_port),),
            udp_idle_seconds=1.0,
        )
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            supervisor.start()
            client.sendto(b"one", ("127.0.0.1", external_port))
            time.sleep(0.05)
            client.sendto(b"two", ("127.0.0.1", external_port))
            time.sleep(0.05)
            supervisor.check_health()
        finally:
            client.close()
            supervisor.close()

    def test_prebind_failure_rolls_back_already_bound_sockets(self):
        free_external = free_port(socket.SOCK_STREAM)
        occupied_port = free_port(socket.SOCK_STREAM)
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", occupied_port))
        occupied.listen(1)

        supervisor = PublicationSupervisor(
            (
                endpoint(TransportProtocol.TCP, free_external, free_external),
                endpoint(TransportProtocol.TCP, occupied_port, occupied_port),
            )
        )
        try:
            with self.assertRaises(PublicationError):
                supervisor.start()
        finally:
            supervisor.close()
            occupied.close()

        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", free_external))
        finally:
            probe.close()

    def test_supervisor_can_restart_after_close(self):
        port = free_port(socket.SOCK_DGRAM)
        target = free_port(socket.SOCK_DGRAM)
        supervisor = PublicationSupervisor(
            (endpoint(TransportProtocol.UDP, port, target),)
        )
        supervisor.start()
        supervisor.close()
        supervisor.start()
        try:
            supervisor.check_health()
        finally:
            supervisor.close()


if __name__ == "__main__":
    unittest.main()
