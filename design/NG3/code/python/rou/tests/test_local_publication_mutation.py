from __future__ import annotations

import unittest
from ipaddress import IPv4Address

from rou.interface_identity import InterfaceIdentity
from rou.local_publication_mutation import (
    LocalPublicationDeleteRef,
    select_local_publication_step,
)
from rou.local_publication_observation import (
    LocalPublicationComparison,
    ObservedLocalPublicationRule,
)
from rou.local_publication_policy import (
    LocalPublicationDesiredState,
    LocalPublicationHook,
    LocalPublicationRuleSpec,
    PublicationProtocol,
)


HOST = InterfaceIdentity("host0", 10)
NEW_HOST = InterfaceIdentity("host0", 20)
ADDR = IPv4Address("198.51.100.47")


def spec(hook: LocalPublicationHook, *, host=HOST):
    return LocalPublicationRuleSpec(
        hook=hook,
        protocol=PublicationProtocol.TCP,
        host_boundary=host,
        local_address=ADDR,
        local_port=44443,
    )


class LocalPublicationMutationPlanTests(unittest.TestCase):
    def test_exact_state_has_no_step(self):
        desired = LocalPublicationDesiredState(
            (spec(LocalPublicationHook.INPUT), spec(LocalPublicationHook.OUTPUT))
        )
        comparison = LocalPublicationComparison(
            confirmed=desired.rules,
            missing=(),
            stale=(),
            conflicts=(),
        )
        self.assertIsNone(
            select_local_publication_step(comparison, desired)
        )

    def test_stale_endpoint_deletes_all_stale_hooks_together(self):
        stale = (
            ObservedLocalPublicationRule(
                handle=41,
                hook=LocalPublicationHook.INPUT,
                protocol=PublicationProtocol.TCP,
                host_boundary=10,
                local_address=ADDR,
                local_port=44443,
            ),
            ObservedLocalPublicationRule(
                handle=42,
                hook=LocalPublicationHook.OUTPUT,
                protocol=PublicationProtocol.TCP,
                host_boundary=10,
                local_address=ADDR,
                local_port=44443,
            ),
        )
        desired = LocalPublicationDesiredState(
            (
                spec(LocalPublicationHook.INPUT, host=NEW_HOST),
                spec(LocalPublicationHook.OUTPUT, host=NEW_HOST),
            )
        )
        comparison = LocalPublicationComparison(
            confirmed=(),
            missing=desired.rules,
            stale=stale,
            conflicts=(),
        )
        step = select_local_publication_step(comparison, desired)
        self.assertEqual(
            step.delete_rules,
            (
                LocalPublicationDeleteRef(LocalPublicationHook.INPUT, 41),
                LocalPublicationDeleteRef(LocalPublicationHook.OUTPUT, 42),
            ),
        )
        self.assertEqual(
            step.add_rules,
            (
                spec(LocalPublicationHook.OUTPUT, host=NEW_HOST),
                spec(LocalPublicationHook.INPUT, host=NEW_HOST),
            ),
        )


    def test_full_diff_combines_all_stale_and_missing_rules(self):
        stale = (
            ObservedLocalPublicationRule(
                handle=51,
                hook=LocalPublicationHook.INPUT,
                protocol=PublicationProtocol.TCP,
                host_boundary=HOST,
                local_address=ADDR,
                local_port=44442,
            ),
            ObservedLocalPublicationRule(
                handle=52,
                hook=LocalPublicationHook.OUTPUT,
                protocol=PublicationProtocol.TCP,
                host_boundary=HOST,
                local_address=ADDR,
                local_port=44442,
            ),
        )
        desired = LocalPublicationDesiredState(
            (
                spec(LocalPublicationHook.INPUT),
                spec(LocalPublicationHook.OUTPUT),
            )
        )
        comparison = LocalPublicationComparison(
            confirmed=(),
            missing=desired.rules,
            stale=stale,
            conflicts=(),
        )
        step = select_local_publication_step(comparison, desired)
        self.assertEqual(
            step.delete_rules,
            (
                LocalPublicationDeleteRef(LocalPublicationHook.INPUT, 51),
                LocalPublicationDeleteRef(LocalPublicationHook.OUTPUT, 52),
            ),
        )
        self.assertEqual(set(step.add_rules), set(desired.rules))

    def test_missing_pair_is_added_in_one_endpoint_transaction(self):
        desired = LocalPublicationDesiredState(
            (spec(LocalPublicationHook.INPUT), spec(LocalPublicationHook.OUTPUT))
        )
        comparison = LocalPublicationComparison(
            confirmed=(),
            missing=desired.rules,
            stale=(),
            conflicts=(),
        )
        step = select_local_publication_step(comparison, desired)
        self.assertEqual(step.delete_rules, ())
        self.assertEqual(
            [rule.hook for rule in step.add_rules],
            [LocalPublicationHook.OUTPUT, LocalPublicationHook.INPUT],
        )

    def test_partial_missing_repairs_only_missing_hook(self):
        desired = LocalPublicationDesiredState(
            (spec(LocalPublicationHook.INPUT), spec(LocalPublicationHook.OUTPUT))
        )
        comparison = LocalPublicationComparison(
            confirmed=(spec(LocalPublicationHook.OUTPUT),),
            missing=(spec(LocalPublicationHook.INPUT),),
            stale=(),
            conflicts=(),
        )
        step = select_local_publication_step(comparison, desired)
        self.assertEqual(step.delete_rules, ())
        self.assertEqual(
            [rule.hook for rule in step.add_rules],
            [LocalPublicationHook.INPUT],
        )

    def test_conflict_blocks_plan(self):
        desired = LocalPublicationDesiredState(())
        comparison = LocalPublicationComparison(
            confirmed=(),
            missing=(),
            stale=(),
            conflicts=(object(),),  # type: ignore[arg-type]
        )
        with self.assertRaisesRegex(Exception, "conflicts"):
            select_local_publication_step(comparison, desired)


if __name__ == "__main__":
    unittest.main()
