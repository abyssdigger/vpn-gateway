from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.availability_confirmation import AvailabilityOutcome
from rou.availability_manager import (
    AvailabilityManager,
    AvailabilityManagerError,
    AvailabilityManagerPolicy,
)
from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.payload_profile import PayloadProfileRequest
from rou.probe_policy import AvailabilityProbeIntent
from rou.probe_runtime import (
    ProbeEvidence,
    ProbeObservationContext,
    ProbeOwnershipDependency,
)
from rou.release1_config import parse_release1_config


A = LogicalPathId("wg", 0, 0)
B = LogicalPathId("oc", 0, 0)
EA = InterfaceIdentity("wg0", 10)
EB = InterfaceIdentity("oc0", 20)
TARGET = IPv4Address("198.51.100.10")


def config(*, reserve=False):
    device_order = '["wg", "oc:reserve"]' if reserve else '["wg", "oc"]'
    return parse_release1_config(f"""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[device.oc]
enabled = true
expected_interfaces = ["oc0"]
use_outbound_nat = false

[device.oc.availability_check]
mechanism = "icmp"
target = "198.51.100.20"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = {device_order}
availability_check = "default"
""")


def profile():
    return PayloadProfileRequest(
        "corp",
        Direction.OUTBOUND,
        (IPv4Network("10.0.0.0/8"),),
        (A, B),
    )


def context(
    path,
    endpoint,
    generation=1,
    target=TARGET,
    ownership_dependency=None,
):
    return ProbeObservationContext(
        AvailabilityProbeIntent(
            ProbePolicyOwner("corp", path),
            target,
        ),
        endpoint,
        generation,
        (
            ProbeOwnershipDependency.not_applicable()
            if ownership_dependency is None
            else ownership_dependency
        ),
    )


def evidence(ctx, outcome):
    return ProbeEvidence(ctx, outcome)


