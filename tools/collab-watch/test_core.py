import copy
import json
import unittest

from core import Conflict, PROTOCOL, project

CFG = {'repository': 'owner/repo', 'event_room': 33, 'task_rooms': [34],
       'roles': {'GUARD': {'actor_id': 1, 'incarnation': 'g1'},
                 'BUILDER': {'actor_id': 1, 'incarnation': 'b1'},
                 'PROJECTHOLDER': {'actor_id': 2, 'incarnation': 'h1'}},
       'legacy_comments': [99]}
REF = 'issue:34#issuecomment-900'
HREF = 'issue:34#issuecomment-901'
SHA = 'a' * 40


def row(cid, body, actor=1):
    return {'id': cid, 'user': {'id': actor}, 'body': body}


def ev(cid, kind, mid, sender='GUARD', to=None, actor=None, **fields):
    role = CFG['roles'][sender]
    e = {'protocol': PROTOCOL, 'event_id': mid, 'kind': kind, 'room': 34,
         'from': sender, 'to': to or ['BUILDER'], 'incarnation': role['incarnation'],
         'payload_ref': HREF if sender == 'PROJECTHOLDER' else REF}
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


def snap(events=(), payloads=None):
    return {'33': list(events), '34': payloads if payloads is not None else [row(900, 'durable task prose'), row(901, 'holder input', actor=2)]}


def run(events=(), prior=None, payloads=None):
    return project(CFG, snap(events, payloads), prior)


class ReplayTests(unittest.TestCase):
    def test_open_only_builder_ready(self):
        p, _ = run([op()])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')
        self.assertEqual(p['roles']['GUARD']['state'], 'WAITING')
        self.assertEqual(p['roles']['PROJECTHOLDER']['state'], 'WAITING')

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
        self.assertEqual(p['roles']['BUILDER']['dormant_claim']['event_id'], 'dormant')

    def test_dormant_never_suppresses_open_work(self):
        p, _ = run([op(), ev(101, 'DORMANT', 'd', sender='BUILDER', to=['BUILDER'])])
        self.assertEqual(p['roles']['BUILDER']['state'], 'READY')

    def test_foreign_actor_ignored_role_claim_not_authority(self):
        p, _ = run([op(actor=999)])
        self.assertEqual(p['roles']['BUILDER']['state'], 'WAITING')
        self.assertEqual(len(p['ignored_external']), 1)
        with self.assertRaises(Conflict):
            run([op(actor=2)])

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
        e = ev(100, 'INPUT', 'decision', sender='PROJECTHOLDER', to=['GUARD'], outcome='ANSWER')
        p, _ = run([e])
        self.assertEqual(p['roles']['GUARD']['state'], 'READY')
        self.assertIn('not evaluated', p['authority'])
        self.assertNotIn('ELIGIBLE_TO_ACTIVATE', str(p))

    def test_known_actor_unstructured_event_fails_closed(self):
        with self.assertRaises(Conflict):
            run([row(100, 'please run everything')])

    def test_late_lower_id_unrelated_input_not_lost(self):
        _, state = run([ev(200, 'INPUT', 'higher', outcome='ANSWER')])
        p, _ = run([ev(200, 'INPUT', 'higher', outcome='ANSWER'), ev(150, 'INPUT', 'lower', outcome='ANSWER')], state)
        self.assertEqual({r['input'] for r in p['roles']['BUILDER']['reasons']}, {'higher', 'lower'})


if __name__ == '__main__':
    unittest.main()
