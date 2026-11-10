#!/usr/bin/env python3
"""EXP-010 phase A: rootless UDP publication/relay smoke without netns."""

import queue
import socket
import sys
import threading
import time

PUBLISH = ("127.0.0.1", 15678)
INTERNAL = ("127.0.0.1", 17890)
SINK = ("127.0.0.1", 19900)
MESSAGE = b"exp010-local-smoke"

errors: queue.Queue[tuple[str, str]] = queue.Queue()
events: list[str] = []


def record(tag: str, text: str) -> None:
    events.append(f"{tag}: {text}")


def sink() -> None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        sock.bind(SINK)
        data, peer = sock.recvfrom(65535)
        record("SINK_RX", f"{peer} {data!r}")
        assert data == b"PAYLOAD:" + MESSAGE
        record("SINK_PASS", "ok")
    except Exception as exc:
        errors.put(("sink", repr(exc)))


def internal_listener() -> None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        sock.bind(INTERNAL)
        data, peer = sock.recvfrom(65535)
        record("INTERNAL_RX", f"{peer} {data!r}")
        assert data == MESSAGE

        out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        out.sendto(b"PAYLOAD:" + data, SINK)
        out.close()
        record("INTERNAL_TX", repr(b"PAYLOAD:" + data))

        sock.sendto(b"ACK:" + data, peer)
        record("INTERNAL_ACK", repr(b"ACK:" + data))
        record("INTERNAL_PASS", "ok")
    except Exception as exc:
        errors.put(("internal", repr(exc)))


def relay() -> None:
    try:
        external = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        external.settimeout(3)
        external.bind(PUBLISH)

        internal = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        internal.settimeout(3)
        internal.bind(("127.0.0.1", 0))

        data, client = external.recvfrom(65535)
        record("RELAY_RX", f"{client} {data!r}")

        internal.sendto(data, INTERNAL)
        record("RELAY_FWD", f"{internal.getsockname()} -> {INTERNAL}")

        reply, peer = internal.recvfrom(65535)
        record("RELAY_RETURN", f"{peer} {reply!r}")

        external.sendto(reply, client)
        record("RELAY_TX", f"{client} {reply!r}")
        record("RELAY_PASS", "ok")
    except Exception as exc:
        errors.put(("relay", repr(exc)))


threads = [
    threading.Thread(target=sink, daemon=True),
    threading.Thread(target=internal_listener, daemon=True),
    threading.Thread(target=relay, daemon=True),
]
for thread in threads:
    thread.start()

time.sleep(0.1)

try:
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(3)
    client.sendto(MESSAGE, PUBLISH)
    record("CLIENT_TX", repr(MESSAGE))
    reply, peer = client.recvfrom(65535)
    record("CLIENT_RX", f"{peer} {reply!r}")
    assert reply == b"ACK:" + MESSAGE
    record("CLIENT_PASS", "ok")
except Exception as exc:
    errors.put(("client", repr(exc)))

for thread in threads:
    thread.join(4)

while not errors.empty():
    print("ERROR", errors.get(), file=sys.stderr)

for event in events:
    print(event)

required = {"SINK_PASS", "INTERNAL_PASS", "RELAY_PASS", "CLIENT_PASS"}
observed = {event.split(":", 1)[0] for event in events}
ok = required <= observed and errors.empty()

print("OVERALL=" + ("PASS" if ok else "FAIL"))
raise SystemExit(0 if ok else 1)
