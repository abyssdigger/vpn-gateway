import json
import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_host_bootstrap import (
    HostBootstrapBypassRuleSpec,
    HostBootstrapDispatchRuleSpec,
    HostBootstrapLinuxAllocation,
    HostBootstrapLinuxDesired,
    HostBootstrapPreserveRuleSpec,
    HostBootstrapRouteSpec,
    HostBootstrapRulePair,
)
from rou.linux_host_bootstrap_backend import LinuxHostBootstrapBackend
from rou.network_policy_layout import NumericResourcePool


class Runner:
    def __init__(self,routes="[]",rules="[]"):
        self.routes=routes; self.rules=rules; self.calls=[]
    def run(self,argv):
        self.calls.append(tuple(argv))
        if "rule" in argv and "show" in argv:
            return self.rules
        if "route" in argv and "show" in argv:
            return self.routes
        return ""


def allocation():
    return HostBootstrapLinuxAllocation(
        table=2147418114,
        bypass_priority=6400,
        pair_priorities=NumericResourcePool(8192,12288),
        rule_protocol=203,
        route_protocol=203,
    )


def desired():
    route=HostBootstrapRouteSpec(
        destination=IPv4Network("10.0.0.0/8"),
        via=IPv4Address("198.19.255.2"),
        interface="vnga-host0",table=allocation().table,protocol=203,
    )
    return HostBootstrapLinuxDesired(
        routes=(route,),
        bypass=HostBootstrapBypassRuleSpec(priority=6400,interface="vnga-host0",protocol=203),
        pairs=(
            HostBootstrapRulePair(
                preserve=HostBootstrapPreserveRuleSpec(
                    priority=8192,destination=IPv4Network("10.0.0.0/8"),
                    suppress_prefixlen=8,protocol=203,
                ),
                dispatch=HostBootstrapDispatchRuleSpec(
                    priority=8193,destination=IPv4Network("10.0.0.0/8"),
                    table=allocation().table,protocol=203,
                ),
            ),
        ),
    )


class LinuxHostBootstrapBackendTests(unittest.TestCase):
    def test_exact_kernel_json_is_observed(self):
        d=desired()
        routes=json.dumps([{
            "dst":"10.0.0.0/8","gateway":"198.19.255.2","dev":"vnga-host0",
            "protocol":203,"table":allocation().table,
        }])
        rules=json.dumps([
            {"priority":0,"src":"all","table":255},
            {"priority":6400,"src":"all","iif":"vnga-host0","table":254,"protocol":203},
            {"priority":8192,"src":"all","dst":"10.0.0.0/8","table":254,
             "protocol":203,"suppress_prefixlen":8},
            {"priority":8193,"src":"all","dst":"10.0.0.0/8","table":allocation().table,
             "protocol":203},
            {"priority":32766,"src":"all","table":254},
        ])
        observed=LinuxHostBootstrapBackend(Runner(routes,rules),allocation()).observe(d)
        self.assertTrue(observed.exact)
        self.assertEqual(observed.conflicts,())

    def test_foreign_rule_at_reserved_priority_is_conflict(self):
        rules=json.dumps([
            {"priority":8192,"src":"all","dst":"10.0.0.0/8","table":254,
             "protocol":99,"suppress_prefixlen":8},
        ])
        observed=LinuxHostBootstrapBackend(Runner("[]",rules),allocation()).observe(desired())
        self.assertIn("foreign rule", "; ".join(observed.conflicts))

    def test_foreign_rule_at_unused_pool_priority_is_not_claimed(self):
        rules=json.dumps([
            {"priority":9000,"src":"all","table":100,"protocol":99},
        ])
        observed=LinuxHostBootstrapBackend(Runner("[]",rules),allocation()).observe(desired())
        self.assertEqual(observed.conflicts,())
        self.assertNotIn(9000,observed.rule_priorities)

    def test_driver_commands_include_owner_protocol(self):
        runner=Runner()
        backend=LinuxHostBootstrapBackend(runner,allocation())
        d=desired()
        backend.add_route(d.routes[0])
        backend.add_bypass_rule(d.bypass)
        backend.add_preserve_rule(d.pairs[0].preserve)
        backend.add_dispatch_rule(d.pairs[0].dispatch)
        self.assertIn(
            ("ip","-4","rule","add","priority","8192","protocol","203",
             "to","10.0.0.0/8","lookup","main","suppress_prefixlength","8"),
            runner.calls,
        )
        self.assertIn(
            ("ip","-4","route","add","table",str(allocation().table),"10.0.0.0/8",
             "via","198.19.255.2","dev","vnga-host0","proto","203"),
            runner.calls,
        )

    def test_stale_owner_rule_is_not_foreign_conflict(self):
        rules=json.dumps([
            {"priority":8192,"src":"all","dst":"192.0.2.0/24","table":254,
             "protocol":203,"suppress_prefixlen":24},
        ])
        observed=LinuxHostBootstrapBackend(Runner("[]",rules),allocation()).observe(desired())
        self.assertEqual(observed.conflicts,())
        self.assertIn(8192,observed.rule_priorities)
        self.assertIn(8192,observed.stale_rule_priorities)
        self.assertIn(8192,observed.missing_rule_priorities)


if __name__=="__main__":
    unittest.main()
