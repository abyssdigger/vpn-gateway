import copy
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import Conflict, canonical, digest
from journal import JOURNAL_MARKER, SIGNAL_MARKER, project_m
from preflight_m import preflight_journal_fact, preflight_signal
from preflight_cli import main, preflight_once


def frame(marker, value):
    return marker + '\n```json\n' + canonical(value) + '\n```'


def row(cid, actor, body):
    return {'id': cid, 'user': {'id': actor}, 'body': body}


class CLI(unittest.TestCase):
    def setUp(self):
        self.cfg = {'protocol':'vpng-collab/1','repository':'owner/repo','signal_room':3,
                    'task_rooms':[1],'journal_epoch':'epoch','roles':{
                    'GUARD':{'actor_id':10,'incarnation':'g'},
                    'BUILDER':{'actor_id':11,'incarnation':'b'}},
                    'projectholder':{'actor_id':12,'room':2,'route_to':['GUARD']},
                    'command_registry':{'cycle':'cycle','capability_scopes':{},'condition_keys':[],
                                        'utc_keys':[], 'model_scopes':{}}}
        self.open = frame(JOURNAL_MARKER, {'protocol':'vpng-collab/1','event_id':'open-1',
                    'journal_epoch':'epoch','kind':'OPEN','room':1,'from':'GUARD','to':['BUILDER'],
                    'incarnation':'g','payload_ref':'issue:1#issuecomment-1',
                    'obligation':{'id':'test','revision':1,'kind':'research',
                                  'assignee':'BUILDER','disposition_by':'GUARD'}})
        self.snap = {'1':[row(1,10,'task'),row(2,10,self.open)],'2':[],'3':[]}
        self.receipt = frame(JOURNAL_MARKER, {'protocol':'vpng-collab/1','event_id':'ack-1',
                      'journal_epoch':'epoch','kind':'HANDLED','room':1,'from':'BUILDER',
                      'to':['BUILDER'],'incarnation':'b','payload_ref':'issue:1#issuecomment-1',
                      'handled':[{'event_id':'open-1','ref':'issue:1#issuecomment-2',
                                  'body_sha256':digest(self.open)}]})
        self.signal = frame(SIGNAL_MARKER, {'protocol':'vpng-collab-signal/1',
                      'journal_epoch':'epoch','signal_id':'sig-1','event_id':'open-1',
                      'journal_ref':'issue:1#issuecomment-2','journal_sha256':digest(self.open),
                      'from':'GUARD','to':'BUILDER','incarnation':'g'})
        self.previous = project_m(self.cfg,self.snap)[1]

    def test_journal_composition(self):
        snap = copy.deepcopy(self.snap); state=copy.deepcopy(self.previous)
        out=preflight_once(self.cfg,11,self.receipt,'journal',previous=state,fixture=snap)
        self.assertEqual(out['binding'],preflight_journal_fact(self.cfg,self.snap,11,self.receipt,self.previous))
        self.assertEqual(out['acquisition'],'declared-fixture'); self.assertEqual(out['history'],'retained-ledger')
        self.assertEqual(snap,self.snap); self.assertEqual(state,self.previous)

    def test_signal_composition(self):
        out=preflight_once(self.cfg,10,self.signal,'signal',fixture=self.snap)
        self.assertEqual(out['binding'],preflight_signal(self.cfg,self.snap,10,self.signal))
        self.assertEqual(out['history'],'fresh-current-only')

    def test_observation_binds_ordinary_prose(self):
        a=preflight_once(self.cfg,11,self.receipt,'journal',fixture=self.snap)
        s=copy.deepcopy(self.snap); s['1'].append(row(3,10,'new ordinary prose'))
        b=preflight_once(self.cfg,11,self.receipt,'journal',fixture=s)
        self.assertEqual(a['binding'],b['binding'])
        self.assertNotEqual(a['full_observation_sha256'],b['full_observation_sha256'])

    def test_order_independent(self):
        a=preflight_once(self.cfg,11,self.receipt,'journal',fixture=self.snap)
        s=copy.deepcopy(self.snap); s['1'].reverse()
        self.assertEqual(a,preflight_once(self.cfg,11,self.receipt,'journal',fixture=s))

    def test_wrong_actor(self):
        with self.assertRaises(Conflict): preflight_once(self.cfg,10,self.receipt,'journal',fixture=self.snap)

    def test_duplicate_receipt(self):
        s=copy.deepcopy(self.snap); s['1'].append(row(3,11,self.receipt))
        with self.assertRaises(Conflict): preflight_once(self.cfg,11,self.receipt,'journal',fixture=s)

    def test_ledger_conflict(self):
        s=copy.deepcopy(self.snap); s['1'][0]['body']='changed'
        with self.assertRaises(Conflict): preflight_once(self.cfg,11,self.receipt,'journal',previous=self.previous,fixture=s)

    def test_incomplete_fixture(self):
        s=copy.deepcopy(self.snap); del s['3']
        with self.assertRaises(Conflict): preflight_once(self.cfg,11,self.receipt,'journal',fixture=s)

    def test_live_uses_existing_acquire(self):
        with patch('preflight_cli.acquire',return_value=self.snap) as acquire:
            out=preflight_once(self.cfg,11,self.receipt,'journal',previous=self.previous,token='fixture-token')
        acquire.assert_called_once_with(self.cfg,'fixture-token',None)
        self.assertEqual(out['acquisition'],'stable-double-scan')

    def test_live_acquisition_failure(self):
        with patch('preflight_cli.acquire',side_effect=Conflict('unstable')):
            with self.assertRaises(Conflict): preflight_once(self.cfg,11,self.receipt,'journal')

    def test_cli_no_write_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name,obj in [('cfg',self.cfg),('state',self.previous),('snapshot',self.snap)]:
                (p/name).write_text(canonical(obj))
            (p/'body').write_bytes(self.receipt.encode())
            args=['--config',str(p/'cfg'),'--actor','11','--kind','journal','--candidate',str(p/'body'),
                  '--state',str(p/'state'),'--fixture',str(p/'snapshot')]
            files={x.name:x.read_bytes() for x in p.iterdir()}
            with redirect_stdout(io.StringIO()) as f: self.assertEqual(main(args),0)
            self.assertEqual(json.loads(f.getvalue())['state'],'PASS')
            self.assertEqual(files,{x.name:x.read_bytes() for x in p.iterdir()})
            (p/'body').write_bytes(self.receipt.encode()+b'\n')
            with redirect_stdout(io.StringIO()) as f: self.assertEqual(main(args),2)
            self.assertEqual(json.loads(f.getvalue())['state'],'CONFLICT')
            self.assertEqual((p/'state').read_bytes(),files['state'])
            (p/'state').unlink()
            with redirect_stdout(io.StringIO()) as f: self.assertEqual(main(args),2)
            self.assertFalse((p/'state').exists())

    def test_cli_rejects_null_fixture_or_state(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'cfg').write_text(canonical(self.cfg)); (p/'body').write_text(self.receipt)
            (p/'null').write_text('null'); (p/'snapshot').write_text(canonical(self.snap))
            base=['--config',str(p/'cfg'),'--actor','11','--kind','journal','--candidate',str(p/'body')]
            with patch('preflight_cli.acquire') as acquire, redirect_stdout(io.StringIO()):
                self.assertEqual(main(base+['--fresh','--fixture',str(p/'null')]),2)
                self.assertEqual(main(base+['--state',str(p/'null'),'--fixture',str(p/'snapshot')]),2)
                acquire.assert_not_called()


if __name__ == '__main__': unittest.main()
