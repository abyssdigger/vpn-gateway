import importlib.util
from pathlib import Path
import unittest
import sys

MODPATH = Path(__file__).resolve().parents[1] / 'rou_v0.py'
spec = importlib.util.spec_from_file_location('rou_v0', MODPATH)
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


class ProjectionTests(unittest.TestCase):
    def bid(self, name, idx):
        return r.BindingId(name, idx)

    def test_first_two_admitted_by_observation_order(self):
        p = r.project_bindings([self.bid('vpns00', 10), self.bid('vpns01', 11)], (), 0)
        self.assertEqual([(a.identity.ifname, a.metric) for a in p.admitted], [('vpns00', 10), ('vpns01', 20)])
        self.assertEqual(p.overflow, ())

    def test_overflow_does_not_evict_survivors(self):
        committed = (
            r.Assignment(self.bid('vpns00', 10), 10),
            r.Assignment(self.bid('vpns01', 11), 20),
        )
        p = r.project_bindings([self.bid('vpns00', 10), self.bid('vpns01', 11), self.bid('vpns02', 12)], committed, 0)
        self.assertEqual(p.admitted, committed)
        self.assertEqual(p.overflow, (self.bid('vpns02', 12),))

    def test_removed_metric_not_reused_same_transition(self):
        committed = (
            r.Assignment(self.bid('vpns00', 10), 10),
            r.Assignment(self.bid('vpns01', 11), 20),
        )
        p = r.project_bindings([self.bid('vpns01', 11), self.bid('vpns02', 12)], committed, 0)
        self.assertEqual([(a.identity.ifname, a.metric) for a in p.admitted], [('vpns01', 20)])
        self.assertEqual(p.overflow, (self.bid('vpns02', 12),))
        p2 = r.project_bindings([self.bid('vpns01', 11), self.bid('vpns02', 12)], p.admitted, p.next_cursor)
        self.assertEqual([(a.identity.ifname, a.metric) for a in p2.admitted], [('vpns01', 20), ('vpns02', 10)])

    def test_same_name_new_ifindex_is_fresh_binding(self):
        committed = (r.Assignment(self.bid('vpns00', 10), 10),)
        p = r.project_bindings([self.bid('vpns00', 99)], committed, 0)
        self.assertEqual([(a.identity.ifindex, a.metric) for a in p.admitted], [(99, 20)])
        self.assertEqual(p.overflow, ())
        self.assertNotEqual(p.admitted[0].identity, committed[0].identity)

    def test_zero_binding_projection(self):
        committed = (r.Assignment(self.bid('vpns00', 10), 10),)
        p = r.project_bindings([], committed, 0)
        self.assertEqual(p.admitted, ())
        self.assertEqual(p.overflow, ())


class BootstrapTests(unittest.TestCase):
    def test_absent_profile_table_flush_is_benign_only_for_known_kernel_error(self):
        calls = []
        original = r.run

        class P:
            def __init__(self, rc, stderr):
                self.returncode = rc
                self.stdout = ""
                self.stderr = stderr

        try:
            r.run = lambda *a, **kw: P(2, "Error: ipv4: FIB table does not exist.\nFlush terminated\n")
            r.flush_profile_table()

            r.run = lambda *a, **kw: P(2, "RTNETLINK answers: Operation not permitted\n")
            with self.assertRaises(r.RouError):
                r.flush_profile_table()
        finally:
            r.run = original


class DesiredStateTests(unittest.TestCase):
    def test_zero_binding_routes_are_fail_closed(self):
        cmds = r.desired_routes(())
        text = [' '.join(c) for c in cmds]
        self.assertTrue(any('blackhole ' + r.PROFILE_TARGET in x for x in text))
        self.assertTrue(any('blackhole default' in x for x in text))
        self.assertFalse(any(' proto 202 ' in (' ' + x + ' ') for x in text))

    def test_firewall_zero_binding_forward_drop(self):
        fw = r.firewall_restore(())
        self.assertIn(':FORWARD DROP', fw)
        self.assertNotIn(' -o vpns', fw)

    def test_firewall_one_binding_is_one_way_new(self):
        a = (r.Assignment(r.BindingId('vpns00', 10), 10),)
        fw = r.firewall_restore(a)
        self.assertIn('-i host0 -o vpns00 -m conntrack --ctstate NEW,ESTABLISHED,RELATED -j ACCEPT', fw)
        self.assertIn('-i vpns00 -o host0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT', fw)
        self.assertNotIn('-i vpns00 -o host0 -m conntrack --ctstate NEW', fw)
        self.assertIn('-o vpns00 -m addrtype ! --dst-type LOCAL -j MASQUERADE', fw)


if __name__ == '__main__':
    unittest.main()
