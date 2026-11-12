from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.availability import ProbeOutcome
from rou.device_engine import InterfaceIdentity
from rou.probe_evidence import ProbeEvidenceStore


class SequenceClock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


class ProbeEvidenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.a = InterfaceIdentity("vpns00", 10)
        self.b = InterfaceIdentity("vpns00", 11)

    def test_store_assigns_process_local_monotonic_ids(self):
        store = ProbeEvidenceStore(
            clock=SequenceClock([1.0, 2.0, 3.0])
        )

        first = store.record(self.a, ProbeOutcome.SUCCESS)
        second = store.record(self.a, ProbeOutcome.FAILURE)
        third = store.record(self.b, ProbeOutcome.SUCCESS)

        self.assertEqual(
            (first.sample_id, second.sample_id, third.sample_id),
            (0, 1, 2),
        )
        self.assertEqual(
            (first.monotonic_time, second.monotonic_time, third.monotonic_time),
            (1.0, 2.0, 3.0),
        )

    def test_snapshot_is_immutable_point_in_time_copy(self):
        store = ProbeEvidenceStore(
            clock=SequenceClock([1.0, 2.0])
        )
        first = store.record(self.a, ProbeOutcome.SUCCESS)
        snapshot = store.snapshot()

        with self.assertRaises(TypeError):
            snapshot[self.b] = first  # type: ignore[index]

        store.record(self.a, ProbeOutcome.FAILURE)

        self.assertEqual(snapshot[self.a], first)
        self.assertNotEqual(
            snapshot[self.a],
            store.snapshot()[self.a],
        )

    def test_retain_drops_old_generation_without_reusing_sequence(self):
        store = ProbeEvidenceStore(
            clock=SequenceClock([1.0, 2.0])
        )
        first = store.record(self.a, ProbeOutcome.SUCCESS)
        store.retain(())
        second = store.record(self.a, ProbeOutcome.FAILURE)

        self.assertEqual(first.sample_id, 0)
        self.assertEqual(second.sample_id, 1)
        self.assertEqual(
            tuple(store.snapshot()),
            (self.a,),
        )

    def test_same_name_new_ifindex_has_independent_latest_sample(self):
        store = ProbeEvidenceStore(
            clock=SequenceClock([1.0, 2.0])
        )
        old = store.record(self.a, ProbeOutcome.FAILURE)
        fresh = store.record(self.b, ProbeOutcome.SUCCESS)

        snapshot = store.snapshot()
        self.assertEqual(snapshot[self.a], old)
        self.assertEqual(snapshot[self.b], fresh)

        store.retain((self.b,))
        snapshot = store.snapshot()
        self.assertNotIn(self.a, snapshot)
        self.assertEqual(snapshot[self.b], fresh)

    def test_retain_requires_interface_identity_values(self):
        store = ProbeEvidenceStore()
        with self.assertRaisesRegex(
            ValueError,
            "InterfaceIdentity",
        ):
            store.retain(("vpns00",))  # type: ignore[arg-type]

    def test_duplicate_retain_identity_is_rejected(self):
        store = ProbeEvidenceStore()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            store.retain((self.a, self.a))

    def test_invalid_input_is_rejected_before_store_mutation(self):
        store = ProbeEvidenceStore(clock=lambda: 1.0)

        with self.assertRaisesRegex(ValueError, "InterfaceIdentity"):
            store.record("vpns00", ProbeOutcome.SUCCESS)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "ProbeOutcome"):
            store.record(self.a, "success")  # type: ignore[arg-type]

        sample = store.record(self.a, ProbeOutcome.SUCCESS)
        self.assertEqual(sample.sample_id, 0)

    def test_invalid_clock_value_does_not_consume_sample_id(self):
        clock = SequenceClock([float("nan"), 2.0])
        store = ProbeEvidenceStore(clock=clock)

        with self.assertRaises(ValueError):
            store.record(self.a, ProbeOutcome.SUCCESS)

        sample = store.record(self.a, ProbeOutcome.SUCCESS)
        self.assertEqual(sample.sample_id, 0)

    def test_concurrent_records_receive_unique_serialized_ids(self):
        store = ProbeEvidenceStore(clock=lambda: 1.0)
        samples = []
        errors = []
        result_lock = threading.Lock()

        def worker():
            try:
                sample = store.record(
                    self.a,
                    ProbeOutcome.SUCCESS,
                )
                with result_lock:
                    samples.append(sample)
            except Exception as exc:
                with result_lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=worker)
            for _ in range(32)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(
            sorted(sample.sample_id for sample in samples),
            list(range(32)),
        )
        self.assertEqual(
            store.snapshot()[self.a].sample_id,
            31,
        )


if __name__ == "__main__":
    unittest.main()
