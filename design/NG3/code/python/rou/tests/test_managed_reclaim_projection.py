from __future__ import annotations

from dataclasses import replace
from itertools import combinations, product
import random
import unittest

from rou.binding import LogicalPathId
from rou.confirmed_current_use import ConfirmedCurrentUse, CurrentUseState
from rou.interface_identity import InterfaceIdentity
from rou.managed_device_demand import ManagedOrdinaryContribution
from rou.managed_reclaim_projection import (
    ReclaimProfile, ReclaimReason, project_reclaim,
)
from rou.managed_wireguard_adapter import ManagedWireGuardObservation, ManagedWireGuardState
from rou.release1_config import ManagedReclaimPolicy


CAREFUL = ManagedReclaimPolicy.CAREFUL
STRICT = ManagedReclaimPolicy.STRICT


def obs(d, generation=None, index=None):
    return ManagedWireGuardObservation(
        d, ManagedWireGuardState.PRESENT,
        InterfaceIdentity(d, index if index is not None else ord(d) + 1),
        generation if generation is not None else "g-" + d,
    )


def use(p, d, generation=None, index=None):
    o = obs(d, generation, index)
    return ConfirmedCurrentUse(
        p, CurrentUseState.CONFIRMED, LogicalPathId(d, 0, 0),
        o.interface, o.confirmed_generation, "peer-g", "peer",
    )


def profile(p, target, counts, external=0, current=None):
    return ReclaimProfile(
        p, target, external + sum(counts.values()), external,
        frozenset(counts), frozenset({"external"}) if external else frozenset(),
        tuple(ManagedOrdinaryContribution(d, n) for d, n in counts.items()),
        current if current is not None else ConfirmedCurrentUse(p, CurrentUseState.NONE),
    )


def project(policy, profiles, devices, mandatory=(), observations=None):
    return project_reclaim(
        policy, profiles=tuple(profiles), managed_device_ids=frozenset(devices),
        observations=tuple(obs(d) for d in devices) if observations is None else tuple(observations),
        mandatory_device_ids=frozenset(mandatory),
    )


def ids(rows):
    return {r.device_id for r in rows}


