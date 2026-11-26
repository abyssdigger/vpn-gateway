import copy
import json
import unittest

from core import Conflict, PROTOCOL, project

CFG = {'repository': 'owner/repo', 'event_room': 33, 'task_rooms': [34],
       'roles': {'GUARD': {'actor_id': 1, 'incarnation': 'g1'},
                 'BUILDER': {'actor_id': 1, 'incarnation': 'b1'}},
       'projectholder': {'actor_id': 2, 'room': 35, 'route_to': ['GUARD']},
       'legacy_comments': [99],
       'command_registry': {'cycle': 'trial', 'capability_scopes': {'write': ['pilot']},
                            'condition_keys': ['reviewed'], 'utc_keys': ['cycle-end'],
                            'model_scopes': {'BUILDER': {'gpt6': ['pilot']}}}}
REF = 'issue:34#issuecomment-900'
HREF = 'issue:34#issuecomment-901'
SHA = 'a' * 40


def row(cid, body, actor=1):
    return {'id': cid, 'user': {'id': actor}, 'body': body}


def ev(cid, kind, mid, sender='GUARD', to=None, actor=None, **fields):
    role = CFG['roles'][sender]
    e = {'protocol': PROTOCOL, 'event_id': mid, 'kind': kind, 'room': 34,
         'from': sender, 'to': to or ['BUILDER'], 'incarnation': role['incarnation'],
         'payload_ref': REF}
    e.update(fields)
    return row(cid, '```json\n' + json.dumps(e, sort_keys=True) + '\n```', role['actor_id'] if actor is None else actor)


def op(cid=100, mid='open', rev=1, **kw):
    return ev(cid, 'OPEN', mid, obligation={'id': 'O', 'revision': rev, 'kind': 'implementation', 'assignee': 'BUILDER', 'disposition_by': 'GUARD'}, **kw)


def inp(cid=101, mid='reply', sender='BUILDER', to=None, rev=1, outcome='ANSWER', **kw):
    return ev(cid, 'INPUT', mid, sender=sender, to=to or ['GUARD'], outcome=outcome, obligation={'id': 'O', 'revision': rev}, **kw)


def handled(cid=102, mid='ack', sender='GUARD', ids=None):
    return ev(cid, 'HANDLED', mid, sender=sender, to=[sender], event_ids=ids or ['reply'])


def disp(cid=103, mid='done', rev=1, disposition='CLOSED', sender='GUARD', **kw):
    return ev(cid, 'DISPOSITION', mid, sender=sender, obligation={'id': 'O', 'revision': rev}, disposition=disposition, closure_ref=REF, **kw)


def snap(events=(), payloads=None, holder=()):
    return {'33': list(events), '34': payloads if payloads is not None else [row(900, 'durable task prose'), row(901, 'holder input', actor=2)], '35': list(holder)}


def run(events=(), prior=None, payloads=None, holder=()):
    return project(CFG, snap(events, payloads, holder), prior)


