"""Offline transport and durable local state evidence; no live GitHub writes."""
import io
from email.message import Message
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from collab_watch import (
    API, PAGE_SIZE, Conflict, NoRedirect, acquire, fetch_page, fetch_room,
    observe_once, state_lock,
)
from test_core import CFG, row, op, snap


class Response:
    def __init__(self, url, rows, headers=None, status=200):
        self.url = url
        self.body = io.BytesIO(json.dumps(rows).encode())
        self.status = status
        self.headers = headers or {}

    def geturl(self):
        return self.url

    def read(self, amount):
        return self.body.read(amount)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AcquisitionTests(unittest.TestCase):
    def test_fixed_get_with_optional_token_and_no_followed_link(self):
        opener = Mock()
        def answer(req, timeout):
            self.assertEqual(req.get_method(), 'GET')
            self.assertEqual(req.full_url, f'{API}/repos/owner/repo/issues/33/comments?per_page=100&page=1')
            self.assertEqual(req.get_header('Authorization'), 'Bearer example-token')
            self.assertGreater(timeout, 0)
            return Response(req.full_url, [row(1, 'content')], {
                'Link': '<https://untrusted.example/anything>; rel="next"'
            })
        opener.open.side_effect = answer
        rows, more = fetch_page('owner/repo', 33, 1, opener, 'example-token')
        self.assertEqual(len(rows), 1)
        self.assertTrue(more)
        opener.open.assert_called_once()
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://untrusted.example'))

    def test_bad_http_or_bad_shape_fails_closed(self):
        opener = Mock()
        for exc in (HTTPError('https://api.github.com', 403, 'forbidden', None, None), URLError('down')):
            with self.subTest(exc=type(exc)), self.assertRaises(Conflict):
                opener.open.side_effect = exc
                fetch_page('owner/repo', 33, 1, opener, None)
        opener.open.side_effect = lambda req, timeout: Response(req.full_url, {'error': 'bad shape'})
        with self.assertRaises(Conflict):
            fetch_page('owner/repo', 33, 1, opener, None)
        opener.open.side_effect = lambda req, timeout: Response(req.full_url, [], status=206)
        with self.assertRaises(Conflict):
            fetch_page('owner/repo', 33, 1, opener, None)
        opener.open.side_effect = lambda req, timeout: Response(req.full_url, [], {'Content-Length': '100'})
        with self.assertRaises(Conflict):
            fetch_page('owner/repo', 33, 1, opener, None)
        opener.open.side_effect = lambda req, timeout: Response('https://untrusted.example', [])
        with self.assertRaises(Conflict):
            fetch_page('owner/repo', 33, 1, opener, None)

    def test_malformed_link_cannot_look_complete(self):
        opener = Mock()
        bad = ['<https://example/last>; rel="last", malformed rel="next"',
               '<https://example/1>; rel="next", <https://example/2>; rel="next"',
               '<https://example/last>; rel="last",',
               '<https://example/unknown>; rel="unknown"', '',
               '<https://example/last>; rel="last"\r\n',
               '<https://example/last<bad>; rel="last"',
               '<https://example/bad path>; rel="last"']
        for link in bad:
            with self.subTest(link=link), self.assertRaises(Conflict):
                opener.open.side_effect = lambda req, timeout: Response(req.full_url, [], {'Link': link})
                fetch_page('owner/repo', 33, 1, opener, None)
        opener.open.side_effect = lambda req, timeout: Response(req.full_url, [], {
            'Link': '<https://example/2>; rel="next", <https://example/3>; rel="last"'
        })
        self.assertEqual(fetch_page('owner/repo', 33, 1, opener, None), ([], True))
        headers = Message()
        headers['Link'] = '<https://example/3>; rel="last"'
        headers['Link'] = 'malformed rel="next"'
        opener.open.side_effect = lambda req, timeout: Response(req.full_url, [], headers)
        with self.assertRaises(Conflict):
            fetch_page('owner/repo', 33, 1, opener, None)

    def test_credential_diagnostics_do_not_echo_value(self):
        opener = Mock()
        for token in ('secret\nvalue', 'secret\rvalue', 'secret value', 'x' * 4097):
            with self.subTest(length=len(token)), self.assertRaisesRegex(Conflict, '^invalid bearer credential format$'):
                fetch_page('owner/repo', 33, 1, opener, token)
        opener.open.assert_not_called()
        opener.open.side_effect = ValueError('secret-token')
        with self.assertRaises(Conflict) as raised:
            fetch_page('owner/repo', 33, 1, opener, 'secret-token')
        self.assertNotIn('secret-token', str(raised.exception))
        with patch('collab_watch.Request', side_effect=ValueError('secret-token')):
            with self.assertRaises(Conflict) as raised:
                fetch_page('owner/repo', 33, 1, opener, 'secret-token')
        self.assertNotIn('secret-token', str(raised.exception))

    def test_full_page_without_link_reads_extra_page(self):
        full = [row(i+1, 'body') for i in range(PAGE_SIZE)]
        with patch('collab_watch.fetch_page', side_effect=[(full, False), ([], False)]) as fetch:
            rows = fetch_room('owner/repo', 33, None, None)
        self.assertEqual(len(rows), PAGE_SIZE)
        self.assertEqual(fetch.call_count, 2)

    def test_page_overlap_and_short_next_page(self):
        with patch('collab_watch.fetch_page', side_effect=[([row(1, 'a'), row(2, 'b')], True), ([row(2, 'b'), row(3, 'c')], False)]):
            rows = fetch_room('owner/repo', 33, None, None)
        self.assertEqual([r['id'] for r in rows], [1, 2, 2, 3])

    def test_truncated_or_repeating_pagination_fails(self):
        with patch('collab_watch.fetch_page', return_value=([row(1, 'a')], True)):
            with self.assertRaisesRegex(Conflict, 'bound'):
                fetch_room('owner/repo', 33, None, None, page_limit=1)
            with self.assertRaisesRegex(Conflict, 'no progress'):
                fetch_room('owner/repo', 33, None, None, page_limit=3)
        with patch('collab_watch.fetch_page', return_value=([], True)), self.assertRaises(Conflict):
            fetch_room('owner/repo', 33, None, None)

    def test_acquisition_checks_all_rooms_twice_and_detects_drift(self):
        snapshots = snap([op()])
        def fetch(repo, room, *args):
            return snapshots[str(room)]
        with patch('collab_watch.fetch_room', side_effect=fetch) as f:
            self.assertEqual(acquire(CFG, opener=Mock()), snapshots)
            self.assertEqual(f.call_count, 6)
        reads = [snapshots[str(i)] for i in (33,34,35,33,34,35)]
        reads[3] = []
        with patch('collab_watch.fetch_room', side_effect=reads), self.assertRaisesRegex(Conflict, 'changed'):
            acquire(CFG, opener=Mock())


