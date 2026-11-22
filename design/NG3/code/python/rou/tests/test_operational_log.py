import unittest

from rou.operational_log import (
    OperationalLogAdapter,
    OperationalLogLevel,
)


class OperationalLogAdapterTests(unittest.TestCase):
    def test_threshold_is_inclusive_and_suppresses_lower_levels(self):
        lines = []
        logger = OperationalLogAdapter(
            OperationalLogLevel.INFO,
            sink=lines.append,
        )
        self.assertFalse(
            logger.emit(
                OperationalLogLevel.DEBUG,
                "PROF",
                "effective_order_changed",
                profile="corp",
            )
        )
        self.assertTrue(
            logger.emit(
                OperationalLogLevel.INFO,
                "AVAIL",
                "path_available",
                profile="corp",
                path="wg-main:0:0",
            )
        )
        self.assertTrue(
            logger.emit(
                OperationalLogLevel.ERROR,
                "POLICY",
                "reconcile_failed",
                status="failed",
            )
        )
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("INFO AVAIL path_available "))
        self.assertTrue(lines[1].startswith("ERROR POLICY reconcile_failed "))

    def test_debug_threshold_includes_all_levels(self):
        lines = []
        logger = OperationalLogAdapter(
            OperationalLogLevel.DEBUG,
            sink=lines.append,
        )
        for level in OperationalLogLevel:
            logger.emit(level, "LIFE", "event")
        self.assertEqual(len(lines), 4)

    def test_component_tag_constraint_is_enforced(self):
        logger = OperationalLogAdapter(sink=lambda _line: None)
        with self.assertRaisesRegex(ValueError, "6 characters"):
            logger.emit(
                OperationalLogLevel.INFO,
                "TOOLONG",
                "event",
            )

    def test_complex_context_is_rejected_instead_of_dumped(self):
        logger = OperationalLogAdapter(sink=lambda _line: None)
        with self.assertRaisesRegex(ValueError, "pre-normalized safe scalar"):
            logger.emit(
                OperationalLogLevel.INFO,
                "LIFE",
                "event",
                unsafe={"secret": "value"},
            )


if __name__ == "__main__":
    unittest.main()
