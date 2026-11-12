from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.availability import AvailabilityPolicy, ProbeOutcome
from rou.availability_controller import AvailabilityController
from rou.availability_supervision import (
    DetectorEvidenceMissing,
    DetectorEvidenceStale,
    DetectorFreshnessPolicy,
)
from rou.device_engine import InterfaceIdentity
from rou.domain import Availability


class ManualClock:
    def __init__(self, value: float = 0.0):
        self.value = value

    def __call__(self) -> float:
        return self.value


class AvailabilityControllerTests(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock()
        self.identity = InterfaceIdentity("vpns00", 10)
        self.other = InterfaceIdentity("vpns01", 11)
        self.controller = AvailabilityController(
            availability_policy=AvailabilityPolicy(
                failure_threshold=2,
                recovery_threshold=2,
            ),
            freshness_policy=DetectorFreshnessPolicy(
                max_age_seconds=5.0,
            ),
            clock=self.clock,
        )

    def test_distinct_probe_records_drive_hysteresis(self):
        self.clock.value = 1.0
        self.controller.record(
            self.identity,
            ProbeOutcome.FAILURE,
        )
        first = self.controller.reconcile((self.identity,))
        self.assertEqual(
            first[self.identity],
            Availability.UNKNOWN,
        )

        self.clock.value = 2.0
        self.controller.record(
            self.identity,
            ProbeOutcome.FAILURE,
        )
        second = self.controller.reconcile((self.identity,))
        self.assertEqual(
            second[self.identity],
            Availability.UNAVAILABLE,
        )

    def test_reconcile_without_new_sample_does_not_advance_hysteresis(self):
        self.clock.value = 1.0
        self.controller.record(
            self.identity,
            ProbeOutcome.FAILURE,
        )
        first = self.controller.reconcile((self.identity,))
        self.clock.value = 2.0
        repeated = self.controller.reconcile((self.identity,))

        self.assertEqual(
            first[self.identity],
            Availability.UNKNOWN,
        )
        self.assertEqual(
            repeated[self.identity],
            Availability.UNKNOWN,
        )
        tracker = self.controller.state().tracker.by_interface[
            self.identity
        ]
        self.assertEqual(tracker.failure_streak, 1)

    def test_stale_error_does_not_commit_controller_state(self):
        self.clock.value = 1.0
        self.controller.record(
            self.identity,
            ProbeOutcome.FAILURE,
        )
        self.controller.reconcile((self.identity,))
        before = self.controller.state()

        self.clock.value = 10.0
        with self.assertRaises(DetectorEvidenceStale):
            self.controller.reconcile((self.identity,))

        self.assertEqual(self.controller.state(), before)

        self.controller.record(
            self.identity,
            ProbeOutcome.FAILURE,
        )
        recovered = self.controller.reconcile((self.identity,))
        self.assertEqual(
            recovered[self.identity],
            Availability.UNAVAILABLE,
        )

    def test_missing_evidence_does_not_commit_or_prune_existing_state(self):
        self.clock.value = 1.0
        self.controller.record(
            self.identity,
            ProbeOutcome.SUCCESS,
        )
        self.controller.reconcile((self.identity,))
        before_state = self.controller.state()
        before_evidence = dict(
            self.controller.evidence_snapshot()
        )

        with self.assertRaises(DetectorEvidenceMissing):
            self.controller.reconcile(
                (self.identity, self.other)
            )

        self.assertEqual(self.controller.state(), before_state)
        self.assertEqual(
            dict(self.controller.evidence_snapshot()),
            before_evidence,
        )

    def test_successful_reconcile_prunes_disappeared_generation(self):
        self.clock.value = 1.0
        self.controller.record(
            self.identity,
            ProbeOutcome.SUCCESS,
        )
        self.controller.record(
            self.other,
            ProbeOutcome.SUCCESS,
        )
        self.controller.reconcile(
            (self.identity, self.other)
        )

        self.clock.value = 2.0
        result = self.controller.reconcile((self.other,))

        self.assertNotIn(
            self.identity,
            self.controller.state().tracker.by_interface,
        )
        self.assertNotIn(
            self.identity,
            self.controller.evidence_snapshot(),
        )
        self.assertEqual(
            result[self.other],
            Availability.UNKNOWN,
        )

    def test_new_controller_starts_with_empty_ephemeral_domains(self):
        self.clock.value = 1.0
        self.controller.record(
            self.identity,
            ProbeOutcome.SUCCESS,
        )
        self.controller.reconcile((self.identity,))

        replacement = AvailabilityController(
            availability_policy=AvailabilityPolicy(
                failure_threshold=2,
                recovery_threshold=2,
            ),
            freshness_policy=DetectorFreshnessPolicy(
                max_age_seconds=5.0,
            ),
            clock=self.clock,
        )

        self.assertEqual(
            dict(replacement.state().tracker.by_interface),
            {},
        )
        self.assertEqual(
            dict(replacement.evidence_snapshot()),
            {},
        )
        with self.assertRaises(DetectorEvidenceMissing):
            replacement.reconcile((self.identity,))

    def test_constructor_requires_typed_policies(self):
        with self.assertRaisesRegex(
            ValueError,
            "AvailabilityPolicy",
        ):
            AvailabilityController(
                availability_policy="bad",  # type: ignore[arg-type]
                freshness_policy=DetectorFreshnessPolicy(5.0),
                clock=self.clock,
            )
        with self.assertRaisesRegex(
            ValueError,
            "DetectorFreshnessPolicy",
        ):
            AvailabilityController(
                availability_policy=AvailabilityPolicy(1, 1),
                freshness_policy="bad",  # type: ignore[arg-type]
                clock=self.clock,
            )

    def test_record_rejects_invalid_typed_values(self):
        with self.assertRaises(ValueError):
            self.controller.record(
                "vpns00",  # type: ignore[arg-type]
                ProbeOutcome.SUCCESS,
            )
        with self.assertRaises(ValueError):
            self.controller.record(
                self.identity,
                "success",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
