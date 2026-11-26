"""Offline v1 CLI/state and outgoing preflight regression."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from collab_watch import acquire, main, observe_once
from core import Conflict, canonical, digest
from journal import JOURNAL_MARKER, PROTOCOL, project_m
from preflight_m import preflight_journal_fact as journal_preview, preflight_signal as signal_preview
from test_journal import CFG, ack, frame, i, j, op, physical_ref, row, semantic, sig, snap, target


class M2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state.json'
        self.fixture = self.root / 'snapshot.json'
        self.config = self.root / 'config.json'
        self.cfg = copy.deepcopy(CFG)
        self.fact = i()
        self.receipt = ack(102, 'ack', 'BUILDER', target(self.fact))
        self.signal = sig(200, self.fact)
        self.snapshot = snap([op(), self.fact, self.receipt], [self.signal])

    def cli(self, expected=0):
        self.config.write_text(canonical(self.cfg))
        self.fixture.write_text(canonical(self.snapshot))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(['--once', '--config', str(self.config), '--state', str(self.state),
                         '--fixture', str(self.fixture)])
        self.assertEqual(code, expected, output.getvalue())
        return json.loads(output.getvalue())

    def test_fixture_cli_replay_consumed_signal_loss_rotation(self):
        self.cfg = json.loads(Path('fixtures/m1-config.json').read_text())
        self.snapshot = json.loads(Path('fixtures/m1-snapshot.json').read_text())
        p = self.cli()
        original = self.state.read_bytes()
        state = json.loads(original)
        self.assertEqual(set(state), {'protocol', 'semantic_config_hash', 'ledger'})
        self.assertEqual(state['protocol'], PROTOCOL)
        self.assertEqual(len(p['gc_candidates']), 1)
        self.assertEqual(semantic(self.cli()), semantic(p))
        self.snapshot['37'] = []
        self.assertEqual(semantic(self.cli()), semantic(p))
        self.cfg['signal_room'] = 38
        self.snapshot['38'] = self.snapshot.pop('37')
        self.assertEqual(semantic(self.cli()), semantic(p))
        self.assertEqual(original, self.state.read_bytes())

    def test_config_and_state_fail_closed(self):
        self.cli(); before = self.state.read_bytes(); cfg = copy.deepcopy(self.cfg)
        variants = [{'protocol': 'unknown'}, {'event_room': 33}, {'legacy_comments': []},
                    {'repository': 'other/repo'}, {'journal_epoch': 'm2'}, {'task_rooms': [39]},
                    {'roles': dict(cfg['roles'], GUARD={'actor_id': 1, 'incarnation': 'g2'})},
                    {'projectholder': dict(cfg['projectholder'], route_to=['BUILDER'])},
                    {'command_registry': dict(cfg['command_registry'], cycle='other')}]
        for variant in variants:
            with self.subTest(variant=variant):
                self.cfg = dict(cfg, **variant)
                self.assertEqual(self.cli(2)['state'], 'CONFLICT')
                self.assertEqual(self.state.read_bytes(), before)
        self.cfg = cfg
        previous = json.loads(before)
        for malformed in ({'config_hash': previous['semantic_config_hash'], 'ledger': previous['ledger']},
                          dict(previous, protocol='vpng-collab/0'), dict(previous, extra=True)):
            with self.assertRaises(Conflict):
                project_m(cfg, self.snapshot, malformed)

    def test_signal_conflict_is_diagnostic_journal_conflict_not_persisted(self):
        p = self.cli(); before = self.state.read_bytes()
        self.snapshot['37'] = [row(200, 'malformed signal')]
        q = self.cli()
        self.assertEqual(semantic(q), semantic(p))
        self.assertEqual(len(q['signal_status']['conflicts']), 1)
        self.assertEqual(self.state.read_bytes(), before)
        self.snapshot['34'].append(row(999, JOURNAL_MARKER + '\ninvalid'))
        self.assertEqual(self.cli(2)['state'], 'CONFLICT')
        self.assertEqual(self.state.read_bytes(), before)

    def test_unstable_signal_acquisition_no_state_advance(self):
        self.cli(); before = self.state.read_bytes(); observed = []
        def fetch(repo, room, opener, token):
            observed.append(room)
            if room == 37 and len(observed) > 3:
                return []
            return self.snapshot[str(room)]
        with patch('collab_watch.fetch_room', side_effect=fetch):
            with self.assertRaisesRegex(Conflict, 'changed during acquisition'):
                observe_once(self.cfg, self.state)
        self.assertEqual(observed, [37, 34, 35, 37, 34, 35])
        self.assertEqual(self.state.read_bytes(), before)
        with patch('collab_watch.fetch_room', side_effect=lambda repo, room, *args: self.snapshot[str(room)]):
            self.assertEqual(acquire(self.cfg), self.snapshot)

    def test_journal_preview_bindings(self):
        cfg = self.cfg; snapshot = snap(payloads=[row(900, 'new payload')]); original = copy.deepcopy(snapshot)
        candidate = i()
        body = candidate['body']
        _, state = project_m(cfg, snapshot)
        b = journal_preview(cfg, snapshot, 1, body, state)
        self.assertEqual(b['body_sha256'], digest(body))
        self.assertEqual(b['observation_sha256'], digest(canonical(state)))
        self.assertNotEqual(b['observation_sha256'], b['prospective_sha256'])
        actual = copy.deepcopy(snapshot); actual['34'].append(candidate)
        _, projected = project_m(cfg, actual, state)
        del projected['ledger'][physical_ref(34, candidate['id'])]
        self.assertEqual(b['prospective_sha256'], digest(canonical(projected)))
        self.assertEqual(snapshot, original)
        self.assertEqual(state, project_m(cfg, original)[1])
        changed = snap(payloads=[row(900, 'different payload')])
        self.assertNotEqual(b['prospective_sha256'], journal_preview(cfg, changed, 1, body)['prospective_sha256'])

    def test_journal_preview_closure_bound(self):
        baseline = snap([op()], payloads=[row(900, 'opening'), row(901, 'closure')])
        candidate = j(103, 'DISPOSITION', 'close', obligation={'id':'O','revision':1},
                      disposition='CLOSED', closure_ref=physical_ref(34,901))
        before = copy.deepcopy(baseline)
        a = journal_preview(self.cfg, baseline, 1, candidate['body'])
        self.assertEqual(baseline, before)
        baseline['34'][1]['body'] = 'changed closure'
        b = journal_preview(self.cfg, baseline, 1, candidate['body'])
        self.assertEqual(a['observation_sha256'], b['observation_sha256'])
        self.assertNotEqual(a['prospective_sha256'], b['prospective_sha256'])

    def test_journal_preview_rejects_duplicate_and_invalid(self):
        for row_ in [self.fact, i(110, 'bad', room=37),
                     ack(103,'bad','BUILDER',dict(target(self.fact),body_sha256='0'*64)),
                     j(104,'DISPOSITION','bad-close',obligation={'id':'absent','revision':1},
                       disposition='CLOSED',closure_ref=physical_ref(34,900))]:
            with self.subTest(row=row_), self.assertRaises(Conflict):
                journal_preview(self.cfg, self.snapshot, row_['user']['id'], row_['body'])

    def test_signal_preview_real_target_and_bindings(self):
        snapshot = snap([self.fact]); before = copy.deepcopy(snapshot)
        state = project_m(self.cfg, snapshot)[1]; saved = copy.deepcopy(state)
        b = signal_preview(self.cfg, snapshot, 1, self.signal['body'], state)
        self.assertEqual(b['journal_ref'], physical_ref(34,101))
        self.assertEqual(b['journal_sha256'], digest(self.fact['body']))
        self.assertEqual(b['body_sha256'], digest(self.signal['body']))
        self.assertEqual(snapshot, before); self.assertEqual(state, saved)
        snapshot['37'].append(row(201, 'unrelated corrupt signal'))
        c = signal_preview(self.cfg, snapshot, 1, self.signal['body'], state)
        self.assertNotEqual(c['signal_observation_sha256'], b['signal_observation_sha256'])
        self.assertEqual(c['observation_sha256'], b['observation_sha256'])
        self.cfg['signal_room'] = 38; snapshot['38'] = snapshot.pop('37')
        d = signal_preview(self.cfg, snapshot, 1, self.signal['body'], state)
        self.assertNotEqual(d['transport_config_hash'], c['transport_config_hash'])
        self.assertEqual(d['semantic_config_hash'], c['semantic_config_hash'])

    def test_signal_preview_rejects_absent_wrong_and_duplicate(self):
        with self.assertRaises(Conflict): signal_preview(self.cfg, snap(), 1, self.signal['body'])
        with self.assertRaises(Conflict): signal_preview(self.cfg, snap([self.fact]), 1, sig(200,self.fact,journal_sha256='0'*64)['body'])
        for prior in [self.signal, sig(201,self.fact,sid='s200',extra=True)]:
            with self.subTest(prior=prior), self.assertRaisesRegex(Conflict, 'already exists'):
                signal_preview(self.cfg, snap([self.fact],[prior]), 1, self.signal['body'])
        with self.assertRaises(Conflict): signal_preview(self.cfg, snap([self.fact]), 2, self.signal['body'])


if __name__ == '__main__':
    unittest.main()
