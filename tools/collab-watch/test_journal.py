"""M1 offline journal/signal projection: no acquisition, send, or delete."""
import copy
import itertools
import unittest

from core import Conflict, canonical, digest, project
from journal import (JOURNAL_MARKER, SIGNAL_MARKER, PROTOCOL, SIGNAL_PROTOCOL,
                     framed, physical_ref, project_m, validate_m_config)

CFG = {'protocol': PROTOCOL, 'repository': 'owner/repo', 'signal_room': 37,
       'task_rooms': [34], 'journal_epoch': 'm1',
       'roles': {'GUARD': {'actor_id': 1, 'incarnation': 'g1'},
                 'BUILDER': {'actor_id': 2, 'incarnation': 'b1'}},
       'projectholder': {'actor_id': 3, 'room': 35, 'route_to': ['GUARD']},
       'command_registry': {'cycle': 'new-cdc', 'capability_scopes': {},
                            'condition_keys': [], 'utc_keys': [], 'model_scopes': {}}}


def row(cid, body, actor=1):
    return {'id': cid, 'user': {'id': actor}, 'body': body}


def frame(marker, obj):
    return marker + '\n```json\n' + canonical(obj) + '\n```'


def j(cid, kind, mid, sender='GUARD', to=('BUILDER',), **kw):
    e = {'protocol': PROTOCOL, 'journal_epoch': 'm1', 'event_id': mid, 'kind': kind,
         'room': 34, 'from': sender, 'to': list(to),
         'incarnation': CFG['roles'][sender]['incarnation'],
         'payload_ref': physical_ref(34, 900)}
    e.update(kw)
    return row(cid, frame(JOURNAL_MARKER, e), CFG['roles'][sender]['actor_id'])


def op(cid=100, mid='open', rev=1, **kw):
    return j(cid, 'OPEN', mid, obligation={'id': 'O', 'revision': rev, 'kind': 'work',
             'assignee': 'BUILDER', 'disposition_by': 'GUARD'}, **kw)


def i(cid=101, mid='input', **kw):
    return j(cid, 'INPUT', mid, outcome='ANSWER', **kw)


def target(fact, room=34, mid=None):
    return {'event_id': mid if mid is not None else framed(fact['body'], JOURNAL_MARKER)['event_id'],
            'ref': physical_ref(room, fact['id']), 'body_sha256': digest(fact['body'])}


def ack(cid, mid, sender, *targets):
    return j(cid, 'HANDLED', mid, sender, (sender,), handled=list(targets))


def sig(cid, fact, recipient='BUILDER', sid=None, **kw):
    e = framed(fact['body'], JOURNAL_MARKER)
    p = {'protocol': SIGNAL_PROTOCOL, 'journal_epoch': 'm1', 'signal_id': sid or f's{cid}',
         'event_id': e['event_id'], 'journal_ref': physical_ref(e['room'], fact['id']),
         'journal_sha256': digest(fact['body']), 'from': e['from'], 'to': recipient,
         'incarnation': e['incarnation']}
    p.update(kw)
    return row(cid, frame(SIGNAL_MARKER, p), fact['user']['id'])


def snap(facts=(), signals=(), holder=(), payloads=None):
    return {'34': [*(payloads if payloads is not None else [row(900, 'task prose'), row(901, 'peer prose', 2)]), *facts],
            '35': list(holder), '37': list(signals)}


def run(facts=(), signals=(), holder=(), payloads=None, previous=None):
    return project_m(CFG, snap(facts, signals, holder, payloads), previous)


def semantic(projection):
    return {k: v for k, v in projection.items() if k not in {'signal_status', 'gc_candidates', 'integrity'}}


def ready(p, role='BUILDER'):
    return p['roles'][role]['state'] == 'READY'


