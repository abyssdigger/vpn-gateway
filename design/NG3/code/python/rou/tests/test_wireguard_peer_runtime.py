from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import (
    NG3_LINUX_POLICY_PLATFORM,
    NG3_PROBE_LOCAL_PLATFORM,
)
from rou.managed_device_manager import (
    ManagedDeviceDesiredState,
    ManagedDeviceRealization,
)
from rou.managed_wireguard_adapter import ManagedWireGuardState
from rou.network_policy_layout import (
    WireGuardGroupProbeOwner,
    WireGuardPeerProbeOwner,
)
from rou.payload_profile import PayloadProfileRequest
from rou.probe_plane_desired import (
    ProbePlaneDesiredAssembly,
    build_probe_plane_desired_assembly,
    project_current_wireguard_probe_intents,
)
from rou.probe_precondition import (
    ProbeExecutionContextKey,
    ProbeExecutionPrecondition,
)
from rou.probe_runtime import (
    ProbeTechnicalObservation,
    ProbeTechnicalOutcome,
)
from rou.release1_config import parse_current_config
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_peer_ownership import (
    WireGuardPeerOwnershipObservation,
    WireGuardPeerOwnershipResult,
)
from rou.wireguard_peer_runtime import (
    WireGuardPeerRuntimeCoordinator,
    WireGuardPeerRuntimeError,
)


PATH = LogicalPathId("wg", 0, 0)
EP = InterfaceIdentity("wg0", 17)
ROUTE = RoutePriorityPathRoute(PATH, EP)
CORP = IPv4Network("10.77.0.0/24")
GROUP_TARGET = IPv4Address("10.77.0.1")
PEER_A_TARGET = IPv4Address("10.201.0.1")
PEER_B_TARGET = IPv4Address("10.201.0.2")


def current_config():
    return parse_current_config(
        """
[device.wg]
enabled = true
use_outbound_nat = false

[device.wg.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/run/private.key"

[[device.wg.managed_vpn.peers]]
id = "a"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[[device.wg.managed_vpn.peers]]
id = "b"
public_key = "AgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4fICE="
endpoint = "198.51.100.11:51820"
probe_target = "10.201.0.2"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.77.0.0/24"]
device_order = ["wg"]

[profile.corp.availability_check]
mechanism = "icmp"
target = "10.77.0.1"
"""
    )


def profile(paths=(PATH,)):
    return PayloadProfileRequest(
        "corp",
        Direction.OUTBOUND,
        (CORP,),
        tuple(paths),
    )


def assembly(config=None, paths=(PATH,), routes=(ROUTE,)):
    config = current_config() if config is None else config
    profiles = (profile(paths),)
    peer_intents, group_intents = project_current_wireguard_probe_intents(
        config,
        profiles,
        routes,
    )
    return build_probe_plane_desired_assembly(
        profiles,
        (),
        peer_intents,
        group_intents,
        routes,
        NG3_LINUX_POLICY_PLATFORM,
        NG3_PROBE_LOCAL_PLATFORM,
    )


def base_realization(*, problem=None):
    return ManagedDeviceRealization(
        device_id="wg",
        desired_state=ManagedDeviceDesiredState.PRESENT,
        desired_generation="base-a",
        confirmed_state=(
            ManagedWireGuardState.PRESENT
            if problem is None
            else None
        ),
        confirmed_generation=(
            "base-a"
            if problem is None
            else None
        ),
        problem=problem,
    )


class SnapshotObserver:
    def __init__(self, events=None):
        self.calls = 0
        self.events = events

    def observe_structural_snapshot(self):
        self.calls += 1
        if self.events is not None:
            self.events.append("snapshot")
        return object()


class Driver:
    def __init__(self, outcomes, events=None):
        self.outcomes = {
            target: list(values)
            for target, values in outcomes.items()
        }
        self.calls = []
        self.events = events

    def execute(self, context):
        self.calls.append(context)
        if self.events is not None:
            label = (
                "group"
                if context.target == GROUP_TARGET
                else "peer"
            )
            self.events.append(f"probe:{label}")
        return self.outcomes[context.target].pop(0)


class Ownership:
    def __init__(self, events=None):
        self.calls = []
        self.events = events

    def converge(self, desired):
        self.calls.append(desired)
        if self.events is not None:
            self.events.append("ownership")
        return WireGuardPeerOwnershipResult(
            True,
            True,
            WireGuardPeerOwnershipObservation(
                desired.device_id,
                desired.interface,
                desired.peers,
            ),
        )


def reply():
    return ProbeTechnicalObservation(ProbeTechnicalOutcome.REPLY)


