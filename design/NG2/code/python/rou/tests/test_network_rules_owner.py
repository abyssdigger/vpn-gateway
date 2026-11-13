import gc
import unittest
import weakref

from rou.network_rules import NetworkRulesSpec
from rou.network_rules_owner import DesiredRulesByOwner


class EqualOwner:
    def __eq__(self, other):
        return isinstance(other, EqualOwner)

    def __hash__(self):
        return 1


class OwnerRegistryTests(unittest.TestCase):
    def test_equal_objects_remain_distinct_owners(self):
        registry = DesiredRulesByOwner()
        first = EqualOwner()
        second = EqualOwner()
        first_rules = NetworkRulesSpec()
        second_rules = NetworkRulesSpec()

        self.assertEqual(first, second)
        registry.replace(first, first_rules)
        registry.replace(second, second_rules)

        self.assertEqual(len(registry), 2)
        self.assertIs(registry.get(first), first_rules)
        self.assertIs(registry.get(second), second_rules)

    def test_replacing_same_owner_does_not_create_new_scope(self):
        registry = DesiredRulesByOwner()
        owner = EqualOwner()
        first = NetworkRulesSpec()
        second = NetworkRulesSpec()

        registry.replace(owner, first)
        registry.replace(owner, second)

        self.assertEqual(len(registry), 1)
        self.assertIs(registry.get(owner), second)

    def test_remove_is_idempotent_at_registry_level(self):
        registry = DesiredRulesByOwner()
        owner = EqualOwner()
        registry.replace(owner, NetworkRulesSpec())

        self.assertTrue(registry.remove(owner))
        self.assertFalse(registry.remove(owner))
        self.assertIsNone(registry.get(owner))

    def test_registry_keeps_owner_identity_alive_until_remove(self):
        registry = DesiredRulesByOwner()
        owner = EqualOwner()
        reference = weakref.ref(owner)
        registry.replace(owner, NetworkRulesSpec())

        del owner
        gc.collect()
        self.assertIsNotNone(reference())

        retained = reference()
        assert retained is not None
        registry.remove(retained)
        del retained
        gc.collect()

        self.assertIsNone(reference())

    def test_desired_sets_keep_owner_policies_separate(self):
        registry = DesiredRulesByOwner()
        first = EqualOwner()
        second = EqualOwner()
        first_rules = NetworkRulesSpec()
        second_rules = NetworkRulesSpec()

        registry.replace(first, first_rules)
        registry.replace(second, second_rules)

        desired = registry.desired_sets()
        self.assertEqual(len(desired), 2)
        self.assertIs(desired[0], first_rules)
        self.assertIs(desired[1], second_rules)


if __name__ == "__main__":
    unittest.main()
