import copy
import unittest

from core import Conflict, canonical, digest, project
from preflight import preflight

ACTOR = 340153730
HOLDER = 114166706
HISTORICAL = '''```json
{
  "protocol": "vpng-collab/0",
  "event_id": "cv0-continuity-c-plan-handled",
  "kind": "HANDLED",
  "room": 34,
  "from": "BUILDER",
  "to": [
    "GUARD"
  ],
  "incarnation": "builder-gpt62-current",
  "payload_ref": "issue:34#issuecomment-7186572370",
  "event_ids": [
    "cv0-continuity-canary-guard-r2",
    "cv0-continuity-c-plan"
  ]
}
```'''


def row(cid, body, actor=ACTOR):
    return {'id': cid, 'user': {'id': actor}, 'body': body}


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'repository': 'a/b', 'event_room': 36, 'task_rooms': [34],
                    'roles': {role: {'actor_id': ACTOR, 'incarnation': inc} for role, inc in
                              [('BUILDER', 'builder-gpt62-current'), ('GUARD', 'guard-gpt56-sol-current')]},
                    'legacy_comments': [9000000000],
                    'projectholder': {'actor_id': HOLDER, 'room': 35, 'route_to': ['GUARD']},
                    'command_registry': {'cycle': 'C', 'capability_scopes': {}, 'condition_keys': [],
                                         'utc_keys': [], 'model_scopes': {}}}
        self.snap = {'36': [], '34': [row(7186572370, 'payload')], '35': [row(5, 'holder input', HOLDER)]}
        self.ob = {'id': 'O', 'revision': 1}

    def event(self, kind, mid, sender='GUARD', to='BUILDER', **kw):
        e = {'protocol': 'vpng-collab/0', 'event_id': mid, 'kind': kind, 'room': 34,
             'from': sender, 'to': [to], 'incarnation': self.cfg['roles'][sender]['incarnation'],
             'payload_ref': 'issue:34#issuecomment-7186572370'}
        e.update(kw)
        return '```json\n' + canonical(e) + '\n```'

    def preview(self, body, actor=ACTOR, previous=None):
        before = copy.deepcopy((self.cfg, self.snap, previous))
        try:
            return preflight(self.cfg, self.snap, actor, body, previous)
        finally:
            self.assertEqual(before, (self.cfg, self.snap, previous))

    def append(self, body):
        result = self.preview(body)
        self.assertEqual(result['body_sha256'], digest(body))
        self.assertEqual(result['event_room'], 36)
        self.assertEqual(result['config_hash'], digest(canonical(self.cfg)))
        self.snap['36'].append(row(100 + len(self.snap['36']), body))
        return result

    def opened(self):
        self.append(self.event('OPEN', 'o', obligation=dict(self.ob, kind='work', assignee='BUILDER', disposition_by='GUARD')))

    def test_all_event_kinds(self):
        self.opened()
        self.append(self.event('BLOCK', 'b', 'BUILDER', 'BUILDER', obligation=self.ob, wait_for_event_id='i'))
        self.append(self.event('DORMANT', 'd', 'BUILDER', 'BUILDER', wait_for_event_id='i'))
        self.append(self.event('INPUT', 'i', obligation=self.ob, outcome='ANSWER'))
        self.append(self.event('HANDLED', 'h', 'BUILDER', 'BUILDER', event_ids=['i']))
        self.append(self.event('HANDLED', 'holder-h', 'GUARD', 'GUARD', event_ids=['holder:5']))
        self.append(self.event('PING', 'p', ping_id='p'))
        self.append(self.event('PONG', 'q', 'BUILDER', 'GUARD', ping_id='p'))
        self.append(self.event('DISPOSITION', 'c', obligation=self.ob, disposition='CLOSED', closure_ref='issue:34#issuecomment-7186572370'))
        result, _ = project(self.cfg, self.snap)
        self.assertEqual(result['obligations'][0]['status'], 'CLOSED')
        self.assertEqual(len(result['health']['matched']), 1)
        self.assertTrue(all(role['state'] == 'WAITING' for role in result['roles'].values()))

    def test_exact_historical_body(self):
        self.assertEqual(digest(HISTORICAL), '629b6989c0b725b58fb231b98a71a264c2158f52fb356746d2c305a7d4c79026')
        for mid in ('cv0-continuity-canary-guard-r2', 'cv0-continuity-c-plan'):
            self.append(self.event('INPUT', mid, outcome='ANSWER'))
        with self.assertRaisesRegex(Conflict, 'self control claim must address self'):
            self.preview(HISTORICAL)

    def test_duplicate_id_requires_reconciliation(self):
        body = self.event('INPUT', 'i', outcome='ANSWER')
        self.append(body)
        for variant in (body, body + '\nchanged note'):
            with self.assertRaisesRegex(Conflict, 'already exists'):
                self.preview(variant)

    def test_exact_body_binding(self):
        body = self.event('INPUT', 'i', outcome='ANSWER')
        a = self.preview(body)
        self.assertEqual(a, self.preview(body))
        b = self.preview(body + '\nchanged note')
        self.assertNotEqual(a['body_sha256'], b['body_sha256'])
        self.assertEqual(a['observation_sha256'], b['observation_sha256'])
        self.assertEqual((a['event_id'], a['kind']), ('i', 'INPUT'))

    def test_orphan_and_wrong_pong(self):
        with self.assertRaisesRegex(Conflict, 'missing admitted PING'):
            self.preview(self.event('PONG', 'q', 'BUILDER', 'GUARD', ping_id='p'))
        self.append(self.event('PING', 'p', ping_id='p'))
        with self.assertRaisesRegex(Conflict, 'room/role mismatch'):
            self.preview(self.event('PONG', 'q', ping_id='p'))

    def test_wrong_handled(self):
        self.append(self.event('INPUT', 'i', outcome='ANSWER'))
        with self.assertRaisesRegex(Conflict, 'non-addressed input'):
            self.preview(self.event('HANDLED', 'h', 'GUARD', 'GUARD', event_ids=['i']))

    def test_wrong_revision_and_disposition(self):
        self.opened()
        with self.assertRaisesRegex(Conflict, 'unknown obligation/revision'):
            self.preview(self.event('BLOCK', 'b', 'BUILDER', 'BUILDER', obligation=dict(self.ob, revision=2), wait_for_event_id='i'))
        with self.assertRaisesRegex(Conflict, 'not from configured closer'):
            self.preview(self.event('DISPOSITION', 'c', 'BUILDER', 'BUILDER', obligation=self.ob, disposition='CLOSED', closure_ref='issue:34#issuecomment-7186572370'))

    def test_wrong_actor_and_payload(self):
        body = self.event('INPUT', 'i', outcome='ANSWER')
        with self.assertRaisesRegex(Conflict, 'outgoing actor'):
            self.preview(body, actor=HOLDER)
        self.snap['34'][0]['user']['id'] = HOLDER
        with self.assertRaisesRegex(Conflict, 'payload actor mismatch'):
            self.preview(body)
        self.snap['34'].clear()
        with self.assertRaisesRegex(Conflict, 'missing or wrong-room payload'):
            self.preview(body)

    def test_previous_ledger_and_poisoned_observation(self):
        self.append(self.event('INPUT', 'i', outcome='ANSWER'))
        _, state = project(self.cfg, self.snap)
        body = self.event('INPUT', 'j', outcome='ANSWER')
        self.preview(body, previous=state)
        self.snap['36'].clear()
        with self.assertRaisesRegex(Conflict, 'prior observed comment missing'):
            self.preview(body, previous=state)
        self.snap['36'].append(row(101, HISTORICAL))
        with self.assertRaisesRegex(Conflict, 'self control claim'):
            self.preview(body)

    def test_missing_snapshot_and_stale_config(self):
        _, state = project(self.cfg, self.snap)
        body = self.event('INPUT', 'i', outcome='ANSWER')
        self.cfg['command_registry']['cycle'] = 'D'
        with self.assertRaisesRegex(Conflict, 'state/config mismatch'):
            self.preview(body, previous=state)
        del self.snap['35']
        with self.assertRaisesRegex(Conflict, 'missing or unexpected room'):
            self.preview(body)


if __name__ == '__main__':
    unittest.main()
