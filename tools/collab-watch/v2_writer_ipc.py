"""Staged one-shot local stream framing; no credential or process-isolation claim."""
from __future__ import annotations

from dataclasses import dataclass
import math
import socket
import struct
import threading
import time

from core import canonical, ident, strict_json
from v2_inputs import MAX_INPUT_BYTES
from v2_trusted_writer import LOCATOR_FIELDS, _closed_result, _rejected, _unknown

VERSION = 1
REQUEST_MAGIC = b"VPNG"
RESPONSE_MAGIC = b"VPNR"
REQUEST_HEADER = struct.Struct("!4sBBI")
RESPONSE_HEADER = struct.Struct("!4sBI")
CHUNK_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 4096


class ProtocolError(Exception):
    """Bounded local protocol failure; never transmit its diagnostic text."""


def _check(condition):
    if not condition:
        raise ProtocolError("writer IPC frame rejected")


def _shape(value, fields):
    return type(value) is dict and all(type(k) is str for k in value) and set(value) == fields


def _remaining(deadline):
    _check(type(deadline) in (int, float) and math.isfinite(deadline))
    remaining = deadline - time.monotonic()
    _check(remaining > 0)
    return remaining


def _receive(sock, size, deadline):
    sock.settimeout(_remaining(deadline))
    data, ancillary, flags, _ = sock.recvmsg(size, 0)
    _check(not ancillary and not flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC))
    _check(type(data) is bytes and len(data) <= size)
    return data


def _read_exact(sock, size, deadline):
    # Allocate incrementally from received bytes, not from untrusted header size.
    result = bytearray()
    while len(result) < size:
        chunk = _receive(sock, min(CHUNK_BYTES, size - len(result)), deadline)
        _check(bool(chunk))
        result.extend(chunk)
    return result


def _eof(sock, deadline):
    _check(_receive(sock, 1, deadline) == b"")
    _remaining(deadline)


def _send_exact(sock, data, deadline):
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        sock.settimeout(_remaining(deadline))
        sent = sock.send(view[offset:offset + CHUNK_BYTES])
        _check(type(sent) is int and 0 < sent <= min(CHUNK_BYTES, len(view) - offset))
        offset += sent


def read_request(sock, deadline):
    magic, version, flag, size = REQUEST_HEADER.unpack(_read_exact(sock, REQUEST_HEADER.size, deadline))
    _check(magic == REQUEST_MAGIC and version == VERSION and flag in (0, 1)
           and 0 < size <= MAX_INPUT_BYTES)
    raw = _read_exact(sock, size, deadline)
    _eof(sock, deadline)
    # The original is opaque here; 9a, not framing, owns semantic JSON admission.
    original = raw.decode("utf-8", errors="strict")
    _remaining(deadline)
    return {"original": original, "reconcile_only": bool(flag)}


def send_request(sock, request, deadline):
    _check(_shape(request, {"original", "reconcile_only"})
           and type(request["original"]) is str and type(request["reconcile_only"]) is bool
           and 0 < len(request["original"]) <= MAX_INPUT_BYTES)
    raw = request["original"].encode("utf-8", errors="strict")
    _check(0 < len(raw) <= MAX_INPUT_BYTES)
    _send_exact(sock, REQUEST_HEADER.pack(REQUEST_MAGIC, VERSION, int(request["reconcile_only"]), len(raw)), deadline)
    _send_exact(sock, raw, deadline)
    _remaining(deadline)
    sock.shutdown(socket.SHUT_WR)


def _result(value):
    """Reuse accepted 9a closed result union, not worker-supplied operation identity."""
    _check(type(value) is dict and all(type(k) is str for k in value))
    # The two wrapper-generated diagnostics are not delegate state/code pairs.
    for special in (_rejected(), _unknown()):
        if _shape(value, set(special)) and all(type(value[k]) is type(v) and value[k] == v
                                               for k, v in special.items()):
            return special
    # The trusted handler owns the actual operation/effect relationship. IPC
    # validates only the accepted result union without decoding worker JSON.
    for operation in LOCATOR_FIELDS:
        try:
            return _closed_result(value, operation)
        except Exception:
            continue
    raise ProtocolError("invalid writer result")


def _outcome(state):
    return {"state": state}


