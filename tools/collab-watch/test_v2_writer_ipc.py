"""Local socketpair framing tests; no actual writer credential or transport."""
import os
import socket
import struct
import threading
import time
import tracemalloc
import unittest
from unittest.mock import patch

from core import canonical
from v2_inputs import MAX_INPUT_BYTES
import v2_writer_ipc as ipc

SESSION = ipc.SessionBinding('BUILDER', 'builder-test', 7, 'session-test')
RESULT = dict(state='VERIFIED', code='CANONICAL_RECEIPT_RECORDED', action_key='a'*64,
              receipt_sha256='b'*64, locator=dict(room=34, physical_ref='issue:34#issuecomment-5'))
SUCCESS = dict(state='RESULT', result=RESULT)
REJECT = dict(state='INGRESS_REJECTED')
UNKNOWN = dict(state='HANDOFF_UNCERTAIN')


def header(size, version=ipc.VERSION, flag=0, magic=ipc.REQUEST_MAGIC):
    return ipc.REQUEST_HEADER.pack(magic, version, flag, size)


class FakeRead:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.sizes = []

    def settimeout(self, value):
        assert value > 0

    def recvmsg(self, size, ancillary):
        self.sizes.append((size, ancillary))
        return next(self.replies)


class WriterIPCTests(unittest.TestCase):
    def setUp(self):
        self.seen = []

    def handler(self, request, session):
        self.seen.append((request, session))
        return RESULT

    def start_server(self, handler=None, *, session=SESSION, seconds=2):
        server, client = socket.socketpair()
        invocation = ipc.WriterInvocation(session, self.handler if handler is None else handler)
        local = []
        now = time.monotonic()
        deadline, response_deadline = now+seconds, now+3
        thread = threading.Thread(target=lambda: local.append(invocation.serve(
            server, deadline=deadline, response_deadline=response_deadline)), daemon=True)
        thread.start()
        self.addCleanup(client.close)
        self.addCleanup(server.close)
        return client, thread, local, deadline, response_deadline

    def finish(self, thread, local):
        thread.join(timeout=4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(local), 1)
        return local[0]

    def raw(self, sender, *, handler=None, seconds=2):
        client, thread, local, _, end = self.start_server(handler, seconds=seconds)
        client.settimeout(2)
        try:
            sender(client)
            client.shutdown(socket.SHUT_WR)
        except (BrokenPipeError, ConnectionResetError):
            pass
        result = ipc.receive_response(client, end)
        client.close()
        return result, self.finish(thread, local)

    def test_valid_small_and_multi_chunk(self):
        for original, reconcile in (('{"role":"GUARD"}', False), ('é'*70000, True)):
            request = dict(original=original, reconcile_only=reconcile)
            client, thread, local, deadline, end = self.start_server()
            result = ipc.exchange(client, request, deadline=deadline, response_deadline=end)
            self.assertEqual(result, SUCCESS)
            self.assertEqual(self.finish(thread, local), SUCCESS)
            self.assertEqual(self.seen[-1], (request, SESSION))
        self.assertEqual(len(self.seen), 2)

    def test_max_header_is_admitted_incrementally(self):
        fake = FakeRead([(header(MAX_INPUT_BYTES), [], 0, None), (b'', [], 0, None)])
        tracemalloc.start()
        try:
            with self.assertRaises(ipc.ProtocolError):
                ipc.read_request(fake, time.monotonic()+2)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(fake.sizes, [(ipc.REQUEST_HEADER.size, 0), (ipc.CHUNK_BYTES, 0)])
        self.assertLess(peak, 2*1024*1024)
        # Bound+1 fails before any body read.
        fake = FakeRead([(header(MAX_INPUT_BYTES+1), [], 0, None)])
        with self.assertRaises(ipc.ProtocolError):
            ipc.read_request(fake, time.monotonic()+2)
        self.assertEqual(fake.sizes, [(ipc.REQUEST_HEADER.size, 0)])

    def test_invalid_headers_truncation_and_utf8(self):
        wires = [header(0), header(MAX_INPUT_BYTES+1), header(1, version=2),
                 header(1, flag=2), header(1, magic=b'NOPE'), header(1)[:3],
                 header(2)+b'x', header(1)+b'\xff', header(1)+b'xy']
        for wire in wires:
            with self.subTest(wire=wire[:16]):
                self.assertEqual(self.raw(lambda s:s.sendall(wire)), (REJECT, REJECT))
        self.assertEqual(self.seen, [])

    def test_delayed_tail_never_hands_off(self):
        def send(s):
            s.sendall(header(1)+b'x')
            time.sleep(.06)
            s.sendall(b'y')
        self.assertEqual(self.raw(send), (REJECT, REJECT))
        self.assertEqual(self.seen, [])

    def test_complete_body_withheld_eof(self):
        client, thread, local, _, end = self.start_server(seconds=.2)
        client.sendall(header(1)+b'x')
        # Keep write direction open through the request deadline.
        self.assertEqual(ipc.receive_response(client, end), REJECT)
        self.assertEqual(self.finish(thread, local), REJECT)
        self.assertEqual(self.seen, [])

    def test_slow_drip_absolute_deadline(self):
        def send(s):
            for byte in header(1)+b'x':
                s.sendall(bytes([byte]))
                time.sleep(.045)
        self.assertEqual(self.raw(send, seconds=.18), (REJECT, REJECT))
        self.assertEqual(self.seen, [])

    def test_ancillary_on_header_body_and_tail(self):
        for where in ('header', 'body', 'tail'):
            def send(s):
                fd = os.open('/dev/null', os.O_RDONLY)
                try:
                    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack('i', fd))]
                    if where == 'header':
                        s.sendmsg([header(1)+b'x'], ancillary)
                    elif where == 'body':
                        s.sendall(header(1))
                        s.sendmsg([b'x'], ancillary)
                    else:
                        s.sendall(header(1)+b'x')
                        s.sendmsg([b'y'], ancillary)
                finally:
                    os.close(fd)
            with self.subTest(where=where):
                client, local = self.raw(send)
                self.assertEqual(local, REJECT)
                # Early rejection may close with unread bytes and reset the
                # client stream; only a complete response proves rejection.
                self.assertIn(client, (REJECT, UNKNOWN))
        self.assertEqual(self.seen, [])

    def test_synthetic_truncation_flags_and_ancillary(self):
        for anc, flags in (([], socket.MSG_TRUNC), ([], socket.MSG_CTRUNC),
                           ([(socket.SOL_SOCKET, socket.SCM_RIGHTS, b'fake')], 0)):
            fake = FakeRead([(header(1), anc, flags, None)])
            with self.assertRaises(ipc.ProtocolError):
                ipc.read_request(fake, time.monotonic()+2)

    def test_copied_endpoint_and_detached_binding(self):
        session = ipc.SessionBinding('BUILDER', 'original', 3, 'copy-test')
        client, thread, local, deadline, end = self.start_server(session=session)
        # Trusted bootstrap copies immutable data; mutation of caller object is not identity.
        object.__setattr__(session, 'role', 'GUARD')
        copy = client.dup()
        request = dict(original='{"role":"SPEC","owner_generation":999}', reconcile_only=False)
        self.assertEqual(ipc.exchange(copy, request, deadline=deadline, response_deadline=end), SUCCESS)
        self.assertEqual(self.finish(thread, local), SUCCESS)
        self.assertEqual(self.seen, [(request, ipc.SessionBinding('BUILDER', 'original', 3, 'copy-test'))])

    def test_bad_session_and_one_shot_invocation(self):
        for role, inc, gen, sid in [('OTHER','i',1,'s'),('BUILDER','',1,'s'),
                                     ('BUILDER','i',True,'s'),('BUILDER','i',0,'s'),
                                     ('BUILDER','i',1,'')]:
            with self.assertRaises(ipc.ProtocolError):
                ipc.SessionBinding(role,inc,gen,sid)
        server, client = socket.socketpair()
        try:
            client.shutdown(socket.SHUT_WR)
            invocation = ipc.WriterInvocation(SESSION,self.handler)
            self.assertEqual(invocation.serve(server,deadline=time.monotonic()+2),REJECT)
            self.assertEqual(ipc.receive_response(client,time.monotonic()+2),REJECT)
            with self.assertRaises(ipc.ProtocolError):
                invocation.serve(server,deadline=time.monotonic()+2)
            self.assertFalse(self.seen)
        finally:
            client.close();server.close()

    def test_handler_exception_or_malformed_is_uncertain(self):
        def fail(request, session):
            self.seen.append((request, session))
            raise RuntimeError('secret text')
        for handler in (fail, lambda *_: dict(RESULT, extra='secret'), lambda *_: None):
            self.assertEqual(self.raw(lambda s:s.sendall(header(1)+b'x'),handler=handler), (UNKNOWN,UNKNOWN))
        self.assertEqual(len(self.seen),1)

    def test_response_loss_after_handoff_is_uncertain(self):
        # The client endpoint is lost after submitting a complete frame. A
        # trusted handler still runs; local response write fails, not no-attempt.
        server, client = socket.socketpair()
        end=time.monotonic()+2
        ipc.send_request(client,dict(original='x',reconcile_only=False),end)
        client.close()
        self.assertEqual(ipc.WriterInvocation(SESSION,self.handler).serve(server,deadline=end), UNKNOWN)
        self.assertEqual(len(self.seen),1)

    def test_bad_or_absent_response_is_uncertain(self):
        raw = canonical(SUCCESS).encode()
        frame = ipc.RESPONSE_HEADER.pack(ipc.RESPONSE_MAGIC,ipc.VERSION,len(raw))+raw
        malformed = canonical(dict(state='INGRESS_REJECTED', extra='secret')).encode()
        wires = [b'', frame[:5], frame[:-1], frame+b'x',
                 ipc.RESPONSE_HEADER.pack(ipc.RESPONSE_MAGIC,ipc.VERSION,len(malformed))+malformed,
                 ipc.RESPONSE_HEADER.pack(ipc.RESPONSE_MAGIC,ipc.VERSION,ipc.MAX_RESPONSE_BYTES+1)]
        for wire in wires:
            server, client = socket.socketpair()
            with server, client:
                server.sendall(wire)
                server.shutdown(socket.SHUT_WR)
                self.assertEqual(ipc.receive_response(client,time.monotonic()+1),UNKNOWN)

    def test_invalid_response_deadline_never_hands_off(self):
        for bad in (time.monotonic()-1, float('inf'), float('nan')):
            with self.subTest(deadline=bad):
                server, client = socket.socketpair()
                with client:
                    end = time.monotonic()+2
                    ipc.send_request(client, dict(original='x', reconcile_only=False), end)
                    outcome = ipc.WriterInvocation(SESSION,self.handler).serve(
                        server, deadline=end, response_deadline=bad)
                    self.assertEqual(outcome, REJECT)
                    self.assertEqual(ipc.receive_response(client,time.monotonic()+1), UNKNOWN)
        self.assertFalse(self.seen)

    def test_request_consumes_response_deadline_before_handoff(self):
        server, client = socket.socketpair()
        with client:
            now = time.monotonic()
            end, response_end = now+2, now+.15
            client.sendall(header(1)+b'x')
            def complete():
                time.sleep(.25)
                client.shutdown(socket.SHUT_WR)
            thread = threading.Thread(target=complete)
            thread.start()
            outcome = ipc.WriterInvocation(SESSION,self.handler).serve(
                server, deadline=end, response_deadline=response_end)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(outcome, REJECT)
            self.assertEqual(ipc.receive_response(client,time.monotonic()+1), UNKNOWN)
            self.assertFalse(self.seen)

    def test_handler_overrun_not_no_attempt(self):
        server, client = socket.socketpair()
        with client:
            end=time.monotonic()+.3
            ipc.send_request(client,dict(original='x',reconcile_only=False),end)
            def slow(request,session):
                self.seen.append((request,session))
                time.sleep(.35)
                return RESULT
            result=ipc.WriterInvocation(SESSION,slow).serve(server,deadline=end)
            self.assertEqual(result,UNKNOWN)
            self.assertEqual(ipc.receive_response(client,time.monotonic()+1),UNKNOWN)
            self.assertEqual(len(self.seen),1)

    def test_bounded_response_send(self):
        class NoSend:
            def settimeout(self, value):
                self.timeout=value
            def send(self, data):
                raise TimeoutError('secret')
        with self.assertRaises(TimeoutError):
            ipc._send_response(NoSend(),SUCCESS,time.monotonic()+1)
