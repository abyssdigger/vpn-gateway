import copy
import dataclasses
import hashlib
import unittest

from core import Observation, Rejected, Result, attempt, candidate_digest


class Fake:
    def __init__(self, before, after=None, delete_error=False):
        self.before, self.after, self.delete_error = before, after, delete_error
        self.reads, self.deletes = [], []

    def read_exact(self, *target):
        self.reads.append(target)
        value = self.before if not self.deletes else self.after
        if isinstance(value, Exception):
            raise value
        return value

    def delete_exact(self, *target):
        self.deletes.append(target)
        if self.delete_error:
            raise OSError('ambiguous mutation')


class JanitorTests(unittest.TestCase):
    def setUp(self):
        self.scope = {'repository': 'a/b', 'signal_room': 37}
        self.target = ('a/b', 37, 91)
        self.obs = Observation(*self.target, 10, 'exact signal\n')
        self.candidate = {'physical_ref': 'issue:37#issuecomment-91', 'actor_id': 10,
                          'body_sha256': hashlib.sha256(b'exact signal\n').hexdigest(),
                          'signal_id': 'sig', 'event_id': 'fact',
                          'journal_ref': 'issue:34#issuecomment-81', 'journal_sha256': 'a'*64,
                          'recipient': 'BUILDER', 'receipt_refs': ['issue:34#issuecomment-82']}
        self.permit = dict(self.scope, candidate_sha256=candidate_digest(self.candidate))

    def run_attempt(self, fake, status, count):
        before = copy.deepcopy((self.scope, self.candidate, self.permit))
        self.assertEqual(attempt(self.scope, self.candidate, self.permit, fake), Result(status, count))
        self.assertEqual(len(fake.deletes), count)
        self.assertEqual(len(fake.reads), 1 + count)
        self.assertTrue(all(target == self.target for target in fake.reads + fake.deletes))
        self.assertEqual(before, (self.scope, self.candidate, self.permit))

    def assert_rejected(self, scope, candidate, permit):
        f = Fake(self.obs)
        with self.assertRaises(Rejected):
            attempt(scope, candidate, permit, f)
        self.assertEqual((f.reads, f.deletes), ([], []))

    def test_exact(self):
        self.run_attempt(Fake(self.obs), 'CONFIRMED_ABSENT_AFTER_ATTEMPT', 1)

    def test_absent(self):
        self.run_attempt(Fake(None), 'ALREADY_ABSENT', 0)

    def test_stale(self):
        for key, val in [('repository','a/c'), ('room',34), ('comment_id',92),
                         ('actor_id',11), ('body','edited'), ('room',True)]:
            with self.subTest(key=key, value=val):
                self.run_attempt(Fake(dataclasses.replace(self.obs, **{key: val})), 'STALE', 0)

    def test_ambiguous_then_absent(self):
        self.run_attempt(Fake(self.obs, delete_error=True), 'CONFIRMED_ABSENT_AFTER_ATTEMPT', 1)

    def test_present_after_attempt(self):
        for exc in (False, True):
            for after in (self.obs, dataclasses.replace(self.obs, body='changed'), OSError('read failed')):
                with self.subTest(exc=exc, after=after):
                    self.run_attempt(Fake(self.obs, after, exc), 'UNCERTAIN', 1)

    def test_read_failure(self):
        self.run_attempt(Fake(OSError('read failed')), 'UNCERTAIN', 0)

    def test_repeated_caller(self):
        fake = Fake(self.obs)
        self.assertEqual(attempt(self.scope, self.candidate, self.permit, fake),
                         Result('CONFIRMED_ABSENT_AFTER_ATTEMPT', 1))
        self.assertEqual(attempt(self.scope, self.candidate, self.permit, fake), Result('ALREADY_ABSENT', 0))
        self.assertEqual(fake.deletes, [self.target])

    def test_invalid_permit(self):
        for permit in (None, {}, dict(self.permit, repository='a/c'),
                       dict(self.permit, signal_room=34), dict(self.permit, signal_room=True),
                       dict(self.permit, candidate_sha256='b'*64), dict(self.permit, extra=True)):
            self.assert_rejected(self.scope, self.candidate, permit)

    def test_entire_candidate_bound(self):
        for key, value in [('receipt_refs',['issue:34#issuecomment-83']),
                           ('journal_ref','issue:34#issuecomment-84'),
                           ('journal_sha256','c'*64), ('recipient','GUARD'),
                           ('signal_id','sig2'), ('event_id','fact2'), ('actor_id',11),
                           ('body_sha256','d'*64), ('physical_ref','issue:37#issuecomment-92')]:
            self.assert_rejected(self.scope, dict(self.candidate, **{key:value}), self.permit)

    def test_bad_candidate_even_with_matching_digest(self):
        variants = [dict(self.candidate, **{key:value}) for key, value in [
            ('physical_ref','issue:34#issuecomment-91'), ('physical_ref','https://github.com/a/b'),
            ('physical_ref','issue:37#issuecomment-091'), ('actor_id',True), ('actor_id',0),
            ('body_sha256','A'*64), ('journal_sha256',9), ('signal_id',''), ('event_id',[]),
            ('journal_ref','issue:37#issuecomment-81'), ('receipt_refs',[]),
            ('receipt_refs',['issue:37#issuecomment-82']), ('receipt_refs',['invalid']),
            ('receipt_refs',[[]]), ('receipt_refs',['issue:34#issuecomment-82']*2),
            ('recipient','bad role')]]
        variants.append(dict(self.candidate, extra='surprise'))
        for c in variants:
            with self.subTest(candidate=c):
                self.assert_rejected(self.scope, c, dict(self.scope, candidate_sha256=candidate_digest(c)))

    def test_scope(self):
        for scope in ({}, {'repository':'../b','signal_room':37}, {'repository':'a/b','signal_room':True},
                      {'repository':'https://a/b','signal_room':37}, {'repository':'a/b','signal_room':34}):
            self.assert_rejected(scope, self.candidate, dict(scope, candidate_sha256=candidate_digest(self.candidate)))

    def test_canonical_digest(self):
        self.assertEqual(candidate_digest(self.candidate), candidate_digest(dict(reversed(list(self.candidate.items())))))
        self.assertNotEqual(candidate_digest(self.candidate), candidate_digest(dict(self.candidate, recipient='GUARD')))


if __name__ == '__main__':
    unittest.main()