class StateTests(unittest.TestCase):
    def test_fixture_replay_restart_and_failed_acquisition_preserves_state(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            state, fixture = p/'state.json', p/'fixture.json'
            fixture.write_text(json.dumps(snap([op()])))
            projection = observe_once(CFG, state, fixture=fixture)
            self.assertEqual(projection['roles']['BUILDER']['state'], 'READY')
            original = state.read_bytes()
            second = observe_once(CFG, state, fixture=fixture)
            self.assertEqual(second['integrity'], 'prior observed comments matched')
            self.assertEqual(state.read_bytes(), original)
            # Deleted event (previously admitted) and partial room set fail.
            for bad in (snap([]), {'33': [op()]}):
                fixture.write_text(json.dumps(bad))
                with self.assertRaises(Conflict):
                    observe_once(CFG, state, fixture=fixture)
                self.assertEqual(state.read_bytes(), original)
            with patch('collab_watch.acquire', side_effect=Conflict('HTTP failed')), self.assertRaises(Conflict):
                observe_once(CFG, state)
            self.assertEqual(state.read_bytes(), original)
            self.assertEqual(state.stat().st_mode & 0o777, 0o600)

    def test_exclusive_state_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)/'state.json'
            with state_lock(state):
                with self.assertRaisesRegex(Conflict, 'locked'):
                    observe_once(CFG, state, fixture=Path(temp)/'missing')
            self.assertFalse(state.exists())

    def test_conflict_before_first_replay_creates_no_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            state, fixture = p/'state.json', p/'fixture.json'
            fixture.write_text(json.dumps(snap([row(100, 'not an event')])))
            with self.assertRaises(Conflict):
                observe_once(CFG, state, fixture=fixture)
            self.assertFalse(state.exists())


if __name__ == '__main__':
    unittest.main()
