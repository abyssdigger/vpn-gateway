"""Offline orchestration checks: mocked acquisition, no live token or writes."""
import contextlib
import io
import unittest
from unittest.mock import patch

import core
import live_compact_evidence as runner


class LiveEvidenceTests(unittest.TestCase):
    def invoke(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc = runner.main()
        return rc, stream.getvalue()

    def test_baseline_drift_fails_before_acquisition(self):
        with patch.object(runner, "BLOBS", {"core.py": "0" * 40}), \
             patch("collab_watch.acquire") as acquisition:
            self.assertEqual(self.invoke(), (1, "FAIL stage: baseline\n"))
            acquisition.assert_not_called()

    def test_orchestration_and_fixed_failure_output(self):
        body = "private synthetic payload"
        raw = {"34": [{"id": 7197283850, "user": {"id": 340153730},
                       "body": body}], "35": [], "37": []}
        actual_digest = core.digest
        payload_sha = "1c71ad57e4717e190d34897877f1dbe0f5d910aefffae7ee2cdd38e08d3a7b98"
        def test_digest(value):
            return payload_sha if value == body else actual_digest(value)

        p, s = {"project": 1}, {"state": 1}
        binding = {"body_sha256": "a" * 64}
        for label, failure in (
            ("positive", None),
            ("payload", "exact payload binding"),
            ("acquisition", "stable raw acquisition"),
            ("projection", "fresh projection equality"),
            ("retained", "retained replay equality"),
            ("binding", "prospective binding equality"),
        ):
            with self.subTest(label=label), contextlib.ExitStack() as stack:
                stack.enter_context(patch.dict("os.environ", {"COLLAB_GITHUB_TOKEN": "fake"}))
                acq = stack.enter_context(patch("collab_watch.acquire", return_value=raw))
                if label == "acquisition":
                    acq.side_effect = ValueError(body)
                if label != "payload":
                    stack.enter_context(patch("core.digest", side_effect=test_digest))
                raw_project = stack.enter_context(patch("journal.project_m", return_value=(p,s)))
                compact_project = stack.enter_context(patch("journal.project_m_compact",
                    side_effect=[({"bad":1},s) if label == "projection" else (p,s),
                                 (p,{"bad":1}) if label == "retained" else (p,s)]))
                stack.enter_context(patch("compact_observation.compact_observation", return_value=object()))
                stack.enter_context(patch("compact_observation.encode_compact", return_value="wire"))
                stack.enter_context(patch("compact_observation.decode_compact", return_value=object()))
                raw_pre = stack.enter_context(patch("preflight_m.preflight_journal_fact", return_value=binding))
                compact_pre = stack.enter_context(patch("preflight_m.preflight_journal_fact_compact",
                    return_value={"bad":1} if label == "binding" else binding))
                rc, report = self.invoke()
                self.assertNotIn(body, report)
                self.assertNotIn("fake", report)
                if failure:
                    self.assertEqual((rc,report), (1, "FAIL stage: " + failure + "\n"))
                else:
                    self.assertEqual(rc, 0)
                    self.assertIn("FRESH_EQUAL=PASS RETAINED_EQUAL=PASS BINDING_EQUAL=PASS", report)
                    self.assertEqual(raw_project.call_count, 2)
                    self.assertEqual(compact_project.call_count, 2)
                    raw_pre.assert_called_once()
                    compact_pre.assert_called_once()
                acq.assert_called_once()


if __name__ == "__main__":
    unittest.main()