class ReclaimProjectionTests(unittest.TestCase):
    def test_careful_use_is_capacity_not_extra_demand(self):
        p = profile("p", 1, {"a": 1, "b": 1}, current=use("p", "b"))
        r = project(CAREFUL, [p], "ab")
        self.assertEqual(ids(r.survivors), {"b"})
        self.assertEqual(r.survivors[0].reason, ReclaimReason.CURRENT_USE)
        self.assertEqual(ids(r.retirement_candidates), {"a"})
        self.assertEqual(r.retirement_candidates[0].interface, obs("a").interface)
        self.assertEqual(r.retirement_candidates[0].generation, "g-a")
        self.assertEqual(r.deferred, ())

    def test_zero_target_careful_and_strict(self):
        p = profile("p", 0, {"a": 1, "b": 0}, current=use("p", "a"))
        observations = (obs("a"), ManagedWireGuardObservation("b", ManagedWireGuardState.ABSENT))
        c = project(CAREFUL, [p], "ab", observations=observations)
        s = project(STRICT, [p], "ab", observations=observations)
        self.assertEqual(ids(c.survivors), {"a"})
        self.assertEqual(c.retirement_candidates, ())
        self.assertEqual(s.survivors, ())
        self.assertEqual(ids(s.retirement_candidates), {"a"})
        self.assertEqual(c.deferred, s.deferred)
        self.assertEqual(s.deferred, ())

    def test_external_only_and_reserve_only(self):
        p = profile("p", 1, {"a": 1}, external=2)
        r = project(CAREFUL, [p], "ar")
        self.assertEqual(r.floors, (("p", 1),))
        self.assertEqual(ids(r.retirement_candidates), {"a", "r"})
        q = project(CAREFUL, [p], "ar", mandatory={"r"})
        self.assertEqual(ids(q.survivors), {"r"})
        self.assertEqual(q.survivors[0].reason, ReclaimReason.MANDATORY)

    def test_fixed_floor_under_deficit_and_multipath(self):
        p = profile("p", 9, {"a": 3, "b": 2, "c": 1}, external=1)
        r = project(STRICT, [p], "abc")
        self.assertEqual(r.floors, (("p", 7),))
        self.assertEqual(ids(r.survivors), set("abc"))
        self.assertEqual(r.retirement_candidates, ())

    def test_isolated_count_before_use_and_use_before_capacity(self):
        p = profile("p", 2, {"a": 3, "b": 2}, current=use("p", "b"))
        self.assertEqual(ids(project(STRICT, [p], "ab").survivors), {"b"})
        q = profile("p", 3, {"a": 3, "b": 2, "c": 1}, current=use("p", "b"))
        self.assertEqual(ids(project(STRICT, [q], "abc").survivors), {"a"})

    def test_multiple_used_candidates_in_residual_isolated_component(self):
        ps = [
            profile("p", 4, {"a": 3, "b": 2, "c": 2}),
            profile("q", 0, {"b": 2}, current=use("q", "b")),
            profile("r", 0, {"c": 2}, current=use("r", "c")),
        ]
        self.assertEqual(ids(project(STRICT, ps, "abc").survivors), {"b", "c"})

    def test_shared_contribution_and_mandatory_reserve_support(self):
        ps = [profile("p", 2, {"a": 2, "b": 2}),
              profile("q", 1, {"a": 1, "c": 1})]
        r = project(STRICT, ps, "abc")
        self.assertEqual(ids(r.survivors), {"a"})
        r = project(STRICT, ps, "abc", mandatory={"b"})
        self.assertIn("b", ids(r.survivors))
        self.assertEqual(len(r.survivors), 2)

    def test_shared_equal_gain_prefers_used(self):
        ps = [profile("p", 1, {"a": 1, "b": 1}, current=use("p", "b")),
              profile("q", 1, {"a": 1, "b": 1})]
        self.assertEqual(ids(project(STRICT, ps, "ab").survivors), {"b"})

    def test_unknown_and_generation_mismatch_scoped(self):
        q = profile("q", 0, {"c": 1})
        for evidence in (
            ConfirmedCurrentUse("p", CurrentUseState.UNKNOWN),
            use("p", "a", "old-g"),
            use("p", "a", index=999),
            ConfirmedCurrentUse("wrong", CurrentUseState.NONE),
        ):
            p = profile("p", 0, {"a": 1, "b": 1}, current=evidence)
            for policy in (CAREFUL, STRICT):
                r = project(policy, [p, q], "abc")
                self.assertEqual(ids(r.deferred), {"a", "b"})
                self.assertEqual(ids(r.retirement_candidates), {"c"})
                self.assertTrue(all(x.reason is ReclaimReason.USE for x in r.deferred))
        p = replace(profile("p", 0, {"a": 1}), current_use=None)
        self.assertEqual(ids(project(STRICT, [p, q], "ac").deferred), {"a"})

    def test_unknown_use_still_has_independently_confirmed_capacity(self):
        ps = [profile("p", 0, {"a": 1},
                      current=ConfirmedCurrentUse("p", CurrentUseState.UNKNOWN)),
              profile("q", 1, {"a": 1, "b": 1})]
        r = project(STRICT, ps, "ab")
        self.assertEqual(ids(r.deferred), {"a"})
        self.assertEqual(ids(r.retirement_candidates), {"b"})

    def test_bad_identity_not_counted_toward_floor(self):
        p = profile("p", 2, {"a": 2, "b": 2})
        q = profile("q", 0, {"c": 1})
        unknown = replace(obs("a"), confirmed_generation=None)
        r = project(STRICT, [p, q], "abc", observations=[unknown, obs("b"), obs("c")])
        self.assertEqual(ids(r.deferred), {"a"})
        self.assertEqual(ids(r.survivors), {"b"})
        self.assertEqual(ids(r.retirement_candidates), {"c"})
        p = profile("p", 3, {"a": 2, "b": 2})
        r = project(STRICT, [p, q], "abc", observations=[unknown, obs("b"), obs("c")])
        self.assertEqual(ids(r.deferred), {"a", "b"})
        self.assertEqual(ids(r.retirement_candidates), {"c"})

    def test_missing_and_conflicting_observations(self):
        p = profile("p", 0, {"a": 1, "b": 1})
        q = profile("q", 0, {"c": 1})
        for observations in (
            [obs("b"), obs("c")],
            [ManagedWireGuardObservation("a", ManagedWireGuardState.ABSENT), obs("b"), obs("c")],
            [obs("a"), obs("a", "other"), obs("b"), obs("c")],
        ):
            r = project(STRICT, [p, q], "abc", observations=observations)
            self.assertEqual(ids(r.deferred), {"a"})
            self.assertEqual(ids(r.retirement_candidates), {"b", "c"})
        alias = replace(obs("a", index=ord("b") + 1), confirmed_generation=None)
        r = project(STRICT, [p, q], "abc", observations=[alias, obs("b"), obs("c")])
        self.assertEqual(ids(r.deferred), {"a", "b"})
        self.assertEqual(ids(r.retirement_candidates), {"c"})

    def test_bad_contributions_are_scoped(self):
        p = profile("p", 1, {"a": 1, "b": 1})
        q = profile("q", 0, {"c": 1})
        for bad in (
            replace(p, contributions=p.contributions[:1]),
            replace(p, contributions=p.contributions + p.contributions[:1]),
            replace(p, ordinary_present=10),
            replace(p, ordinary_target=True),
        ):
            r = project(STRICT, [bad, q], "abc")
            self.assertEqual(ids(r.deferred), {"a", "b"})
            self.assertEqual(ids(r.retirement_candidates), {"c"})
            self.assertEqual(r.floors, (("q", 0),))

    def test_unidentifiable_envelope_rejects(self):
        p = profile("p", 1, {"a": 1})
        with self.assertRaises(ValueError):
            project(STRICT, [p, p], "a")
        with self.assertRaises(ValueError):
            project(STRICT, [p], "b")
        with self.assertRaises(ValueError):
            project(STRICT, [p], "a", mandatory="b")
        with self.assertRaises(ValueError):
            project("strict", [p], "a")

    def test_deterministic_under_input_permutations(self):
        ps = [profile("p", 2, {"a": 2, "b": 1, "c": 1}, current=use("p", "b")),
              profile("q", 2, {"a": 1, "b": 2, "c": 1})]
        r = project(STRICT, ps, "abc")
        reversed_ps = [replace(p, contributions=tuple(reversed(p.contributions)))
                       for p in reversed(ps)]
        self.assertEqual(project(STRICT, reversed_ps, "cba"), r)

    def test_isolated_bruteforce_oracle(self):
        # All use assignments represented by independent zero-target Profiles;
        # A.004 itself carries at most one use fact per Profile.
        for capacities in product((1, 2, 3), repeat=3):
            ds = "abc"
            counts = dict(zip(ds, capacities))
            for flags in product((False, True), repeat=3):
                sticky = {d for d, flag in zip(ds, flags) if flag}
                use_profiles = [profile("use-" + d, 0, {d: counts[d]},
                                        current=use("use-" + d, d)) for d in sticky]
                for target in range(sum(capacities) + 2):
                    p = profile("p", target, counts)
                    floor = min(target, sum(capacities))
                    options = [set(ss) for k in range(4) for ss in combinations(ds, k)
                               if sum(counts[d] for d in ss) >= floor]
                    expected = min(options, key=lambda ss: (len(ss), -len(ss & sticky), sorted(ss)))
                    actual = ids(project(STRICT, [p, *use_profiles], ds).survivors)
                    self.assertEqual(actual, expected)

    def test_shared_seeded_floor_and_irreducibility(self):
        rng = random.Random(12012)
        ds = "abcde"
        for _ in range(500):
            rows = [{d: rng.randrange(4) for d in ds} for _ in range(3)]
            targets = [rng.randrange(12) for _ in rows]
            externals = [rng.randrange(3) for _ in rows]
            mandatory = {d for d in ds if rng.randrange(5) == 0}
            ps = [profile(str(i), t, row, external=e)
                  for i, (t, row, e) in enumerate(zip(targets, rows, externals))]
            r = project(STRICT, ps, ds, mandatory=mandatory)
            survivors = ids(r.survivors)
            self.assertEqual(r.deferred, ())
            self.assertTrue(mandatory <= survivors)
            self.assertEqual(ids(r.retirement_candidates), set(ds) - survivors)
            floors = [min(t, e + sum(row.values()))
                      for t, row, e in zip(targets, rows, externals)]
            def covers(items):
                return all(e + sum(row[d] for d in items) >= f
                           for row, e, f in zip(rows, externals, floors))
            self.assertTrue(covers(survivors))
            for d in survivors - mandatory:
                self.assertFalse(covers(survivors - {d}))
            self.assertEqual(project(STRICT, list(reversed(ps)), ds[::-1],
                                     mandatory=mandatory), r)


if __name__ == "__main__":
    unittest.main()
