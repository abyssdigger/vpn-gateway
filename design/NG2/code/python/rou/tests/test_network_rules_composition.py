from ipaddress import IPv4Network
import gc
import unittest
import weakref

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    DispatchRuleSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalDisposition,
    TrafficProtocol,
)
from rou.network_rules_composition import (
    NetworkRulesCompositionError,
    OwnedNetworkRules,
    OwnerRulesRegistry,
    OwnerToken,
    compose_network_rules,
)


class EqualOwner:
    def __eq__(self, other):
        return isinstance(other, EqualOwner)

    def __hash__(self):
        return 1


def _spec(
    domain: str,
    destination: str,
    *,
    source=None,
) -> NetworkRulesSpec:
    network = IPv4Network(destination)
    if source is None:
        source = NetworkEndpoint.local_network()
    return NetworkRulesSpec(
        routing_domains=(
            RoutingDomainSpec(
                name=domain,
                destinations=(network,),
                ordered_paths=(),
                terminal_disposition=TerminalDisposition.DROP,
            ),
        ),
        dispatch_rules=(
            DispatchRuleSpec(
                destination=network,
                routing_domain=domain,
                source=source,
            ),
        ),
    )


class OwnerRulesRegistryTests(unittest.TestCase):
    def test_equal_but_distinct_objects_get_distinct_tokens(self):
        registry = OwnerRulesRegistry()
        first = EqualOwner()
        second = EqualOwner()

        first_token = registry.replace(first, NetworkRulesSpec())
        second_token = registry.replace(second, NetworkRulesSpec())

        self.assertNotEqual(first_token, second_token)
        self.assertEqual(first, second)

    def test_replacing_same_identity_preserves_token(self):
        registry = OwnerRulesRegistry()
        owner = object()

        first = registry.replace(owner, NetworkRulesSpec())
        second_rules = _spec("corp", "10.0.0.0/8")
        second = registry.replace(owner, second_rules)

        self.assertEqual(first, second)
        self.assertEqual(
            registry.snapshot(),
            (OwnedNetworkRules(first, second_rules),),
        )

    def test_ensure_registers_identity_without_committed_rules(self):
        registry = OwnerRulesRegistry()
        owner = object()

        token = registry.ensure(owner)

        self.assertEqual(token, OwnerToken(1))
        self.assertTrue(registry.has_identity(owner))
        self.assertEqual(
            registry.registered_rules(),
            ((token, None),),
        )
        self.assertEqual(registry.snapshot(), ())

    def test_preview_replace_does_not_commit_candidate_rules(self):
        registry = OwnerRulesRegistry()
        owner = object()
        old = _spec("old", "10.0.0.0/8")
        new = _spec("new", "192.168.0.0/16")
        token = registry.replace(owner, old)

        preview_token, preview = registry.preview_replace(owner, new)

        self.assertEqual(preview_token, token)
        self.assertEqual(
            preview,
            (OwnedNetworkRules(token, new),),
        )
        self.assertEqual(
            registry.snapshot(),
            (OwnedNetworkRules(token, old),),
        )

    def test_preview_remove_does_not_remove_committed_owner(self):
        registry = OwnerRulesRegistry()
        owner = object()
        rules = _spec("a", "10.0.0.0/8")
        token = registry.replace(owner, rules)

        preview = registry.preview_remove(owner)

        self.assertEqual(preview, ())
        self.assertEqual(
            registry.snapshot(),
            (OwnedNetworkRules(token, rules),),
        )

    def test_cleanup_then_readd_gets_fresh_token(self):
        registry = OwnerRulesRegistry()
        owner = object()

        first = registry.replace(owner, NetworkRulesSpec())
        self.assertTrue(registry.remove(owner))
        second = registry.replace(owner, NetworkRulesSpec())

        self.assertGreater(second.value, first.value)

    def test_registry_holds_owner_identity_strongly_until_remove(self):
        registry = OwnerRulesRegistry()
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

    def test_remove_unknown_owner_is_idempotent(self):
        registry = OwnerRulesRegistry()

        self.assertFalse(registry.remove(object()))