class ReplayTests(unittest.TestCase):
    def test_registered_commands(self):
        forms = [('!COLLAB STOP cycle=trial', 'STOP', {'cycle': 'trial'}),
                 ('!COLLAB DENY capability=write scope=pilot', 'DENY', {'capability': 'write', 'scope': 'pilot'}),
                 ('!COLLAB ALLOW capability=write scope=pilot', 'ALLOW', {'capability': 'write', 'scope': 'pilot'}),
                 ('!COLLAB ALLOW capability=write scope=pilot condition=reviewed until=cycle-end', 'ALLOW', {'capability': 'write', 'scope': 'pilot', 'condition': 'reviewed', 'until': 'cycle-end'}),
                 ('!COLLAB MODEL role=BUILDER model=gpt6 scope=pilot', 'MODEL', {'role': 'BUILDER', 'model': 'gpt6', 'scope': 'pilot'})]
        for body, kind, args in forms:
            with self.subTest(kind=kind, args=args):
                p, _ = run(holder=[row(800, body, actor=2)])
                reason = p['roles']['GUARD']['reasons'][0]
                self.assertEqual(reason['outcome'], 'HOLDER_COMMAND')
                self.assertEqual(reason['command'], {'id': kind, 'args': args})
                self.assertEqual(p['roles']['BUILDER']['reasons'], p['roles']['GUARD']['reasons'])
                self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
                self.assertNotIn(body, json.dumps(p))

    def test_command_ack_is_per_worker(self):
        holder = [row(800, '!COLLAB STOP cycle=trial', actor=2)]
        p, _ = run([handled(100, ids=['holder:800'])], holder=holder)
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
        p, _ = run([handled(100, ids=['holder:800']),
                    handled(101, mid='ack-b', sender='BUILDER', ids=['holder:800'])], holder=holder)
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')

    def test_command_not_guessed(self):
        forms = ['!COLLAB STOP cycle=another', '!COLLAB STOP cycle=trial\n',
                 ' !COLLAB STOP cycle=trial', '!COLLAB stop cycle=trial',
                 '```\n!COLLAB STOP cycle=trial\n```',
                 '!COLLAB ALLOW capability=write scope=other',
                 '!COLLAB ALLOW capability=write scope=pilot until=unknown',
                 '!COLLAB ALLOW capability=write scope=pilot condition=unknown',
                 '!COLLAB MODEL role=GUARD model=gpt6 scope=pilot',
                 '!COLLAB DENY capability=unknown scope=pilot',
                 'please stop the cycle']
        for body in forms:
            with self.subTest(body=body):
                p, _ = run(holder=[row(800, body, actor=2)])
                reason = p['roles']['GUARD']['reasons'][0]
                self.assertEqual(reason['outcome'], 'PRODUCT_MANAGER')
                self.assertNotIn('command', reason)

    def test_nonholder_command_ignored(self):
        p, _ = run(holder=[row(800, '!COLLAB STOP cycle=trial', actor=1)])
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')

    def test_room_qualified_physical_identity(self):
        p, state = run([op(900)], holder=[row(900, 'ordinary', actor=2)])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
        self.assertEqual(p['roles']['GUARD']['state'], 'READY')
        self.assertEqual(set(state['ledger']), {'issue:33#issuecomment-900', 'issue:34#issuecomment-900', 'issue:35#issuecomment-900'})

    def test_open_only_builder_ready(self):
        p, _ = run([op()])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')
        self.assertNotIn('PROJECTHOLDER', p['roles'])

    def test_identical_logical_and_physical_duplicates(self):
        a = inp()
        p, _ = run([op(), a, a, {**a, 'id': 104}])
        self.assertEqual(len(p['roles']['GUARD']['reasons']), 1)

    def test_conflicting_logical_body(self):
        with self.assertRaises(Conflict):
            run([op(), inp(), inp(104, outcome='PARTIAL')])

    def test_conflicting_physical_body(self):
        with self.assertRaises(Conflict):
            run([op(), inp(), inp(outcome='NEEDS_INFO')])

    def test_partial_and_needs_info_not_closure(self):
        for outcome in ('PARTIAL', 'NEEDS_INFO', 'REJECTED'):
            with self.subTest(outcome=outcome):
                p, _ = run([op(), inp(outcome=outcome)])
                self.assertEqual(p['obligations'][0]['status'], 'OPEN')
                self.assertEqual(p['roles']['GUARD']['state'], 'READY')

    def test_ack_not_closure(self):
        p, _ = run([op(), inp(), handled()])
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')
        self.assertEqual(p['obligations'][0]['status'], 'OPEN')
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')

    def test_closure_requires_exact_ref(self):
        e = disp()
        d = json.loads(e['body'][8:-4]); del d['closure_ref']
        with self.assertRaises(Conflict):
            run([op(), row(103, '```json\n' + json.dumps(d) + '\n```')])

    def test_closer_only(self):
        with self.assertRaises(Conflict):
            run([op(), disp(sender='BUILDER')])

    def test_explicit_close(self):
        p, _ = run([op(), inp(), handled(), disp()])
        self.assertEqual(p['obligations'][0]['status'], 'CLOSED')
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')

    def test_conflicting_terminal_claims(self):
        with self.assertRaises(Conflict):
            run([op(), disp(), disp(104, 'cancel', disposition='CANCELLED')])

    def test_late_old_revision(self):
        p, _ = run([op(), disp(102, 'sup', disposition='SUPERSEDED'), op(103, 'new', rev=2), inp(104, 'late', rev=1)])
        self.assertEqual([x['status'] for x in p['obligations']], ['SUPERSEDED', 'OPEN'])
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')
        self.assertIn('late', p['stale_events'])

    def test_revision_without_supersession(self):
        with self.assertRaises(Conflict):
            run([op(), op(104, 'new', rev=2)])

    def test_blocked_and_exact_response(self):
        a = op(wait_for_event_id='response')
        p, _ = run([a])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')
        wrong = inp(101, 'other', sender='GUARD', to=['BUILDER'])
        p, _ = run([a, wrong, handled(102, 'b-ack', 'BUILDER', ['other'])])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')
        right = inp(103, 'response', sender='GUARD', to=['BUILDER'], outcome='NEEDS_INFO')
        p, _ = run([a, wrong, handled(102, 'b-ack', 'BUILDER', ['other']), right])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
        self.assertEqual(p['obligations'][0]['status'], 'OPEN')

    def test_block_predicate_not_satisfied_by_ack_or_wrong_target(self):
        with self.assertRaises(Conflict):
            run([op(wait_for_event_id='reply'), inp()])
        with self.assertRaises(Conflict):
            run([op(wait_for_event_id='ack'), inp(), handled()])

    def test_block_update_and_dormant(self):
        block = ev(101, 'BLOCK', 'block', sender='BUILDER', to=['BUILDER'], obligation={'id': 'O', 'revision': 1}, wait_for_event_id='response')
        dormant = ev(102, 'DORMANT', 'dormant', sender='BUILDER', to=['BUILDER'], wait_for_event_id='response')
        p, _ = run([op(), block, dormant])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')
        p, _ = run([op(), block, dormant, inp(103, 'response', sender='GUARD', to=['BUILDER'])])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
        self.assertEqual(p['roles']['BUILDER']['dormant_claims'][0]['event_id'], 'dormant')

    def test_dormant_never_suppresses_open_work(self):
        p, _ = run([op(), ev(101, 'DORMANT', 'd', sender='BUILDER', to=['BUILDER'])])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')

    def test_foreign_actor_ignored_role_claim_not_authority(self):
        p, _ = run([op(actor=999)])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')
        self.assertEqual(len(p['ignored_external']), 1)
        p, _ = run([op(actor=2)])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')

    def test_stale_incarnation(self):
        with self.assertRaises(Conflict):
            run([op(incarnation='g-old')])

    def test_ready_claim_and_unknown_kind_fail_closed(self):
        for e in (op(state='READY'), ev(100, 'RUN', 'bad'), op(protocol='vpng-collab/1')):
            with self.assertRaises(Conflict):
                run([e])

    def test_duplicate_json_key(self):
        e = op(); e['body'] = e['body'].replace('"kind": "OPEN"', '"kind": "OPEN", "kind": "OPEN"')
        with self.assertRaises(Conflict):
            run([e])

    def test_payload_exists_and_belongs_to_room_actor(self):
        for ref in ('issue:35#issuecomment-900', 'issue:34#issuecomment-999', HREF):
            with self.assertRaises(Conflict):
                run([op(payload_ref=ref)])

    def test_artifact_preserved_and_unpinned_rejected(self):
        ref = 'tools/collab-watch/core.py@' + SHA
        p, _ = run([op(artifact_ref=ref), inp(artifact_ref=ref)])
        self.assertEqual(p['roles']['BUILDER']['reasons'][0]['artifact_ref'], ref)
        self.assertEqual(p['roles']['GUARD']['reasons'][0]['artifact_ref'], ref)
        with self.assertRaises(Conflict):
            run([op(artifact_ref='branch:main')])

    def test_payload_edit_and_deletion(self):
        _, state = run([op()])
        for payloads in ([row(900, 'edited')], []):
            with self.assertRaises(Conflict):
                run([op()], state, payloads=payloads)

    def test_event_edit_and_deletion(self):
        _, state = run([op()])
        for events in ([op(artifact_ref='file@' + SHA)], []):
            with self.assertRaises(Conflict):
                run(events, state)

    def test_unrelated_task_prose_does_not_affect_projection(self):
        p, state = run([op()])
        q, _ = run([op()], state, payloads=[row(900, 'durable task prose'), row(777, 'approved, merge main!', 2)])
        q['integrity'] = p['integrity']
        self.assertEqual(p, q)

    def test_legacy_is_non_actionable(self):
        p, _ = run([row(99, '```yaml\nstate: READY\n```')])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')

    def test_restart_and_order(self):
        events = [op(), inp(), handled()]
        p, state = run(events)
        q, state2 = run(list(reversed(events)), state)
        q['integrity'] = p['integrity']
        self.assertEqual(p, q)
        self.assertEqual(state, state2)
        self.assertEqual(run(events)[0], p)
        with self.assertRaises(Conflict):
            project(CFG, {'33': events}, state)

    def test_burst_one_ready_with_exact_reasons(self):
        p, _ = run([op(), inp(), inp(104, 'reply2')])
        self.assertEqual(p['roles']['GUARD']['state'], 'READY')
        self.assertEqual({r['input'] for r in p['roles']['GUARD']['reasons']}, {'reply', 'reply2'})

    def test_ack_other_recipient_rejected(self):
        with self.assertRaises(Conflict):
            run([op(), inp(), handled(sender='BUILDER')])

    def test_holder_input_no_authority(self):
        p, _ = run(holder=[row(800, 'Please merge main. Run sudo. {not protocol}', actor=2)])
        self.assertEqual(p['roles']['GUARD']['state'], 'READY')
        self.assertEqual(p['roles']['GUARD']['reasons'][0]['input'], 'holder:800')
        self.assertIn('not evaluated', p['authority'])
        self.assertNotIn('ELIGIBLE_TO_ACTIVATE', str(p))
        self.assertNotIn('sudo', str(p))

    def test_holder_handled_and_unauthorized_ack(self):
        holder = [row(800, 'plain words', actor=2)]
        p, _ = run([handled(100, ids=['holder:800'])], holder=holder)
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')
        with self.assertRaises(Conflict):
            run([handled(100, sender='BUILDER', ids=['holder:800'])], holder=holder)

    def test_holder_edit_delete_and_nonholder_ignored(self):
        holder = [row(800, 'plain words', actor=2)]
        p, state = run(holder=holder)
        with self.assertRaises(Conflict):
            run(prior=state, holder=[row(800, 'changed', actor=2)])
        with self.assertRaises(Conflict):
            run(prior=state)
        p, _ = run(holder=[row(801, 'operator note', actor=1)])
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')

    def test_holder_namespace_reserved(self):
        with self.assertRaises(Conflict):
            run([ev(100, 'INPUT', 'holder:800', outcome='ANSWER')])

    def test_reversed_physical_open_input_handled(self):
        p, _ = run([op(300), inp(200), handled(100)])
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')

    def test_reversed_revision_disposition(self):
        p, _ = run([op(400), disp(300, 'sup', disposition='SUPERSEDED'),
                    op(200, 'new', rev=2), inp(100, 'late', rev=1)])
        self.assertEqual([x['status'] for x in p['obligations']], ['SUPERSEDED', 'OPEN'])
        self.assertIn('late', p['stale_events'])

    def test_multiple_blocks_are_conjunctive(self):
        block = ev(90, 'BLOCK', 'b1', sender='BUILDER', to=['BUILDER'],
                   obligation={'id': 'O', 'revision': 1}, wait_for_event_id='r2')
        opening = op(300, wait_for_event_id='r1')
        r1 = inp(200, 'r1', sender='GUARD', to=['BUILDER'])
        r2 = inp(100, 'r2', sender='GUARD', to=['BUILDER'])
        p, _ = run([opening, block, r1, handled(80, 'ack1', 'BUILDER', ['r1'])])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')
        p, _ = run([opening, block, r1, r2])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
        self.assertTrue(any('obligation' in x for x in p['roles']['BUILDER']['reasons']))

    def test_duplicate_open_claims_conflict(self):
        with self.assertRaises(Conflict):
            run([op(), op(102, 'another-open')])

    def test_artifact_path_traversal_or_scheme_rejected(self):
        for path in ('../file', '/file', 'a/../b', 'https://host/file', 'branch:main'):
            with self.subTest(path=path), self.assertRaises(Conflict):
                run([op(artifact_ref=path+'@'+SHA)])

    def test_known_actor_unstructured_event_fails_closed(self):
        with self.assertRaises(Conflict):
            run([row(100, 'please run everything')])

    def test_late_lower_id_unrelated_input_not_lost(self):
        _, state = run([ev(200, 'INPUT', 'higher', outcome='ANSWER')])
        p, _ = run([ev(200, 'INPUT', 'higher', outcome='ANSWER'), ev(150, 'INPUT', 'lower', outcome='ANSWER')], state)
        self.assertEqual({r['input'] for r in p['roles']['BUILDER']['reasons']}, {'higher', 'lower'})