def no_reply():
    return ProbeTechnicalObservation(ProbeTechnicalOutcome.NO_REPLY)


class WireGuardPeerRuntimeCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.config = current_config()
        self.assembly = assembly(self.config)
        self.observer = SnapshotObserver()
        self.ownership = Ownership()
        self.verify_calls = []

        def verify(snapshot, full_desired, owners, platform):
            self.assertIs(platform, NG3_LINUX_POLICY_PLATFORM)
            self.assertEqual(len(owners), 1)
            owner = next(iter(owners))
            self.verify_calls.append(owner)
            rule = next(
                item
                for item in full_desired.rules
                if item.owner == owner
            )
            return ProbeExecutionPrecondition(
                routing=SimpleNamespace(confirmed=True),
                local=SimpleNamespace(desired_confirmed=True),
                interfaces_stable_snapshot=(rule.endpoint,),
                contexts=frozenset(
                    {
                        ProbeExecutionContextKey(
                            owner,
                            rule.mechanism,
                            rule.target,
                            rule.endpoint,
                        )
                    }
                ),
            )

        self.verify_patch = patch(
            "rou.wireguard_peer_runtime."
            "verify_probe_execution_precondition_scoped",
            side_effect=verify,
        )
        self.verify_patch.start()
        self.addCleanup(self.verify_patch.stop)

    def reconcile(self, coordinator, driver, *, routes=(ROUTE,), current_assembly=None):
        return coordinator.reconcile(
            self.config,
            (base_realization(),),
            routes,
            self.assembly if current_assembly is None else current_assembly,
            snapshot_observer=self.observer,
            probe_driver=driver,
            ownership=self.ownership,
            platform=NG3_LINUX_POLICY_PLATFORM,
        )

    def test_each_peer_and_group_attempt_gets_fresh_exact_owner_scope(self):
        events = []
        self.observer = SnapshotObserver(events)
        self.ownership = Ownership(events)
        driver = Driver(
            {
                PEER_A_TARGET: [reply()],
                GROUP_TARGET: [reply()],
            },
            events,
        )

        result = self.reconcile(
            WireGuardPeerRuntimeCoordinator(),
            driver,
        )

        self.assertTrue(result.confirmed)
        self.assertTrue(result.ready)
        self.assertEqual(
            result.realizations[0].owner_for("corp"),
            "a",
        )
        self.assertEqual(
            self.verify_calls,
            [
                WireGuardPeerProbeOwner("wg", "a"),
                WireGuardGroupProbeOwner("corp", "wg"),
            ],
        )
        self.assertEqual(self.observer.calls, 2)
        self.assertEqual(
            [item.target for item in driver.calls],
            [PEER_A_TARGET, GROUP_TARGET],
        )
        self.assertEqual(len(self.ownership.calls), 1)
        self.assertEqual(
            events,
            [
                "snapshot",
                "probe:peer",
                "ownership",
                "snapshot",
                "probe:group",
            ],
        )

    def test_manager_state_is_retained_across_periodic_triggers(self):
        coordinator = WireGuardPeerRuntimeCoordinator()
        first = self.reconcile(
            coordinator,
            Driver(
                {
                    PEER_A_TARGET: [no_reply()],
                    PEER_B_TARGET: [reply()],
                    GROUP_TARGET: [reply()],
                }
            ),
        )
        self.assertEqual(first.realizations[0].owner_for("corp"), "b")

        self.verify_calls.clear()
        second_driver = Driver(
            {
                PEER_A_TARGET: [reply()],
                PEER_B_TARGET: [reply()],
                GROUP_TARGET: [reply()],
            }
        )
        second = self.reconcile(coordinator, second_driver)

        self.assertEqual(second.realizations[0].owner_for("corp"), "b")
        self.assertEqual(
            second.realizations[0].generation,
            first.realizations[0].generation,
        )
        self.assertEqual(
            [item.target for item in second_driver.calls],
            [PEER_B_TARGET, GROUP_TARGET],
        )
        self.assertNotIn(
            WireGuardPeerProbeOwner("wg", "a"),
            self.verify_calls,
        )

    def test_no_current_path_discards_retained_manager_state(self):
        coordinator = WireGuardPeerRuntimeCoordinator()
        first = self.reconcile(
            coordinator,
            Driver(
                {
                    PEER_A_TARGET: [no_reply()],
                    PEER_B_TARGET: [reply()],
                    GROUP_TARGET: [reply()],
                }
            ),
        )
        self.assertEqual(first.realizations[0].owner_for("corp"), "b")

        empty = assembly(self.config, paths=(), routes=())
        inactive = self.reconcile(
            coordinator,
            Driver({}),
            routes=(),
            current_assembly=empty,
        )
        self.assertEqual(inactive.realizations, ())

        restored_driver = Driver(
            {
                PEER_A_TARGET: [reply()],
                GROUP_TARGET: [reply()],
            }
        )
        restored = self.reconcile(coordinator, restored_driver)
        self.assertEqual(
            restored.realizations[0].owner_for("corp"),
            "a",
        )
        self.assertEqual(
            [item.target for item in restored_driver.calls],
            [PEER_A_TARGET, GROUP_TARGET],
        )

    def test_confirmed_no_owner_is_not_local_runtime_failure(self):
        driver = Driver(
            {
                PEER_A_TARGET: [no_reply()],
                PEER_B_TARGET: [no_reply()],
            }
        )
        result = self.reconcile(
            WireGuardPeerRuntimeCoordinator(),
            driver,
        )

        self.assertTrue(result.confirmed)
        self.assertFalse(result.ready)
        self.assertIsNone(
            result.realizations[0].owner_for("corp")
        )
        self.assertIsNone(result.realizations[0].problem)
        self.assertIsNotNone(result.realizations[0].generation)

    def test_unconfirmed_d001_generation_blocks_before_probe_or_mutation(self):
        driver = Driver({})
        with self.assertRaisesRegex(
            WireGuardPeerRuntimeError,
            "no confirmed current D.001 base generation",
        ):
            WireGuardPeerRuntimeCoordinator().reconcile(
                self.config,
                (base_realization(problem="D.001 failed"),),
                (ROUTE,),
                self.assembly,
                snapshot_observer=self.observer,
                probe_driver=driver,
                ownership=self.ownership,
                platform=NG3_LINUX_POLICY_PLATFORM,
            )

        self.assertEqual(driver.calls, [])
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.observer.calls, 0)

    def test_mismatched_d001_generation_blocks_before_probe_or_mutation(self):
        inconsistent = ManagedDeviceRealization(
            device_id="wg",
            desired_state=ManagedDeviceDesiredState.PRESENT,
            desired_generation="base-b",
            confirmed_state=ManagedWireGuardState.PRESENT,
            confirmed_generation="base-a",
        )
        driver = Driver({})

        with self.assertRaisesRegex(
            WireGuardPeerRuntimeError,
            "no confirmed current D.001 base generation",
        ):
            WireGuardPeerRuntimeCoordinator().reconcile(
                self.config,
                (inconsistent,),
                (ROUTE,),
                self.assembly,
                snapshot_observer=self.observer,
                probe_driver=driver,
                ownership=self.ownership,
                platform=NG3_LINUX_POLICY_PLATFORM,
            )

        self.assertEqual(driver.calls, [])
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.observer.calls, 0)

    def test_stale_probe_path_binding_blocks_before_probe_or_mutation(self):
        stale_route = RoutePriorityPathRoute(
            PATH,
            InterfaceIdentity("wg0", 99),
        )
        peer_intents = tuple(
            type(intent)(
                intent.owner,
                intent.target,
                stale_route,
                intent.mechanism,
            )
            for intent in self.assembly.peer_intents
        )
        stale = ProbePlaneDesiredAssembly(
            layout=self.assembly.layout,
            probe=self.assembly.probe,
            availability_intents=self.assembly.availability_intents,
            peer_intents=peer_intents,
            group_intents=self.assembly.group_intents,
        )
        driver = Driver({})

        with self.assertRaisesRegex(
            WireGuardPeerRuntimeError,
            "peer probe path binding is stale",
        ):
            self.reconcile(
                WireGuardPeerRuntimeCoordinator(),
                driver,
                current_assembly=stale,
            )

        self.assertEqual(driver.calls, [])
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.observer.calls, 0)

    def test_stale_probe_owner_union_blocks_before_probe_or_mutation(self):
        stale = ProbePlaneDesiredAssembly(
            layout=self.assembly.layout,
            probe=self.assembly.probe,
            availability_intents=self.assembly.availability_intents,
            peer_intents=(),
            group_intents=self.assembly.group_intents,
        )
        driver = Driver({})

        with self.assertRaisesRegex(
            WireGuardPeerRuntimeError,
            "peer probe owner union is stale",
        ):
            self.reconcile(
                WireGuardPeerRuntimeCoordinator(),
                driver,
                current_assembly=stale,
            )

        self.assertEqual(driver.calls, [])
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.observer.calls, 0)


if __name__ == "__main__":
    unittest.main()