class NetworkRulesCompositionTests(unittest.TestCase):
    def test_same_logical_domain_name_is_owner_scoped(self):
        composed = compose_network_rules(
            (
                OwnedNetworkRules(
                    OwnerToken(1),
                    _spec("default", "10.0.0.0/8"),
                ),
                OwnedNetworkRules(
                    OwnerToken(2),
                    _spec("default", "192.168.0.0/16"),
                ),
            )
        )

        refs = [item.routing_domain for item in composed.dispatch_rules]
        self.assertEqual(
            [(item.owner.value, item.name) for item in refs],
            [(2, "default"), (1, "default")],
        )

    def test_dispatch_is_globally_longest_prefix_first(self):
        composed = compose_network_rules(
            (
                OwnedNetworkRules(
                    OwnerToken(1),
                    _spec("broad", "10.0.0.0/8"),
                ),
                OwnedNetworkRules(
                    OwnerToken(2),
                    _spec("narrow", "10.1.0.0/16"),
                ),
            )
        )

        self.assertEqual(
            [str(item.destination) for item in composed.dispatch_rules],
            ["10.1.0.0/16", "10.0.0.0/8"],
        )

    def test_duplicate_dispatch_selector_inside_one_owner_is_rejected(self):
        network = IPv4Network("10.0.0.0/8")
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    name="a",
                    destinations=(network,),
                    ordered_paths=(),
                    terminal_disposition=TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    network,
                    "a",
                    source=NetworkEndpoint.local_network(),
                ),
                DispatchRuleSpec(
                    network,
                    "a",
                    source=NetworkEndpoint.local_network(),
                ),
            ),
        )

        with self.assertRaises(NetworkRulesCompositionError):
            compose_network_rules(
                (OwnedNetworkRules(OwnerToken(1), rules),)
            )

    def test_same_dispatch_selector_across_owners_is_rejected(self):
        with self.assertRaises(NetworkRulesCompositionError):
            compose_network_rules(
                (
                    OwnedNetworkRules(
                        OwnerToken(1),
                        _spec("a", "10.0.0.0/8"),
                    ),
                    OwnedNetworkRules(
                        OwnerToken(2),
                        _spec("b", "10.0.0.0/8"),
                    ),
                )
            )

    def test_same_destination_with_different_sources_is_not_conflict(self):
        path = NetworkEndpoint.interface_path(
            InterfaceIdentity("vpns00", 10)
        )
        composed = compose_network_rules(
            (
                OwnedNetworkRules(
                    OwnerToken(1),
                    _spec("local", "10.0.0.0/8"),
                ),
                OwnedNetworkRules(
                    OwnerToken(2),
                    _spec(
                        "path",
                        "10.0.0.0/8",
                        source=path,
                    ),
                ),
            )
        )

        self.assertEqual(len(composed.dispatch_rules), 2)

    def test_local_process_same_target_different_bound_paths_are_distinct(self):
        target = IPv4Network("203.0.113.24/32")
        local = NetworkEndpoint.local_process()
        first_path = NetworkEndpoint.interface_path(
            InterfaceIdentity("vpns00", 10)
        )
        second_path = NetworkEndpoint.interface_path(
            InterfaceIdentity("vpns01", 11)
        )

        def probe_rules(domain, path):
            return NetworkRulesSpec(
                routing_domains=(
                    RoutingDomainSpec(
                        domain,
                        (target,),
                        (path.interface,),
                        TerminalDisposition.DROP,
                    ),
                ),
                dispatch_rules=(
                    DispatchRuleSpec(
                        target,
                        domain,
                        source=local,
                        bound_output=path,
                        protocol=TrafficProtocol.ICMP,
                    ),
                ),
            )

        composed = compose_network_rules(
            (
                OwnedNetworkRules(
                    OwnerToken(1),
                    probe_rules("primary", first_path),
                ),
                OwnedNetworkRules(
                    OwnerToken(2),
                    probe_rules("secondary", second_path),
                ),
            )
        )

        self.assertEqual(len(composed.dispatch_rules), 2)
        self.assertEqual(
            {item.bound_output for item in composed.dispatch_rules},
            {first_path, second_path},
        )

    def test_duplicate_owner_token_is_rejected(self):
        with self.assertRaises(NetworkRulesCompositionError):
            compose_network_rules(
                (
                    OwnedNetworkRules(
                        OwnerToken(1),
                        NetworkRulesSpec(),
                    ),
                    OwnedNetworkRules(
                        OwnerToken(1),
                        NetworkRulesSpec(),
                    ),
                )
            )

    def test_removal_recomposition_preserves_surviving_owner(self):
        registry = OwnerRulesRegistry()
        first = object()
        second = object()
        first_rules = _spec("first", "10.0.0.0/8")
        second_rules = _spec("second", "192.168.0.0/16")

        first_token = registry.replace(first, first_rules)
        second_token = registry.replace(second, second_rules)
        before = compose_network_rules(registry.snapshot())

        self.assertTrue(registry.remove(first))
        after = compose_network_rules(registry.snapshot())

        self.assertEqual(len(before.owners), 2)
        self.assertEqual(
            after.owners,
            (OwnedNetworkRules(second_token, second_rules),),
        )
        self.assertNotIn(
            first_token,
            [item.owner for item in after.dispatch_rules],
        )


if __name__ == "__main__":
    unittest.main()