class JournalTests(unittest.TestCase):
    def test_open_and_input_without_signal_restart(self):
        facts = [op(), i()]
        p, state = run(facts)
        self.assertTrue(ready(p))
        self.assertEqual(len(p['roles']['BUILDER']['reasons']), 2)
        self.assertEqual(p['obligations'][0]['status'], 'OPEN')
        self.assertEqual(run(facts, previous=state)[1], state)
        self.assertEqual(semantic(run(facts)[0]), semantic(p))
        self.assertEqual(set(state['ledger']), {physical_ref(34, x) for x in [100, 101, 900]})

    def test_consumed_duplicates_partial_gc_restart(self):
        fact = i()
        receipt = ack(102, 'ack', 'BUILDER', target(fact))
        signal = sig(200, fact)
        dup = copy.deepcopy(signal); dup['id'] = 201
        p, state = run([fact, receipt], [signal, dup, signal])
        self.assertFalse(ready(p))
        self.assertEqual([c['physical_ref'] for c in p['gc_candidates']], [physical_ref(37, x) for x in [200, 201]])
        c = p['gc_candidates'][0]
        self.assertEqual(c, {'physical_ref': physical_ref(37, 200), 'actor_id': 1,
                             'body_sha256': digest(signal['body']), 'signal_id': 's200',
                             'event_id': 'input', 'journal_ref': physical_ref(34, 101),
                             'journal_sha256': digest(fact['body']), 'recipient': 'BUILDER',
                             'receipt_refs': [physical_ref(34, 102)]})
        for signals in ([dup], [], [signal, dup]):
            for previous in (None, state):
                after, after_state = run([receipt, fact], signals, previous=previous)
                self.assertEqual(semantic(after), semantic(p))
                self.assertEqual(after_state, state)
                self.assertEqual(len(after['gc_candidates']), len(signals))

    def test_signal_corruption_only_local(self):
        fact = i()
        p, state = run([fact], [sig(200, fact)])
        for bad in [row(200, 'malformed'), sig(200, fact, journal_sha256='0'*64),
                    sig(200, fact, journal_ref=physical_ref(34, 999)),
                    sig(200, fact, event_id='other'), sig(200, fact, recipient='GUARD'),
                    sig(200, fact, incarnation='old'), sig(200, fact, journal_epoch='old'),
                    sig(200, fact, protocol=PROTOCOL), sig(200, fact, to=['BUILDER']),
                    sig(200, fact, extra=True), row(200, sig(200, fact)['body'], 2)]:
            with self.subTest(bad=bad):
                q, s = run([fact], [bad], previous=state)
                self.assertEqual(semantic(q), semantic(p))
                self.assertEqual(s, state)
                self.assertEqual(len(q['signal_status']['conflicts']), 1)
                self.assertEqual(q['gc_candidates'], [])
        p, _ = run([fact], [row(200, 'unknown actor garbage', 99)])
        self.assertTrue(ready(p))
        self.assertEqual(p['signal_status']['ignored_external'], [physical_ref(37, 200)])

    def test_conflicting_signal_logical_and_physical_identity(self):
        fact = i(); receipt = ack(102, 'ack', 'BUILDER', target(fact))
        s = sig(200, fact)
        for conflicting in [sig(201, fact, sid='s200', journal_sha256='0'*64),
                            sig(201, fact, sid='s200', extra=True),
                            row(200, 'changed'), row(200, s['body'], 99)]:
            p, _ = run([fact, receipt], [s, conflicting])
            self.assertFalse(ready(p))
            self.assertEqual(p['gc_candidates'], [])
            self.assertIn(physical_ref(37, 200), {x['physical_ref'] for x in p['signal_status']['conflicts']})
        # Two valid but distinct physical/semantic targets sharing a signal ID.
        other = i(103, 'other'); other_ack = ack(104, 'ack2', 'BUILDER', target(other))
        p, _ = run([fact, receipt, other, other_ack], [s, sig(201, other, sid='s200')])
        self.assertEqual(len(p['signal_status']['conflicts']), 2)
        self.assertEqual(p['gc_candidates'], [])

    def test_journal_reserved_frame_strict_and_external_ignored(self):
        fact = i()
        for body in [JOURNAL_MARKER, JOURNAL_MARKER+'\n```json\n{bad}\n```',
                     fact['body']+'\ntrailing prose', fact['body'].replace('/1 -->', '/2 -->', 1),
                     fact['body'].replace('"journal_epoch":"m1"','"journal_epoch":"old"'),
                     fact['body'].replace('"protocol":"vpng-collab/1"','"protocol":"vpng-collab/0"'),
                     fact['body'].replace('"kind":"INPUT"','"kind":"NOPE"'),
                     fact['body'].replace('"kind":"INPUT"','"kind":"INPUT","kind":"INPUT"')]:
            with self.subTest(body=body), self.assertRaises(Conflict):
                run([row(101, body)])
        p, state = run([row(101, 'Quoted example:\n'+fact['body']), row(102, JOURNAL_MARKER, 99)])
        self.assertFalse(ready(p))
        self.assertEqual(state['ledger'], {})
        self.assertEqual(p['ignored_external'], [physical_ref(34, 102)])
        with self.assertRaises(Conflict):
            run([i(payload_ref=physical_ref(34, 102)), row(102, JOURNAL_MARKER, 99)])

    def test_peer_payload_and_closure_author_binding(self):
        fact = i(payload_ref=physical_ref(34, 901))
        p, state = run([fact])
        self.assertTrue(ready(p)); self.assertIn(physical_ref(34, 901), state['ledger'])
        done = j(102, 'DISPOSITION', 'done', obligation={'id':'O','revision':1},
                 disposition='CLOSED', closure_ref=physical_ref(34, 901))
        with self.assertRaisesRegex(Conflict, 'payload actor mismatch'):
            run([op(), done])
        done = j(102, 'DISPOSITION', 'done', obligation={'id':'O','revision':1},
                 disposition='CLOSED', closure_ref=physical_ref(34, 900), payload_ref=physical_ref(34, 901))
        self.assertEqual(run([op(), done])[0]['obligations'][0]['status'], 'CLOSED')
        with self.assertRaisesRegex(Conflict, 'missing or wrong-room payload'):
            run([op(), i(payload_ref=physical_ref(34, 100))])
        with self.assertRaises(Conflict):
            run([op(), i(payload_ref=physical_ref(35, 900))])

    def test_exact_receipt_prevents_fresh_replay_after_target_edit(self):
        fact = i(); receipt = ack(102, 'ack', 'BUILDER', target(fact))
        old = run([fact, receipt])[1]
        edit = j(101, 'INPUT', 'input', outcome='PARTIAL')
        for facts in ([edit, receipt], [receipt], [fact, ack(102, 'ack','BUILDER',dict(target(fact), body_sha256='0'*64))]):
            with self.subTest(facts=facts), self.assertRaises(Conflict):
                run(facts)  # no retained ledger needed for this binding
        with self.assertRaises(Conflict):
            run([edit, receipt], previous=old)

    def test_canonical_ledger_edits_and_deletions(self):
        fact = i(); receipt = ack(102, 'ack','BUILDER', target(fact))
        holder = [row(800, 'holder prose', 3)]
        p, state = run([fact, receipt], holder=holder)
        for args in [dict(facts=[fact], holder=holder), dict(facts=[fact, receipt], holder=[]),
                     dict(facts=[fact, receipt], holder=holder, payloads=[row(900, 'changed')]),
                     dict(facts=[fact, receipt], holder=holder, payloads=[row(900, 'task prose', 2)]),
                     dict(facts=[fact, receipt], holder=[row(800, 'changed', 3)])]:
            with self.subTest(args=args), self.assertRaises(Conflict):
                run(previous=state, **args)
        self.assertEqual(semantic(run([fact, receipt], holder=holder, previous=state)[0]), semantic(p))

    def test_independent_recipient_and_physical_occurrence_receipts(self):
        fact = i(to=('GUARD','BUILDER'))
        same = copy.deepcopy(fact); same['id'] = 104
        sg, sb, sb2 = sig(200, fact, 'GUARD'), sig(201, fact), sig(202, same)
        gb = ack(102, 'b', 'BUILDER', target(fact))
        p, _ = run([fact, same, gb], [sg, sb, sb2])
        self.assertTrue(ready(p, 'GUARD')); self.assertFalse(ready(p))
        self.assertEqual([c['physical_ref'] for c in p['gc_candidates']], [physical_ref(37, 201)])
        gg = ack(103, 'g', 'GUARD', target(fact)); gb2 = ack(105, 'b2', 'BUILDER', target(same))
        q, _ = run([fact, same, gb, gg, gb2], [sg, sb, sb2])
        self.assertFalse(ready(q, 'GUARD')); self.assertFalse(ready(q))
        self.assertEqual(len(q['gc_candidates']), 3)
        # One receipt may name two physical identical occurrences explicitly.
        p, _ = run([fact, same, ack(106,'both','BUILDER',target(fact),target(same))], [sb, sb2])
        self.assertEqual(len(p['gc_candidates']), 2)

    def test_handled_open_does_not_close_or_satisfy_block(self):
        fact = op(); receipt = ack(102, 'ack','BUILDER',target(fact))
        p, _ = run([fact,receipt],[sig(200,fact)])
        self.assertEqual(len(p['gc_candidates']),1); self.assertTrue(ready(p))
        self.assertEqual(p['obligations'][0]['status'],'OPEN')
        blocked = op(wait_for_event_id='ack')
        with self.assertRaisesRegex(Conflict,'wait predicate does not match'):
            run([blocked,ack(102,'ack','BUILDER',target(blocked))])

    def test_no_ack_of_ack_or_bare_ids(self):
        fact = i(); receipt = ack(102,'ack','BUILDER',target(fact))
        for bad in [ack(103,'bad','BUILDER',target(receipt)),
                    j(103,'HANDLED','bad','BUILDER',('BUILDER',),event_ids=['input']),
                    ack(103,'bad','GUARD',target(fact)),
                    ack(103,'bad','BUILDER',target(fact),target(fact)),
                    ack(103,'bad','BUILDER',dict(target(fact),event_id='wrong'))]:
            with self.subTest(bad=bad), self.assertRaises(Conflict):run([fact,receipt,bad])
        p, _ = run([fact,receipt],[sig(200,receipt)])
        self.assertEqual(len(p['signal_status']['conflicts']),1)
        self.assertEqual(p['gc_candidates'],[])

    def test_holder_exact_receipt_and_command_per_recipient(self):
        h = row(800,'!COLLAB STOP cycle=new-cdc',3)
        ht = target(h,35,'holder:800')
        b = ack(100,'b','BUILDER',ht); g = ack(101,'g','GUARD',ht)
        p, _ = run([b],holder=[h]); self.assertFalse(ready(p)); self.assertTrue(ready(p,'GUARD'))
        p, _ = run([b,g],holder=[h]); self.assertFalse(ready(p)); self.assertFalse(ready(p,'GUARD'))
        with self.assertRaises(Conflict):run([b,g],holder=[row(800,'changed',3)])
        # The old cycle command is ordinary GUARD input in the current registry.
        old = row(801,'!COLLAB STOP cycle=old-cdc',3)
        p, _ = run(holder=[old]); self.assertTrue(ready(p,'GUARD')); self.assertFalse(ready(p))
        self.assertEqual(p['roles']['GUARD']['reasons'][0]['outcome'],'PRODUCT_MANAGER')
        with self.assertRaises(Conflict):run([ack(100,'b','BUILDER',target(old,35,'holder:801'))],holder=[old])

    def test_health_is_durable_no_implicit_gc(self):
        ping = j(100,'PING','p',ping_id='p'); pong = j(101,'PONG','q','BUILDER',('GUARD',),ping_id='p')
        sp, sq = sig(200,ping), sig(201,pong,'GUARD')
        p, state = run([ping,pong],[sp,sq])
        self.assertFalse(ready(p)); self.assertFalse(ready(p,'GUARD'))
        self.assertEqual(len(p['health']['matched']),1); self.assertEqual(p['gc_candidates'],[])
        receipts = [ack(102,'hp','BUILDER',target(ping)),ack(103,'hq','GUARD',target(pong))]
        p, state = run([ping,pong,*receipts],[sp,sq])
        self.assertEqual(len(p['gc_candidates']),2)
        for signals in ([sp],[sq],[]):
            q, s = run([pong,ping,*receipts],signals,previous=state)
            self.assertEqual(semantic(q),semantic(p)); self.assertEqual(s,state)
        with self.assertRaises(Conflict):run([pong])
        with self.assertRaises(Conflict):run([op(wait_for_event_id='p'),ping,pong])

    def test_old_and_new_config_do_not_mix(self):
        bad=copy.deepcopy(CFG); bad['event_room']=36
        with self.assertRaises(Conflict):validate_m_config(bad)
        bad=copy.deepcopy(CFG); bad['signal_room']=34
        with self.assertRaises(Conflict):validate_m_config(bad)
        old_cfg=copy.deepcopy(CFG); old_cfg.pop('protocol'); old_cfg.pop('journal_epoch'); old_cfg['event_room']=old_cfg.pop('signal_room');old_cfg['legacy_comments']=[]
        with self.assertRaises(Conflict):project_m(old_cfg,snap())
        with self.assertRaises(Conflict):project(CFG,snap())
        with self.assertRaises(Conflict):project_m(CFG,dict(snap(),**{'36':[]}))
        old = row(101,'```json\n{"protocol":"vpng-collab/0"}\n```')
        p,s=run([old]); self.assertFalse(ready(p));self.assertEqual(s['ledger'],{})
        with self.assertRaises(Conflict):run([j(101,'INPUT','i',outcome='ANSWER',journal_epoch='other')])

    def test_wrong_room_and_cross_task_receipt(self):
        cfg=copy.deepcopy(CFG); cfg['task_rooms'].append(38)
        fact=i(); sn=snap();sn['38']=[fact]
        with self.assertRaisesRegex(Conflict,'physical/semantic room mismatch'):project_m(cfg,sn)
        other=j(102,'HANDLED','h','BUILDER',('BUILDER',),handled=[target(fact)],room=38,payload_ref=physical_ref(38,901))
        sn=snap([fact]);sn['38']=[row(901,'other room',2),other]
        with self.assertRaisesRegex(Conflict,'HANDLED target identity'):project_m(cfg,sn)

    def test_fact_conflicts_and_order_independence(self):
        fact=i(); receipt=ack(102,'ack','BUILDER',target(fact))
        p,s=run([fact,receipt],[sig(200,fact)])
        for order in itertools.permutations([fact,receipt,copy.deepcopy(fact)]):
            self.assertEqual(run(order,[sig(200,fact)]),(p,s))
        with self.assertRaises(Conflict):run([fact,j(103,'INPUT','input',outcome='PARTIAL')])
        with self.assertRaises(Conflict):run([fact,row(101,'ordinary')])

    def test_shared_reducer_matches_v0_across_event_subsets(self):
        # Same logical facts, valid/invalid relation combinations, physically
        # transported by different protocols. Only admission/receipt framing differ.
        import test_core as v0
        old_cfg=copy.deepcopy(v0.CFG)
        cfg=copy.deepcopy(CFG);cfg['roles']=copy.deepcopy(old_cfg['roles'])
        cfg['projectholder']=copy.deepcopy(old_cfg['projectholder'])
        cfg['command_registry']=copy.deepcopy(old_cfg['command_registry'])
        all_rows=[v0.op(100), v0.inp(101), v0.handled(102), v0.disp(103),
                  v0.ev(104,'BLOCK','block',sender='BUILDER',to=['BUILDER'],
                        obligation={'id':'O','revision':1},wait_for_event_id='released'),
                  v0.inp(105,'released',sender='GUARD',to=['BUILDER']),
                  v0.ev(106,'PING','ping',ping_id='ping'),
                  v0.ev(107,'PONG','pong',sender='BUILDER',to=['GUARD'],ping_id='ping'),
                  v0.ev(108,'DORMANT','d',sender='BUILDER',to=['BUILDER'])]
        from core import envelope
        new_rows={}
        for item in all_rows:
            e=envelope(item['body']);e.update(protocol=PROTOCOL,journal_epoch='m1')
            if e['kind']=='HANDLED':continue
            new_rows[e['event_id']]=row(item['id'],frame(JOURNAL_MARKER,e),item['user']['id'])
        for item in all_rows:
            e=envelope(item['body']);e.update(protocol=PROTOCOL,journal_epoch='m1')
            if e['kind']=='HANDLED':
                e['handled']=[target(new_rows[mid]) for mid in e.pop('event_ids')]
                new_rows[e['event_id']]=row(item['id'],frame(JOURNAL_MARKER,e),item['user']['id'])
        keys=('roles','obligations','health','stale_events')
        valid=0
        for mask in range(1<<len(all_rows)):
            old=[item for idx,item in enumerate(all_rows) if mask&(1<<idx)]
            new=[new_rows[envelope(item['body'])['event_id']] for item in reversed(old)]
            try: expected=project(old_cfg,v0.snap(old))[0]
            except Conflict:
                with self.assertRaises(Conflict):project_m(cfg,snap(new,payloads=v0.snap()['34']))
                continue
            actual=project_m(cfg,snap(new,payloads=v0.snap()['34']))[0]
            self.assertEqual({k:actual[k] for k in keys},{k:expected[k] for k in keys})
            valid+=1
        self.assertGreater(valid,0)

    def test_invalid_signal_field_types_are_local_conflicts(self):
        fact=i();receipt=ack(102,'ack','BUILDER',target(fact))
        baseline,state=run([fact,receipt])
        original=framed(sig(200,fact)['body'],SIGNAL_MARKER)
        for field in original:
            for value in (None,False,[],{},42):
                changed=dict(original,**{field:value})
                bad=row(200,frame(SIGNAL_MARKER,changed))
                p,s=run([fact,receipt],[bad],previous=state)
                self.assertEqual(semantic(p),semantic(baseline));self.assertEqual(s,state)
                self.assertEqual(len(p['signal_status']['conflicts']),1)
                self.assertEqual(p['gc_candidates'],[])

    def test_invalid_receipt_target_types_fail_closed(self):
        fact=i();original=target(fact)
        for field in original:
            for value in (None,False,[],{},42):
                with self.assertRaises(Conflict):run([fact,ack(102,'bad','BUILDER',dict(original,**{field:value}))])
        for value in (None,False,[],{},42,[None],[{}]):
            bad=j(102,'HANDLED','bad','BUILDER',('BUILDER',),handled=value)
            with self.assertRaises(Conflict):run([fact,bad])

    def test_signal_room_rotation_does_not_change_semantic_hash(self):
        fact=i();receipt=ack(102,'ack','BUILDER',target(fact))
        p,state=run([fact,receipt],[sig(200,fact)])
        cfg=copy.deepcopy(CFG);cfg['signal_room']=39
        sn=snap([fact,receipt]);sn['39']=sn.pop('37')
        q,next_state=project_m(cfg,sn,state)
        self.assertEqual(semantic(q),semantic(p));self.assertEqual(next_state,state)
        self.assertEqual(q['gc_candidates'],[])
        sn['39']=[sig(201,fact)]
        r,last_state=project_m(cfg,sn,state)
        self.assertEqual(semantic(r),semantic(p));self.assertEqual(last_state,state)
        self.assertEqual(r['gc_candidates'][0]['physical_ref'],physical_ref(39,201))

    def test_semantic_config_changes_rejected_before_replay(self):
        fact=i();p,state=run([fact])
        for field,value in [('command_registry',dict(CFG['command_registry'],cycle='other')),
                            ('roles',dict(CFG['roles'],BUILDER={'actor_id':2,'incarnation':'new'})),
                            ('projectholder',dict(CFG['projectholder'],route_to=['BUILDER'])),
                            ('journal_epoch','different'),('repository','owner/other')]:
            cfg=copy.deepcopy(CFG);cfg[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(Conflict,'state/config mismatch'):
                project_m(cfg,snap([fact]),state)


if __name__=='__main__':unittest.main()
