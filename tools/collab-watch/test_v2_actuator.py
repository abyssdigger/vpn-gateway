import copy
from email.message import Message
from io import BytesIO
import json
import subprocess
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from threading import Event, local
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import HTTPSHandler
from urllib.response import addinfourl

from core import canonical, digest, strict_json
from test_split_journal import CFG, SHA, fixture, issue, opening, material, ref, row, close, ts
from test_v2_acquisition import Response, Opener, snapshots, ROOT
from v2_attempts import initialize, open_store
from v2_inputs import initialize_inputs, open_inputs
from v2_compact import compact_v2
from v2_material import preflight_material
from v2_preflight import preflight_control_compact, preflight_close_compact, preflight_initial_open_compact
from v2_actuator import actuate, freeze_inputs, _bound, _stable_intent, _write_transport

BUILDER = dict(selected_role="BUILDER", selected_incarnation="b")
GUARD = dict(selected_role="GUARD", selected_incarnation="g")
SPEC = dict(selected_role="SPEC", selected_incarnation="s")


class Crash(BaseException):
    pass


class Remote:
    def __init__(self, before, after, actor, response):
        self.before, self.after = before, after
        self.actor, self.response = actor, response
        self.sent = []
        self.user_reads = []
        self.read_calls = []
        self.applied = False
        self.error = False
        self.user_error = False
        self.redirect = False
        self.crash = False
        self.store_check = None
    def read(self, req, timeout):
        source = self.after if self.applied else self.before
        opener = Opener(source)
        opener.scan = 0
        result = opener.open(req, timeout)
        self.read_calls.extend(opener.calls)
        return result
    def open(self, req, timeout):
        method, url = req.get_method(), req.full_url
        if method == "GET":
            self.user_reads.append((url, req.get_header("Authorization")))
            if self.user_error:
                raise URLError("sensitive remote error")
            return Response(url, {"id": self.actor}, redirect="https://evil.invalid" if self.redirect else None)
        self.sent.append((method, url, req.data, req.get_header("Authorization")))
        if self.store_check:
            self.store_check()
        self.applied = True
        if self.crash:
            raise Crash()
        if self.error:
            raise URLError("secret body must not escape")
        return Response(url, self.response, status=200 if method == "PATCH" else 201)


class ReadOpener:
    def __init__(self, remote):
        self.remote = remote
    def open(self, req, timeout):
        return self.remote.read(req, timeout)


class ActuatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"attempts.db"
        self.store = initialize(self.path, "actuator-test")
        self.input_path = Path(self.tmp.name)/"inputs.db"
        self.retention = initialize_inputs(self.input_path, "input-test", "actuator-test")
        self.write_context = local()
        transport = patch('v2_actuator._write_transport', side_effect=self.transport_factory)
        transport.start()
        self.addCleanup(transport.stop)

    def transport_factory(self):
        return _write_transport() if self.write_context.real else self.write_context.remote

    def material_case(self, extra_row=False, cfg=CFG):
        task = issue()
        task["repository"] = cfg["repository"]
        rows = [opening(task)]
        if cfg["journal_epoch"] != CFG["journal_epoch"]:
            rows[0]["body"] = rows[0]["body"].replace(
                '"journal_epoch":"' + CFG["journal_epoch"] + '"',
                '"journal_epoch":"' + cfg["journal_epoch"] + '"', 1)
        if extra_row:
            rows.append(row(800, 99, "ordinary new prose", 7))
        out = material(1001, "RESULT", 5)
        baseline = compact_v2(cfg, {"34": rows}, {"42": task})
        proof = preflight_material(cfg, baseline, "O1", 11, out["body"], **BUILDER)
        original = freeze_inputs("material_comment", cfg, baseline, 11, **BUILDER,
                                 expected_proof_sha256=digest(canonical(proof)), task_key="O1", body=out["body"])
        post = copy.deepcopy(task)
        post["comments"].append(out)
        remote = Remote(snapshots(rows, [task]), snapshots(rows, [post]), 11,
                        dict(out, issue_url=ROOT+"/issues/42"))
        return original, remote

    def control_case(self, witness=True):
        rows, task = fixture()
        task["comments"] = task["comments"][:1]
        prior = rows[:1]
        if witness:
            prior = prior+[row(800, 99, "ordinary witness", 7)]
        baseline = compact_v2(CFG, {"34": prior}, {"42": task})
        proof = preflight_control_compact(CFG, baseline, 11, rows[1]["body"], **BUILDER)
        original = freeze_inputs("control_comment", CFG, baseline, 11, **BUILDER,
                                 expected_proof_sha256=digest(canonical(proof)), body=rows[1]["body"])
        remote = Remote(snapshots(prior, [task]), snapshots(prior+[rows[1]], [task]), 11,
                        dict(rows[1], issue_url=ROOT+"/issues/34"))
        return original, remote

    def initial_case(self):
        rows, task = fixture()
        extra = issue(43, 4003)
        out = opening(extra, task="O2", mid="o2", cid=200, second=20)
        baseline = compact_v2(CFG, {"34": rows}, {"42": task})
        proof = preflight_initial_open_compact(CFG, baseline, extra, 13, out["body"], **SPEC)
        original = freeze_inputs("initial_open", CFG, baseline, 13, **SPEC,
                                 expected_proof_sha256=digest(canonical(proof)), body=out["body"], extra_task=extra)
        remote = Remote(snapshots(rows, [task, extra]), snapshots(rows+[out], [task, extra]), 13,
                        dict(out, issue_url=ROOT+"/issues/34"))
        return original, remote

    def close_case(self):
        rows, task = fixture()
        rows = rows+[row(800, 99, "ordinary witness", 12)]
        baseline = compact_v2(CFG, {"34": rows}, {"42": task})
        request = dict(task="O1", issue_number=42, issue_id=4002, revision=1, attempt=1,
                       commit_sha=SHA, accept_ref={"room":34, **ref(rows[2])})
        proof = preflight_close_compact(CFG, baseline, 10, request, **GUARD)
        original = freeze_inputs("issue_close", CFG, baseline, 10, **GUARD,
                                 expected_proof_sha256=digest(canonical(proof)), request=request)
        post = copy.deepcopy(task)
        close(post)
        remote = Remote(snapshots(rows, [task]), snapshots(rows, [post]), 10,
                        {"id":4002, "number":42, "state":"closed", "url":ROOT+"/issues/42"})
        return original, remote

    def run_case(self, original, remote, authorize=lambda _: True, *, real_transport=False, **kwargs):
        self.write_context.remote = remote
        self.write_context.real = real_transport
        args = dict(read_token="read-token", write_token="write-token",
                    read_opener=ReadOpener(remote))
        args.update(kwargs)
        return actuate(self.store, original, self.retention, authorize, **args)

    def test_success_paths_and_durable_start(self):
        for case in (self.material_case, self.control_case, self.close_case, self.initial_case):
            original, remote = case()
            seen = []
            def authority(action):
                seen.append(action)
                return True
            def check():
                key = digest(canonical(seen[-1]))
                state = open_store(self.path, "actuator-test").status(key)
                self.assertEqual(state["state"], "STARTED")
            remote.store_check = check
            result = self.run_case(original, remote, authority)
            self.assertEqual(result["state"], "VERIFIED", result)
            self.assertEqual(len(remote.sent), 1)
            self.assertEqual(remote.user_reads, [("https://api.github.com/user", "Bearer write-token")])
            self.assertTrue(all(a == "Bearer read-token" for _, _, a in remote.read_calls))
            self.assertEqual(remote.sent[0][3], "Bearer write-token")
            self.assertEqual(digest(remote.sent[0][2].decode()), seen[0]["request_sha256"])
            record = self.store.status(result["action_key"])
            self.assertEqual(record["state"], "VERIFIED")
            self.assertNotIn("write-token", canonical(record))
            self.assertNotIn("Candidate SHA:", canonical(record))
            self.assertEqual(self.run_case(original, remote)["state"], "VERIFIED")
            self.assertEqual(len(remote.sent), 1)

    def test_actor_mismatch_redirect_and_missing_write_token(self):
        for mode in ("actor", "redirect", "missing", "error"):
            original, remote = self.material_case()
            if mode == "actor":
                remote.actor = 10
            if mode == "redirect":
                remote.redirect = True
            if mode == "error":
                remote.user_error = True
            result = self.run_case(original, remote, **({"write_token":None} if mode == "missing" else {}))
            self.assertEqual(result["state"], "PREPARED")
            self.assertEqual(result["code"], "WRITE_ACTOR_UNVERIFIED")
            self.assertFalse(remote.sent)

    def test_authority_false_error_and_mutation(self):
        def error(_):
            raise ValueError("secret")
        def mutate(action):
            action["candidate"]["task"] = "changed"
            return True
        for authority in (lambda _: False, error, mutate):
            original, remote = self.material_case()
            result = self.run_case(original, remote, authority)
            self.assertEqual(result["code"], "AUTHORITY_DENIED")
            self.assertEqual(result["state"], "PREPARED")
            self.assertFalse(remote.sent)
            self.assertNotIn("secret", str(result))

    def test_chronology_and_drift(self):
        original, remote = self.control_case(False)
        result = self.run_case(original, remote)
        self.assertEqual(result["code"], "CHRONOLOGY_INELIGIBLE")
        self.assertFalse(remote.sent)
        original, remote = self.control_case()
        remote.before["/issues/42/comments"].append(dict(row(800, 99, "drift", 8),
                                                        issue_url=ROOT+"/issues/42"))
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "PREPARED")
        self.assertFalse(remote.sent)

    def test_timeout_after_effect_reconciles_without_resend(self):
        original, remote = self.material_case()
        remote.error = True
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertIsNone(self.store.status(result["action_key"])["response_hint"])
        self.store = open_store(self.path, "actuator-test")
        self.assertEqual(self.run_case(original, remote)["state"], "VERIFIED")
        self.assertEqual(len(remote.sent), 1)

    def test_malformed_response_readback(self):
        original, remote = self.material_case()
        remote.response = ["malformed"]
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "VERIFIED", result)
        self.assertIsNone(self.store.status(result["action_key"])["response_hint"])
        self.assertEqual(len(remote.sent), 1)

    def test_wrong_hint_unresolved_then_no_resend(self):
        original, remote = self.material_case()
        remote.response["id"] = 999
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "UNRESOLVED")
        self.assertEqual(self.store.status(result["action_key"])["response_hint"]["comment_id"], 999)
        self.store = open_store(self.path, "actuator-test")
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(len(remote.sent), 1)

    def test_missing_after_ambiguous_send_then_recovery(self):
        original, remote = self.material_case()
        post = remote.after
        remote.after = remote.before
        remote.error = True
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "UNRESOLVED")
        remote.after = post
        self.store = open_store(self.path, "actuator-test")
        recovered = self.run_case(original, remote, reconcile_only=True)
        self.assertEqual(recovered["state"], "VERIFIED")
        self.assertEqual(len(remote.sent), 1)

    def test_ambiguous_duplicate_no_hint_no_resend(self):
        original, remote = self.material_case()
        other = dict(remote.after["/issues/42/comments"][0], id=2000)
        remote.after["/issues/42/comments"].append(other)
        remote.error = True
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(len(remote.sent), 1)

    def test_same_second_control_no_resend(self):
        original, remote = self.control_case()
        target = remote.after["/issues/34/comments"][-1]
        target["created_at"] = target["updated_at"] = ts(5)
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "UNRESOLVED")
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.assertEqual(len(remote.sent), 1)

    def test_no_recovery_inputs_no_resend(self):
        original, remote = self.material_case()
        post = remote.after
        remote.after = remote.before
        remote.error = True
        self.assertEqual(self.run_case(original, remote)["state"], "UNRESOLVED")
        self.input_path.unlink()
        remote.after = post
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "EFFECT_UNKNOWN")
        self.assertEqual(result["code"], "INPUT_PROVIDER_UNAVAILABLE")
        self.assertFalse(self.input_path.exists())
        self.assertEqual(len(remote.sent), 1)

    def test_crash_before_hint_then_reopen(self):
        original, remote = self.material_case()
        remote.crash = True
        with self.assertRaises(Crash):
            self.run_case(original, remote)
        self.store = open_store(self.path, "actuator-test")
        self.retention = open_inputs(self.input_path, "input-test", "actuator-test")
        result = self.run_case(original, remote, reconcile_only=True)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertIsNone(self.store.status(result["action_key"])["response_hint"])
        self.assertEqual(len(remote.sent), 1)

    def test_crash_after_hint_then_reopen(self):
        original, remote = self.material_case()
        with patch.object(self.store, "mark_verified", side_effect=Crash):
            with self.assertRaises(Crash):
                self.run_case(original, remote)
        self.store = open_store(self.path, "actuator-test")
        self.retention = open_inputs(self.input_path, "input-test", "actuator-test")
        result = self.run_case(original, remote, reconcile_only=True)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertEqual(self.store.status(result["action_key"])["response_hint"]["comment_id"], 1001)
        self.assertEqual(len(remote.sent), 1)

    def test_hint_store_failure_no_false_success_or_resend(self):
        original, remote = self.material_case()
        with patch.object(self.store, "record_response_hint", side_effect=OSError("secret")):
            result = self.run_case(original, remote)
        self.assertEqual(result["state"], "EFFECT_UNKNOWN")
        self.assertNotIn("secret", str(result))
        self.store = open_store(self.path, "actuator-test")
        self.assertEqual(self.run_case(original, remote)["state"], "VERIFIED")
        self.assertEqual(len(remote.sent), 1)

    def test_concurrent_refreshed_actions_one_effect(self):
        original_a, a = self.material_case()
        original_b, b = self.material_case(True)
        self.assertNotEqual(_bound(original_a)[4], _bound(original_b)[4])
        self.assertEqual(_bound(original_a)[3], _bound(original_b)[3])
        entered, release = Event(), Event()
        def check():
            entered.set()
            self.assertTrue(release.wait(5))
        a.store_check = check
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.run_case, original_a, a)
            try:
                self.assertTrue(entered.wait(5))
                b.applied = True
                before_reads = len(b.read_calls)
                other = pool.submit(self.run_case, original_b, b, reconcile_only=True).result(5)
                self.assertEqual(other["code"], "ACTUATOR_BUSY")
                self.assertEqual(len(b.read_calls), before_reads)
                claimed = self.store.claimed(_bound(original_a)[3])
                self.assertEqual(claimed["state"], "STARTED")
                self.assertIsNone(claimed["response_hint"])
            finally:
                release.set()
            result = first.result(5)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertEqual(self.run_case(original_b, b)["action_key"], result["action_key"])
        self.assertEqual(len(a.sent)+len(b.sent), 1)

    def test_conflicting_control_body_same_effect(self):
        for claimed_state in ("VERIFIED", "STARTED", "UNRESOLVED"):
            with self.subTest(claimed_state=claimed_state):
                with tempfile.TemporaryDirectory() as directory:
                    self.store = initialize(Path(directory)/"attempts.db", "conflict-test")
                    self.retention = initialize_inputs(Path(directory)/"inputs.db", "conflict-input", "conflict-test")
                    original, remote = self.control_case()
                    data, baseline, _, effect, _, _ = _bound(original)
                    body = data["body"].replace('{"', '{ "', 1)
                    proof = preflight_control_compact(CFG, baseline, 11, body, **BUILDER)
                    alternative = freeze_inputs("control_comment", CFG, baseline, 11, **BUILDER,
                                                expected_proof_sha256=digest(canonical(proof)), body=body)
                    self.assertEqual(effect, _bound(alternative)[3])
                    self.assertNotEqual(_bound(original)[4]["request_sha256"],
                                        _bound(alternative)[4]["request_sha256"])
                    if claimed_state == "STARTED":
                        remote.crash = True
                        with self.assertRaises(Crash):
                            self.run_case(original, remote)
                    else:
                        if claimed_state == "UNRESOLVED":
                            remote.error = True
                            remote.after = remote.before
                        self.assertEqual(self.run_case(original, remote)["state"], claimed_state)
                    old = self.store.claimed(effect)
                    result = self.run_case(alternative, remote)
                    self.assertEqual(result, {"state":"CONFLICT", "code":"EFFECT_CLAIM_CONFLICT",
                                              "action_key":old["action_key"]})
                    self.assertEqual(self.store.claimed(effect), old)
                    self.assertEqual(len(remote.sent), 1)

    def test_lock_held_by_independent_process_then_exit(self):
        original, remote = self.material_case()
        script = ("import fcntl, os, sys, time; "
                  "fd=os.open(sys.argv[1], os.O_RDONLY); "
                  "fcntl.flock(fd, fcntl.LOCK_EX); print('locked', flush=True); time.sleep(30)")
        proc = subprocess.Popen([sys.executable, "-c", script, str(self.path)],
                                stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "locked")
            self.assertEqual(self.run_case(original, remote)["code"], "ACTUATOR_BUSY")
            self.assertFalse(remote.sent)
        finally:
            proc.kill()
            proc.wait(timeout=5)
            proc.stdout.close()
        self.assertEqual(self.run_case(original, remote)["state"], "VERIFIED")

    def test_mutation_redirect_real_no_redirect_handler(self):
        original, remote = self.material_case()
        calls = []
        def https_open(handler, req):
            calls.append((req.get_method(), req.full_url))
            headers = Message()
            if req.get_method() == "GET":
                status, payload = 200, {"id":11}
            else:
                self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "STARTED")
                status, payload = 302, {}
                headers["Location"] = "https://evil.invalid/redirected"
            raw = json.dumps(payload).encode()
            headers["Content-Length"] = str(len(raw))
            response = addinfourl(BytesIO(raw), headers, req.full_url, status)
            response.msg = "synthetic"
            return response
        with patch.object(HTTPSHandler, "https_open", https_open):
            result = self.run_case(original, remote, real_transport=True)
        self.assertEqual(result["state"], "UNRESOLVED")
        self.assertEqual(calls, [("GET", "https://api.github.com/user"),
                                 ("POST", ROOT+"/issues/42/comments")])
        self.assertEqual(self.store.claimed(_bound(original)[3])["state"], "UNRESOLVED")

    def test_public_write_opener_cannot_fabricate_actor(self):
        original, remote = self.material_case()
        remote.actor = 11
        with self.assertRaises(TypeError):
            self.run_case(original, remote, write_opener=remote)
        self.assertFalse(remote.user_reads)
        self.assertFalse(remote.sent)
        self.assertIsNone(self.store.claimed(_bound(original)[3]))

    def test_signal_room_rotation_equivalent_claim(self):
        original, remote = self.material_case()
        changed, other = self.material_case(cfg=dict(CFG, signal_room=38))
        self.assertEqual(_bound(original)[3], _bound(changed)[3])
        self.assertNotEqual(_bound(original)[4], _bound(changed)[4])
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertEqual(self.run_case(changed, other), result)
        self.assertFalse(other.sent)

    def test_action_affecting_epoch_change_conflicts(self):
        original, remote = self.material_case()
        changed, other = self.material_case(cfg=dict(CFG, journal_epoch="v2-next"))
        _, _, _, effect, action, _ = _bound(original)
        _, _, _, changed_effect, changed_action, _ = _bound(changed)
        self.assertEqual(effect, changed_effect)
        self.assertNotEqual(_stable_intent(action), _stable_intent(changed_action))
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "VERIFIED")
        old = self.store.claimed(effect)
        self.assertEqual(self.run_case(changed, other),
                         {"state":"CONFLICT", "code":"EFFECT_CLAIM_CONFLICT",
                          "action_key":old["action_key"]})
        self.assertEqual(self.store.claimed(effect), old)
        self.assertEqual(len(remote.sent), 1)
        self.assertFalse(other.sent)

    def test_provider_pair_mismatch_and_fake_provider_before_start(self):
        original, remote = self.material_case()
        self.retention = initialize_inputs(Path(self.tmp.name)/"wrong.db", "wrong-input", "wrong-attempt")
        self.assertEqual(self.run_case(original, remote)["code"], "INPUT_PROVIDER_UNAVAILABLE")
        class Fake:
            def save(self, *_):
                raise AssertionError("must not call")
            def load(self, *_):
                raise AssertionError("must not call")
        self.retention = Fake()
        self.assertEqual(self.run_case(original, remote)["code"], "INPUT_PROVIDER_UNAVAILABLE")
        self.assertFalse(remote.sent)
        self.assertFalse(remote.user_reads)
        self.assertIsNone(self.store.claimed(_bound(original)[3]))

    def test_provider_disappears_at_authority_gate_no_start(self):
        original, remote = self.material_case()
        def authority(_):
            self.input_path.unlink()
            return True
        result = self.run_case(original, remote, authority)
        self.assertEqual(result["state"], "PREPARED")
        self.assertEqual(result["code"], "INPUT_PROVIDER_UNAVAILABLE")
        self.assertFalse(remote.sent)
        self.assertIsNone(self.store.claimed(_bound(original)[3]))
        self.assertFalse(self.input_path.exists())

    def test_crash_after_provider_commit_before_started(self):
        original, remote = self.material_case()
        seen = []
        def authority(action):
            seen.append(digest(canonical(action)))
            return True
        with patch.object(self.store, "start", side_effect=Crash):
            with self.assertRaises(Crash):
                self.run_case(original, remote, authority)
        self.assertFalse(remote.sent)
        self.assertIsNone(self.store.claimed(_bound(original)[3]))
        self.assertEqual(self.store.status(seen[0])["state"], "PREPARED")
        self.retention = open_inputs(self.input_path, "input-test", "actuator-test")
        self.store = open_store(self.path, "actuator-test")
        self.assertEqual(self.retention.load(seen[0]), original)
        result = self.run_case(original, remote)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertEqual(result["action_key"], seen[0])
        self.assertEqual(len(remote.sent), 1)

    def test_started_provider_corruption_is_unknown_no_resend(self):
        original, remote = self.material_case()
        remote.crash = True
        with self.assertRaises(Crash):
            self.run_case(original, remote)
        claimed = self.store.claimed(_bound(original)[3])
        with sqlite3.connect(self.input_path) as conn:
            conn.execute("UPDATE originals SET original_sha256=? WHERE action_key=?",
                         ("0"*64, claimed["action_key"]))
        result = self.run_case(original, remote, reconcile_only=True)
        self.assertEqual(result["state"], "EFFECT_UNKNOWN")
        self.assertEqual(result["code"], "RETAINED_INPUT_UNAVAILABLE")
        self.assertEqual(self.store.claimed(_bound(original)[3]), claimed)
        self.assertEqual(len(remote.sent), 1)
        self.assertNotIn("write-token", str(result))
        self.assertNotIn("Candidate SHA:", str(result))

    def test_provider_loss_during_post_readback_prevents_verified(self):
        for mode in ("delete", "replace"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                self.path = Path(directory)/"attempts.db"
                self.input_path = Path(directory)/"inputs.db"
                self.store = initialize(self.path, "postread-attempt")
                self.retention = initialize_inputs(self.input_path, "postread-input", "postread-attempt")
                original, remote = self.material_case()
                read = remote.read
                changed = []
                def remove_during_readback(req, timeout):
                    response = read(req, timeout)
                    if remote.applied and not changed:
                        claimed = self.store.claimed(_bound(original)[3])
                        self.input_path.unlink()
                        if mode == "replace":
                            replacement = initialize_inputs(self.input_path, "postread-input", "postread-attempt")
                            try:
                                replacement.save(claimed["action_key"], original)
                            finally:
                                replacement.close()
                        changed.append(claimed["action_key"])
                    return response
                remote.read = remove_during_readback
                result = self.run_case(original, remote)
                self.assertEqual(result["state"], "EFFECT_UNKNOWN")
                self.assertEqual(result["code"], "RETAINED_INPUT_UNAVAILABLE")
                self.assertEqual(changed, [result["action_key"]])
                record = self.store.status(result["action_key"])
                self.assertEqual(record["state"], "STARTED")
                self.assertIsNone(record["receipt_sha256"])
                self.assertEqual(self.run_case(original, remote)["state"], "EFFECT_UNKNOWN")
                self.assertEqual(len(remote.sent), 1)
                self.retention.close()

    def test_repository_casing_stable_effect(self):
        original, _ = self.material_case()
        changed, _ = self.material_case(cfg=dict(CFG, repository="Owner/Repo"))
        self.assertEqual(_bound(original)[3], _bound(changed)[3])
        self.assertNotEqual(_bound(original)[4], _bound(changed)[4])

    def test_foreign_target_and_invalid_inputs(self):
        original, remote = self.close_case()
        data = strict_json(original)
        data["request"]["issue_id"] = 9999
        self.assertEqual(self.run_case(canonical(data), remote)["state"], "NO_ATTEMPT")
        data = strict_json(original)
        data["url"] = "https://evil.invalid"
        self.assertEqual(self.run_case(canonical(data), remote)["state"], "NO_ATTEMPT")
        self.assertFalse(remote.sent)

    def test_authority_external_source_mutation_cannot_change_request(self):
        original, remote = self.material_case()
        external = strict_json(original)
        def authority(action):
            external["body"] = "foreign body"
            external["cfg"]["repository"] = "evil/other"
            return True
        result = self.run_case(original, remote, authority)
        self.assertEqual(result["state"], "VERIFIED")
        self.assertEqual(remote.sent[0][1], ROOT+"/issues/42/comments")
        self.assertEqual(strict_json(remote.sent[0][2].decode())["body"], strict_json(original)["body"])
