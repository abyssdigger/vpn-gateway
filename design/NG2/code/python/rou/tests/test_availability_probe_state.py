import unittest

from rou.availability_probe_state import ProbeObservationGeneration


class ProbeObservationGenerationTests(unittest.TestCase):
    def test_requires_positive_integer_sequence(self):
        self.assertEqual(ProbeObservationGeneration(1).sequence, 1)

        for value in (0, -1, True, 1.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ProbeObservationGeneration(value)


if __name__ == "__main__":
    unittest.main()