class AvailabilityManagerTests(unittest.TestCase):
    def test_synchronize_starts_from_baseline_order(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(2, 2))
        projected = manager.synchronize(
            (context(A, EA), context(B, EB)),
            (profile(),),
            config(),
        )
        self.assertEqual(projected.problem_owners, frozenset())
        self.assertEqual(
            projected.effective_profiles[0].ordered_paths,
            (A, B),
        )

    def test_degradation_requires_threshold_then_reorders(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(2, 2))
        cfg = config()
        p = profile()
        ca = context(A, EA)
        cb = context(B, EB)
        manager.synchronize((ca, cb), (p,), cfg)

        one = manager.apply_evidence(
            evidence(ca, AvailabilityOutcome.NEGATIVE),
            (p,),
            cfg,
        )
        self.assertEqual(one.effective_profiles[0].ordered_paths, (A, B))

        two = manager.apply_evidence(
            evidence(ca, AvailabilityOutcome.NEGATIVE),
            (p,),
            cfg,
        )
        self.assertEqual(two.effective_profiles[0].ordered_paths, (B, A))
        self.assertEqual(
            two.problem_owners,
            frozenset((ProbePolicyOwner("corp", A),)),
        )

    def test_recovery_clears_problem_without_unnecessary_failback(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(1, 2))
        cfg = config()
        p = profile()
        ca = context(A, EA)
        cb = context(B, EB)
        manager.synchronize((ca, cb), (p,), cfg)

        failed = manager.apply_evidence(
            evidence(ca, AvailabilityOutcome.NEGATIVE),
            (p,),
            cfg,
        )
        self.assertEqual(failed.effective_profiles[0].ordered_paths, (B, A))

        one = manager.apply_evidence(
            evidence(ca, AvailabilityOutcome.POSITIVE),
            (p,),
            cfg,
        )
        self.assertEqual(one.effective_profiles[0].ordered_paths, (B, A))

        recovered = manager.apply_evidence(
            evidence(ca, AvailabilityOutcome.POSITIVE),
            (p,),
            cfg,
        )
        self.assertEqual(recovered.problem_owners, frozenset())
        self.assertEqual(
            recovered.effective_profiles[0].ordered_paths,
            (B, A),
        )

    def test_reserve_active_path_yields_to_recovered_higher_preference(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(1, 1))
        cfg = config(reserve=True)
        p = profile()
        ca = context(A, EA)
        cb = context(B, EB)
        manager.synchronize((ca, cb), (p,), cfg)

        failed = manager.apply_evidence(
            evidence(ca, AvailabilityOutcome.NEGATIVE),
            (p,),
            cfg,
        )
        self.assertEqual(failed.effective_profiles[0].ordered_paths, (B, A))

        recovered = manager.apply_evidence(
            evidence(ca, AvailabilityOutcome.POSITIVE),
            (p,),
            cfg,
        )
        self.assertEqual(
            recovered.effective_profiles[0].ordered_paths,
            (A, B),
        )

    def test_context_change_resets_confirmation_progress(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(2, 2))
        cfg = config()
        p = profile()
        ca1 = context(A, EA, generation=1)
        cb = context(B, EB)
        manager.synchronize((ca1, cb), (p,), cfg)
        manager.apply_evidence(
            evidence(ca1, AvailabilityOutcome.NEGATIVE),
            (p,),
            cfg,
        )

        ca2 = context(A, EA, generation=2)
        manager.synchronize((ca2, cb), (p,), cfg)
        projected = manager.apply_evidence(
            evidence(ca2, AvailabilityOutcome.NEGATIVE),
            (p,),
            cfg,
        )
        self.assertEqual(projected.problem_owners, frozenset())
        self.assertEqual(
            projected.effective_profiles[0].ordered_paths,
            (A, B),
        )

    def test_d002_generation_change_invalidates_problem_evidence_same_endpoint(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(1, 1))
        cfg = config()
        p = profile()
        ca1 = context(
            A,
            EA,
            ownership_dependency=ProbeOwnershipDependency.confirmed(
                "d002-generation-a"
            ),
        )
        cb = context(B, EB)
        manager.synchronize((ca1, cb), (p,), cfg)

        failed = manager.apply_evidence(
            evidence(ca1, AvailabilityOutcome.NEGATIVE),
            (p,),
            cfg,
        )
        self.assertEqual(
            failed.problem_owners,
            frozenset((ProbePolicyOwner("corp", A),)),
        )
        self.assertEqual(
            failed.effective_profiles[0].ordered_paths,
            (B, A),
        )

        ca2 = context(
            A,
            EA,
            ownership_dependency=ProbeOwnershipDependency.confirmed(
                "d002-generation-b"
            ),
        )
        projected = manager.synchronize((ca2, cb), (p,), cfg)
        self.assertEqual(projected.problem_owners, frozenset())
        self.assertEqual(
            projected.effective_profiles[0].ordered_paths,
            (B, A),
            "routing stickiness is separate from invalidated availability evidence",
        )
        with self.assertRaisesRegex(
            AvailabilityManagerError,
            "current synchronized context",
        ):
            manager.apply_evidence(
                evidence(ca1, AvailabilityOutcome.NEGATIVE),
                (p,),
                cfg,
            )

    def test_stale_evidence_is_rejected(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(2, 2))
        cfg = config()
        p = profile()
        ca1 = context(A, EA, generation=1)
        cb = context(B, EB)
        manager.synchronize((ca1, cb), (p,), cfg)
        ca2 = context(A, EA, generation=2)
        manager.synchronize((ca2, cb), (p,), cfg)

        with self.assertRaisesRegex(
            AvailabilityManagerError,
            "current synchronized context",
        ):
            manager.apply_evidence(
                evidence(ca1, AvailabilityOutcome.NEGATIVE),
                (p,),
                cfg,
            )

    def test_no_evidence_does_not_change_problem_state(self):
        manager = AvailabilityManager(AvailabilityManagerPolicy(1, 1))
        cfg = config()
        p = profile()
        ca = context(A, EA)
        cb = context(B, EB)
        manager.synchronize((ca, cb), (p,), cfg)

        projected = manager.apply_evidence(
            ProbeEvidence(ca, AvailabilityOutcome.NO_EVIDENCE, "local error"),
            (p,),
            cfg,
        )
        self.assertEqual(projected.problem_owners, frozenset())
        self.assertEqual(
            projected.effective_profiles[0].ordered_paths,
            (A, B),
        )


if __name__ == "__main__":
    unittest.main()
