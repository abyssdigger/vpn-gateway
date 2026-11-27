"""Fixed C-B2 synthetic-only child fixture. No real credential or network route.

This is staged integration machinery, not a production transport or authority
implementation. The independent local counter represents synthetic remote
effects across actual child crashes.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import hashlib
import os
import socket
import struct
import time
from unittest.mock import patch

from core import canonical, require, strict_json
from v2_attempts import open_store
from v2_inputs import open_inputs
from v2_owner import open_owner
from v2_runtime_state import open_state
from v2_trusted_writer import TrustedWriter
from v2_writer_coordinator import Coordinator, _inode
from v2_writer_spool import Spool

MAX_FIXTURE = 2 * 1024 * 1024
COUNTER = struct.Struct(">Q")


def _open(pin, flags):
    pin.check()
    fd = os.open(pin.path, flags | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        require(_inode(os.fstat(fd)) == pin.inode, "synthetic fixture pin mismatch")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _fixture(spec):
    fd = _open(spec.data, os.O_RDONLY)
    try:
        raw = bytearray()
        while len(raw) <= MAX_FIXTURE:
            block = os.read(fd, min(65536, MAX_FIXTURE + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        require(0 < len(raw) <= MAX_FIXTURE and hashlib.sha256(raw).hexdigest() == spec.data_sha256,
                "synthetic fixture rejected")
        text = raw.decode("utf-8")
        data = strict_json(text)
        require(canonical(data) == text and type(data) is dict
                and set(data) == {"before", "after", "actor", "response"}
                and type(data["before"]) is dict and type(data["after"]) is dict
                and type(data["actor"]) is int and data["actor"] > 0
                and type(data["response"]) is dict, "invalid synthetic fixture")
        spec.data.check()
        return data
    finally:
        os.close(fd)


def _read_counter(fd):
    raw = os.pread(fd, COUNTER.size + 1, 0)
    require(len(raw) == COUNTER.size, "invalid synthetic counter")
    return COUNTER.unpack(raw)[0]


def _count(pin, send=False):
    fd = _open(pin, os.O_RDWR if send else os.O_RDONLY)
    try:
        n = _read_counter(fd)
        if send:
            require(n < 2**32, "synthetic counter exhausted")
            require(os.pwrite(fd, COUNTER.pack(n + 1), 0) == COUNTER.size,
                    "synthetic counter write failed")
            os.fsync(fd)
        pin.check()
        return n
    finally:
        os.close(fd)


def _deny(*args, **kwargs):
    raise RuntimeError("synthetic-only transport: network disabled")


@contextmanager
def composition(route, recovery, deadline):
    """Construct actual accepted stores/writer/coordinator in the invoking child."""
    # Import fixed reviewed fixture classes; no worker-selected adapter/import.
    from test_v2_actuator import Remote, ReadOpener
    cfg, bindings = strict_json(route.config_json), strict_json(route.bindings_json)
    require(cfg["repository"] == "owner/repo" and cfg["journal_epoch"] == "v2-test",
            "synthetic test scope only")
    p = route.pins
    for pin in p.values() + (route.fixture.data, route.fixture.counter):
        pin.check()
    data = _fixture(route.fixture)
    require(data["actor"] == cfg["roles"][route.session.role]["actor_id"], "synthetic actor mismatch")
    remote = Remote(data["before"], data["after"], data["actor"], data["response"])
    # Observe counter only while actual invocation uses it; the initial value is
    # refreshed immediately before each read. Counter remains separate from spool.
    read = remote.read
    def read_current(req, timeout):
        remote.applied = _count(route.fixture.counter) > 0
        return read(req, timeout)
    remote.read = read_current
    remote.store_check = lambda: _count(route.fixture.counter, True)
    with ExitStack() as stack:
        owner = open_owner(p.owner.path, p.owner.store_id, cfg["repository"], cfg["journal_epoch"])
        stack.callback(owner.close)
        state = open_state(p.checkpoint.path, p.checkpoint.store_id, cfg["repository"], cfg["journal_epoch"])
        stack.callback(state.close)
        attempt = open_store(p.attempt.path, p.attempt.store_id)
        retention = open_inputs(p.input.path, p.input.store_id, p.attempt.store_id)
        stack.callback(retention.close)
        spool = Spool.open(p.spool.path, expected_inode=p.spool.inode, cfg=cfg, bindings=bindings,
                           runtime_model=route.runtime_model, session=route.session,
                           spool_id=p.spool.store_id, attempt_store_id=p.attempt.store_id,
                           input_store_id=p.input.store_id, quotas=route.quotas,
                           resource_policy=route.policy.identity())
        stack.callback(spool.close)
        writer = TrustedWriter(cfg, bindings, route.runtime_model, selected_role=route.session.role,
                               owner_store=owner, capability=route.capability, store=attempt,
                               retention=retention, runtime_state=state, authorize=lambda _: True,
                               read_token="synthetic-read-only", write_token="synthetic-write-only",
                               read_opener=ReadOpener(remote))
        coordinator = Coordinator(spool, writer, pins=p, session=route.session,
                                  resource_policy=route.policy.identity())
        stack.callback(coordinator.close)
        stack.enter_context(patch("v2_actuator._write_transport", return_value=remote))
        # Defensive standard-library transport denial; not an OS sandbox claim.
        stack.enter_context(patch.object(socket, "create_connection", _deny))
        stack.enter_context(patch.object(socket.socket, "connect", _deny))
        stack.enter_context(patch.object(socket.socket, "connect_ex", _deny))
        stack.enter_context(patch.object(socket, "getaddrinfo", _deny))
        stack.enter_context(patch("urllib.request.urlopen", _deny))
        if not recovery and route.fixture.fault in ("after_marker", "hold_marker"):
            mark = Spool.mark_initial
            def mark_fault(store, request_id, version):
                result = mark(store, request_id, version)
                if route.fixture.fault == "after_marker":
                    os._exit(23)
                # Fixed bounded test hold, useful only for actual-child
                # supervisor-loss evidence. The outer flock remains held.
                time.sleep(min(8, max(0, deadline-time.monotonic())))
                return result
            stack.enter_context(patch.object(Spool, "mark_initial", mark_fault))
        if not recovery and route.fixture.fault == "after_writer":
            def result_fault(store, request_id, version, execution, value):
                require(value["state"] == "VERIFIED", "synthetic writer did not verify")
                os._exit(24)
            stack.enter_context(patch.object(Spool, "persist_result", result_fault))
        yield coordinator