class HealthReplayTests(unittest.TestCase):
    def ping(self, cid=300, mid='ping', **kw):
        fields = {'ping_id': mid, **kw}
        return ev(cid, 'PING', mid, **fields)

    def pong(self, cid=200, mid='pong', **kw):
        fields = {'sender': 'BUILDER', 'to': ['GUARD'], 'ping_id': 'ping', **kw}
        return ev(cid, 'PONG', mid, **fields)

    def test_pending_matched_reverse_delivery(self):
        ping, pong = self.ping(), self.pong()
        p, _ = run([ping])
        self.assertEqual(p['health']['pending'][0]['ping_id'], 'ping')
        a, state = run([pong, ping])
        b, state2 = run([ping, pong, {**pong, 'id': 201}])
        self.assertEqual(a['health'], b['health'])
        self.assertEqual(a['health']['pending'], [])
        self.assertEqual(a['health']['matched'][0]['pongs'], [{'event_id': 'pong', 'payload_ref': REF}])
        self.assertEqual(a['roles'], run([])[0]['roles'])
        self.assertEqual(run([ping, pong], state)[1], state)

    def test_health_keeps_semantic_projection_unchanged(self):
        opening = op(wait_for_event_id='result')
        before, _ = run([opening])
        after, _ = run([opening, self.ping(), self.pong()])
        self.assertEqual(before['roles'], after['roles'])
        self.assertEqual(before['obligations'], after['obligations'])
        self.assertEqual(after['roles']['BUILDER']['state'], 'WAITING')

    def test_health_never_satisfies_block_or_handled(self):
        for events in ([op(wait_for_event_id='ping'), self.ping()],
                       [op(wait_for_event_id='pong'), self.ping(), self.pong()],
                       [self.ping(), handled(101, ids=['ping'], sender='BUILDER')],
                       [self.ping(), self.pong(), handled(101, ids=['pong'])]):
            with self.subTest(events=events), self.assertRaises(Conflict):
                run(events)

    def test_missing_or_wrong_roles(self):
        for events in ([self.pong()], [self.ping(), self.pong(ping_id='missing')],
                       [self.ping(), self.pong(sender='GUARD', to=['BUILDER'])],
                       [self.ping(), self.pong(to=['BUILDER'])],
                       [self.ping(), self.pong(ping_id='pong')]):
            with self.subTest(events=events), self.assertRaises(Conflict):
                run(events)

    def test_strict_health_envelopes(self):
        for event in (self.ping(ping_id='not-ping'), self.ping(ping_id=None),
                      self.ping(to=['GUARD']), self.ping(to=['GUARD','BUILDER']),
                      self.ping(incarnation='g-old'), self.ping(outcome='ANSWER'),
                      self.ping(obligation={'id':'O','revision':1})):
            with self.subTest(event=event), self.assertRaises(Conflict):
                run([event])
        for event in (self.pong(disposition='CLOSED'), self.pong(incarnation='b-old'),
                      self.pong(outcome='ANSWER'), self.pong(ping_id=None)):
            with self.subTest(event=event), self.assertRaises(Conflict):
                run([self.ping(), event])

    def test_wrong_room_even_with_valid_payload(self):
        cfg = copy.deepcopy(CFG)
        cfg['task_rooms'].append(36)
        snapshots = snap([self.ping(), self.pong(room=36, payload_ref='issue:36#issuecomment-902')])
        snapshots['36'] = [row(902, 'valid other-room payload')]
        with self.assertRaises(Conflict):
            project(cfg, snapshots)

    def test_health_identity_conflict(self):
        for events in ([self.ping(), self.ping(301, payload_ref='issue:34#issuecomment-902')],
                       [self.ping(), ev(301, 'INPUT', 'ping', outcome='ANSWER')]):
            with self.subTest(events=events), self.assertRaises(Conflict):
                run(events, payloads=[row(900, 'payload'), row(902, 'other payload')])

    def test_foreign_actor_never_confirms_health(self):
        a, _ = run([self.ping(), self.pong(actor=999)])
        self.assertEqual(len(a['health']['pending']), 1)
        self.assertEqual(a['health']['matched'], [])

    def test_multiple_replies_sorted_and_repeat_idempotent(self):
        a, _ = run([self.ping(), self.pong(mid='z'), self.pong(201, mid='a')])
        self.assertEqual([p['event_id'] for p in a['health']['matched'][0]['pongs']], ['a','z'])

    def test_health_payload_integrity(self):
        _, state = run([self.ping(), self.pong()])
        with self.assertRaises(Conflict):
            run([self.ping()], state)
        with self.assertRaises(Conflict):
            run([self.ping(), self.pong()], state, payloads=[row(900, 'edited')])


if __name__ == '__main__':
    unittest.main()
