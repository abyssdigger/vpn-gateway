"""One bounded wait attempt; no semantic dependency or health progression."""
import copy
import unittest

from core import Conflict
from v2_peer_wait import advance_peer_wait, WAIT_MS


class PeerWaitTests(unittest.TestCase):
    def setUp(self):
        self.d = {"role": "BUILDER", "incarnation": "b", "peer": "GUARD",
                  "dependency_key": "unit7c-C.review.r1", "wait_token": "wait-1"}

    def advance(self, descriptor, previous, now):
        frozen = copy.deepcopy((descriptor, previous))
        result = advance_peer_wait(descriptor, previous, now)
        self.assertEqual((descriptor, previous), frozen)
        return result

    def test_exact_boundary_once_and_same_now(self):
        s, intents = self.advance(self.d, None, 500)
        self.assertFalse(s["expired"])
        self.assertEqual(intents, [])
        s, intents = self.advance(self.d, s, 500 + WAIT_MS - 1)
        self.assertEqual(intents, [])
        s, intents = self.advance(self.d, s, 500 + WAIT_MS)
        self.assertTrue(s["expired"])
        self.assertEqual(intents, [dict(self.d, kind="PEER_WAIT_BUDGET_EXPIRED")])
        unchanged, intents = self.advance(self.d, s, s["last_now_ms"])
        self.assertEqual(unchanged, s)
        self.assertEqual(intents, [])
        later, intents = self.advance(self.d, s, 10_000_000)
        self.assertTrue(later["expired"])
        self.assertEqual(intents, [])

    def test_clock_rejects_bool_noninteger_negative_and_backwards(self):
        s, _ = self.advance(self.d, None, 500)
        for now in (True, 500.0, "500", None, -1, 499):
            with self.subTest(now=now), self.assertRaises(Conflict):
                self.advance(self.d, s, now)
        for now in (False, -1, 0.0):
            with self.assertRaises(Conflict):
                self.advance(self.d, None, now)

    def test_every_descriptor_field_bound(self):
        s, _ = self.advance(self.d, None, 0)
        for field in self.d:
            with self.subTest(field=field), self.assertRaises(Conflict):
                self.advance(dict(self.d, **{field: "other"}), s, 1)

    def test_closed_descriptor_and_strict_identifiers(self):
        invalid = [None, [], dict(self.d, extra="x"),
                   dict(self.d, peer=self.d["role"])]
        for field in self.d:
            missing = dict(self.d)
            del missing[field]
            invalid.append(missing)
            for value in ("", "a b", "x"*129, "a\n", 7, None, "../x"):
                invalid.append(dict(self.d, **{field: value}))
        for d in invalid:
            with self.subTest(d=d), self.assertRaises(Conflict):
                self.advance(d, None, 0)

    def test_restart_and_explicit_new_wait_same_dependency(self):
        old, _ = self.advance(self.d, None, 0)
        old, _ = self.advance(self.d, old, WAIT_MS)
        next_d = dict(self.d, wait_token="wait-2")
        with self.assertRaises(Conflict):
            self.advance(next_d, old, WAIT_MS + 1)
        fresh, intents = self.advance(next_d, None, 8_000_000)
        self.assertFalse(fresh["expired"])
        self.assertEqual(intents, [])
        fresh, intents = self.advance(next_d, fresh, 8_000_000 + WAIT_MS - 1)
        self.assertEqual(intents, [])
        fresh, intents = self.advance(next_d, fresh, 8_000_000 + WAIT_MS)
        self.assertEqual(intents, [dict(next_d, kind="PEER_WAIT_BUDGET_EXPIRED")])
        restart, intents = self.advance(next_d, None, 99_000_000)
        self.assertFalse(restart["expired"])
        self.assertEqual(restart["baseline_ms"], 99_000_000)
        self.assertEqual(intents, [])

    def test_return_is_detached_and_closed(self):
        s, _ = self.advance(self.d, None, 0)
        new, intents = self.advance(self.d, s, WAIT_MS)
        self.assertEqual(set(new), {"descriptor", "baseline_ms", "last_now_ms", "expired"})
        self.assertEqual(set(intents[0]), set(self.d) | {"kind"})
        new["descriptor"]["peer"] = "SPEC"
        intents[0]["peer"] = "other"
        self.assertEqual(s["descriptor"], self.d)
        self.assertEqual(self.d["peer"], "GUARD")

    def test_prior_state_closed_and_consistent(self):
        s, _ = self.advance(self.d, None, 10)
        invalid = [[], {}, dict(s, extra=1), dict(s, descriptor={}),
                   dict(s, baseline_ms=11), dict(s, expired=True),
                   dict(s, last_now_ms=10+WAIT_MS)]
        for field in s:
            missing = dict(s)
            del missing[field]
            invalid.append(missing)
        for field in ("baseline_ms", "last_now_ms"):
            for value in (True, 10.0, -1, "10", None):
                invalid.append(dict(s, **{field: value}))
        for value in (0, 1, None, "false"):
            invalid.append(dict(s, expired=value))
        for state in invalid:
            with self.subTest(state=state), self.assertRaises(Conflict):
                self.advance(self.d, state, 10+WAIT_MS)
        s["descriptor"]["peer"] = "SPEC"
        with self.assertRaises(Conflict):
            self.advance(self.d, s, 10+WAIT_MS)

    def test_expired_prior_cannot_be_reset_or_forged_early(self):
        s, _ = self.advance(self.d, None, 0)
        s, _ = self.advance(self.d, s, WAIT_MS)
        for state in (dict(s, expired=False), dict(s, last_now_ms=WAIT_MS-1)):
            with self.assertRaises(Conflict):
                self.advance(self.d, state, WAIT_MS)
