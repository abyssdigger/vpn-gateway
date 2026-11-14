import unittest

from rou.availability_probe_state import (
    AvailabilityProbeState,
    AvailabilityProbeStateInfo,
    ProbeObservationGeneration,
)


class ProbeObservationGenerationTests(unittest.TestCase):
    def test_sequence_must_be_positive_integer(self):
        for value in (0, -1, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ProbeObservationGeneration(value)


class AvailabilityProbeStateInfoTests(unittest.TestCase):
    def test_unknown_has_no_authoritative_generation(self):
        info = AvailabilityProbeStateInfo(
            "probe-a",
            AvailabilityProbeState.UNKNOWN,
            reason="rules are not ready",
        )

        self.assertIsNone(info.observation_generation)

        with self.assertRaises(ValueError):
            AvailabilityProbeStateInfo(
                "probe-a",
                AvailabilityProbeState.UNKNOWN,
                observation_generation=ProbeObservationGeneration(1),
            )

    def test_reachable_and_unreachable_require_generation(self):
        generation = ProbeObservationGeneration(3)

        reachable = AvailabilityProbeStateInfo(
            "probe-a",
            AvailabilityProbeState.REACHABLE,
            observation_generation=generation,
        )
        unreachable = AvailabilityProbeStateInfo(
            "probe-a",
            AvailabilityProbeState.UNREACHABLE,
            observation_generation=generation,
            reason="threshold satisfied",
        )

        self.assertEqual(reachable.observation_generation, generation)
        self.assertEqual(unreachable.observation_generation, generation)

        for state in (
            AvailabilityProbeState.REACHABLE,
            AvailabilityProbeState.UNREACHABLE,
        ):
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    AvailabilityProbeStateInfo("probe-a", state)

    def test_rejects_empty_probe_id_and_untyped_state(self):
        with self.assertRaises(ValueError):
            AvailabilityProbeStateInfo(
                "",
                AvailabilityProbeState.UNKNOWN,
            )
        with self.assertRaises(ValueError):
            AvailabilityProbeStateInfo(
                "probe-a",
                "unknown",
            )


if __name__ == "__main__":
    unittest.main()