def _envelope(value):
    _check(type(value) is dict and type(value.get("state")) is str)
    state = value["state"]
    if state in ("INGRESS_REJECTED", "HANDOFF_UNCERTAIN"):
        _check(_shape(value, {"state"}))
        return _outcome(state)
    _check(state == "RESULT" and _shape(value, {"state", "result"}))
    return {"state": state, "result": _result(value["result"])}


def _encode_response(value):
    raw = canonical(_envelope(value)).encode("utf-8")
    _check(0 < len(raw) <= MAX_RESPONSE_BYTES)
    return raw


def _send_response(sock, value, deadline):
    raw = _encode_response(value)
    _send_exact(sock, RESPONSE_HEADER.pack(RESPONSE_MAGIC, VERSION, len(raw)), deadline)
    _send_exact(sock, raw, deadline)
    _remaining(deadline)
    sock.shutdown(socket.SHUT_WR)


def receive_response(sock, deadline):
    """No complete valid trusted response means uncertainty, never no-attempt."""
    try:
        magic, version, size = RESPONSE_HEADER.unpack(_read_exact(sock, RESPONSE_HEADER.size, deadline))
        _check(magic == RESPONSE_MAGIC and version == VERSION and 0 < size <= MAX_RESPONSE_BYTES)
        raw = _read_exact(sock, size, deadline)
        _eof(sock, deadline)
        text = raw.decode("utf-8", errors="strict")
        value = _envelope(strict_json(text))
        _check(canonical(value) == text)
        _remaining(deadline)
        return value
    except Exception:
        return _outcome("HANDOFF_UNCERTAIN")


def exchange(sock, request, *, deadline, response_deadline=None):
    """One-shot client; never infer server handoff status from a send failure."""
    try:
        send_request(sock, request, deadline)
        return receive_response(sock, deadline if response_deadline is None else response_deadline)
    except Exception:
        return _outcome("HANDOFF_UNCERTAIN")
    finally:
        sock.close()


@dataclass(frozen=True, slots=True)
class SessionBinding:
    """Trusted launcher metadata, never decoded from a worker frame."""
    role: str
    incarnation: str
    owner_generation: int
    session_id: str

    def __post_init__(self):
        _check(type(self.role) is str and self.role in ("GUARD", "SPEC", "BUILDER")
               and type(self.incarnation) is str and ident(self.incarnation)
               and type(self.owner_generation) is int and 0 < self.owner_generation < 2**63
               and type(self.session_id) is str and ident(self.session_id))


class WriterInvocation:
    """Trusted one-shot handler/session binding; endpoint possession delegates that session.

    No worker registration, peer-credential identity, authority or owner-status
    lookup. The handler is trusted and synchronous; this framing module cannot
    interrupt it. OS/process execution limits belong to 9b-B.
    """
    __slots__ = ("_session", "_handler", "_used", "_lock")

    def __init__(self, session, handler):
        _check(type(session) is SessionBinding and callable(handler))
        self._session = SessionBinding(session.role, session.incarnation, session.owner_generation, session.session_id)
        self._handler = handler
        self._used = False
        self._lock = threading.Lock()

    def serve(self, sock, *, deadline, response_deadline=None):
        """Own and close the server endpoint; return local outcome, not delivery proof."""
        with self._lock:
            _check(not self._used)
            self._used = True
        handed_off = False
        response_deadline = deadline if response_deadline is None else response_deadline
        try:
            try:
                _remaining(response_deadline)
                request = read_request(sock, deadline)
                _remaining(deadline)
                _remaining(response_deadline)
            except Exception:
                outcome = _outcome("INGRESS_REJECTED")
            else:
                # Trusted local handoff boundary: set before attempting handler entry.
                handed_off = True
                try:
                    result = self._handler(request, self._session)
                    outcome = {"state": "RESULT", "result": _result(result)}
                    _remaining(response_deadline)
                    _encode_response(outcome)
                except Exception:
                    outcome = _outcome("HANDOFF_UNCERTAIN")
            try:
                _send_response(sock, outcome, response_deadline)
            except Exception:
                if handed_off:
                    outcome = _outcome("HANDOFF_UNCERTAIN")
                # A local pre-handoff rejection remains local knowledge; a client
                # without a complete valid response still reports uncertainty.
            return outcome
        finally:
            sock.close()
