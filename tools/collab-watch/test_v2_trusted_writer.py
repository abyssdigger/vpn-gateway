"""Staged writer data-interface tests; no claim of hostile Python/OS isolation."""
import copy
from dataclasses import replace
import sqlite3
import unittest
from unittest.mock import patch

from core import Conflict, canonical, strict_json
from test_split_journal import CFG
import test_v2_actuator as tf
import test_v2_aux_actuator as af
import test_v2_aggregate_actuator as gf
from v2_actuator import _bound
from v2_fenced_actuator import actuate_fenced
from v2_identity import SCHEMA
from v2_trusted_writer import TrustedWriter


def pair(role):
    return dict(transport_role=role, incarnation=CFG['roles'][role]['incarnation'])


BINDINGS = dict(schema=SCHEMA, bindings=[
    dict(model='GPT-5.6 Sol', status='admitted', transport_pairs=[pair('GUARD'), pair('SPEC')],
         additional_responsibilities={'GUARD': ['SPEC']}),
    dict(model='GPT-6.2', status='admitted', transport_pairs=[pair('BUILDER')],
         additional_responsibilities={}),
])
REJECTED = dict(state='NO_ATTEMPT', code='TRUSTED_INGRESS_REJECTED', action_key=None)
UNKNOWN = dict(state='EFFECT_UNKNOWN', code='TRUSTED_RESULT_INVALID', action_key=None)


class DictSubclass(dict):
    pass


class StrSubclass(str):
    pass


class WriterTests(unittest.TestCase):
    case = af.AuxActuatorTests.case
    new_checkpoint = gf.AggregateActuatorTests.new_checkpoint

    def setUp(self):
        gf.AggregateActuatorTests.setUp(self)
        self.caps = {}

    def cap(self, original):
        data = strict_json(original)
        role = data['role']
        if role not in self.caps:
            self.caps[role] = self.owner.claim(role, data['incarnation'], lambda _: True)
        return self.caps[role]

    def writer(self, original, remote, **kwargs):
        data = strict_json(original)
        role = data['role']
        params = dict(cfg=data['cfg'], bindings=copy.deepcopy(BINDINGS),
                      runtime_model='GPT-6.2' if role == 'BUILDER' else 'GPT-5.6 Sol',
                      selected_role=role, owner_store=self.owner, capability=self.cap(original),
                      store=self.store, retention=self.retention, runtime_state=remote.runtime_state,
                      authorize=lambda _: True, read_token='read-token', write_token='write-token',
                      read_opener=tf.ReadOpener(remote))
        params.update(kwargs)
        return TrustedWriter(**params)

    def invoke(self, writer, original, remote, reconcile=False):
        with patch('v2_actuator._write_transport', return_value=remote):
            return writer.invoke(dict(original=original, reconcile_only=reconcile))

    def counts(self):
        counts = []
        for path, table in ((self.store.path, 'attempts'), (self.retention.path, 'originals')):
            with sqlite3.connect(path) as db:
                counts.append(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0])
        return counts

    def assert_untouched(self, remote):
        self.assertEqual(self.counts(), [0, 0])
        self.assertFalse(remote.sent or remote.read_calls or remote.user_reads)

    def test_strict_request_and_frozen_shape(self):
        original, remote = tf.ActuatorTests.material_case(self)
        writer = self.writer(original, remote)
        good = dict(original=original, reconcile_only=False)
        requests = [None, [], {}, DictSubclass(good), dict(good, original=StrSubclass(original)),
                    dict(good, reconcile_only=1), dict(good, reconcile_only='false'),
                    dict(good, original=original+' '), dict(good, original='{'),
                    dict(good, original='{"x":1,"x":2}'),
                    dict(good, original=canonical(dict(strict_json(original), token='secret')))]
        missing = strict_json(original)
        del missing['actor']
        requests.append(dict(good, original=canonical(missing)))
        for field in ('cfg', 'role', 'actor', 'capability', 'store', 'path', 'opener',
                      'url', 'token', 'authorize', 'runtime_state', 'headers'):
            requests.append(dict(good, **{field: 'secret'}))
        with patch('v2_trusted_writer.actuate_fenced') as delegate:
            for request in requests:
                self.assertEqual(writer.invoke(request), REJECTED)
            with patch('v2_trusted_writer.MAX_INPUT_BYTES', 5), \
                 patch('v2_trusted_writer.strict_json') as decode:
                self.assertEqual(writer.invoke(dict(good, original='ééé')), REJECTED)
                decode.assert_not_called()
            delegate.assert_not_called()
        self.assert_untouched(remote)

    def test_detached_config_and_identity(self):
        original, remote = tf.ActuatorTests.material_case(self)
        cfg, bindings = copy.deepcopy(CFG), copy.deepcopy(BINDINGS)
        writer = self.writer(original, remote, cfg=cfg, bindings=bindings)
        cfg['signal_room'] += 1
        bindings['bindings'][1]['status'] = 'disabled'
        changed = canonical(dict(strict_json(original), cfg=cfg))
        with patch('v2_trusted_writer.actuate_fenced') as delegate:
            self.assertEqual(writer.invoke(dict(original=changed, reconcile_only=False)), REJECTED)
            delegate.assert_not_called()
        self.assertEqual(self.invoke(writer, original, remote)['state'], 'VERIFIED')
        self.assertEqual(len(remote.sent), 1)

    def test_bootstrap_rejects_identity_and_scope(self):
        original, remote = self.case()
        cap = self.cap(original)
        for overrides in (dict(selected_role=None), dict(runtime_model='GPT-6.2'),
                          dict(selected_role='SPEC'), dict(capability=replace(cap, incarnation='wrong')),
                          dict(runtime_state=self.new_checkpoint(epoch='wrong')),
                          dict(retention=object()), dict(store=object()), dict(authorize=None)):
            with self.subTest(overrides=tuple(overrides)), self.assertRaises(Conflict):
                self.writer(original, remote, **overrides)
        self.assert_untouched(remote)

    def test_same_epoch_transport_and_actor_drift(self):
        original, remote = tf.ActuatorTests.material_case(self)
        writer = self.writer(original, remote)
        data = strict_json(original)
        changed = [dict(data, role='GUARD'), dict(data, incarnation='wrong'),
                   dict(data, actor=True), dict(data, actor=99), dict(data, operation='unknown'),
                   dict(data, operation='signal_comment')]
        for edit in ('signal_room', 'actor', 'holder', 'registry'):
            cfg = copy.deepcopy(data['cfg'])
            if edit == 'signal_room':
                cfg['signal_room'] += 1
            elif edit == 'actor':
                cfg['roles']['GUARD']['actor_id'] = 99
            elif edit == 'holder':
                cfg['projectholder']['room'] += 1
            else:
                cfg['command_registry']['cycle'] = 'changed'
            changed.append(dict(data, cfg=cfg))
        with patch('v2_trusted_writer.actuate_fenced') as delegate:
            for obj in changed:
                self.assertEqual(writer.invoke(dict(original=canonical(obj), reconcile_only=False)), REJECTED)
            delegate.assert_not_called()
        self.assert_untouched(remote)

    def test_six_actual_send_families_and_receipts(self):
        cases = (tf.ActuatorTests.material_case, tf.ActuatorTests.control_case,
                 af.AuxActuatorTests.case, tf.ActuatorTests.initial_case,
                 tf.ActuatorTests.close_case, tf.ActuatorTests.creation_case)
        for case in cases:
            original, remote = case(self)
            op = strict_json(original)['operation']
            writer = self.writer(original, remote)
            def check_start():
                self.assertEqual(self.store.claimed(_bound(original)[3])['state'], 'STARTED')
            remote.store_check = check_start
            with self.subTest(operation=op), patch('v2_trusted_writer.actuate_fenced', wraps=actuate_fenced) as delegate:
                result = self.invoke(writer, original, remote)
                delegate.assert_called_once()
                self.assertEqual(result['state'], 'VERIFIED', result)
                claim = self.store.claimed(_bound(original)[3])
                self.assertEqual(claim['action_key'], result['action_key'])
                self.assertEqual(self.retention.load(result['action_key']), original)
                self.assertEqual(len(remote.sent), 1)
                self.assertEqual(self.invoke(writer, original, remote, True), result)
                self.assertEqual(delegate.call_count, 2)
                self.assertEqual(len(remote.sent), 1)

    def test_signal_reconcile_only_and_never_resend(self):
        original, remote = af.AuxActuatorTests.signal_case(self)
        writer = self.writer(original, remote, runtime_state=None, write_token=None)
        with patch('v2_trusted_writer.actuate_fenced', wraps=actuate_fenced) as delegate:
            self.assertEqual(self.invoke(writer, original, remote), REJECTED)
            delegate.assert_not_called()
            absent = self.invoke(writer, original, remote, True)
            self.assertEqual(absent['code'], 'NO_CLAIMED_EFFECT')
            delegate.assert_called_once()
        self.assert_untouched(remote)
        # Establish historical claim through the already accepted lower layer, synthetic only.
        with patch('v2_actuator._write_transport', return_value=remote):
            historical = actuate_fenced(self.owner, self.cap(original), self.store, original,
                                        self.retention, lambda _: True, read_token='read-token',
                                        write_token='write-token', read_opener=tf.ReadOpener(remote))
        self.assertEqual(historical['state'], 'VERIFIED', historical)
        self.assertEqual(self.invoke(writer, original, remote), REJECTED)
        self.assertEqual(self.invoke(writer, original, remote, True), historical)
        self.assertEqual(len(remote.sent), 1)

    def test_replaced_owner_and_busy_remain_fenced(self):
        original, remote = tf.ActuatorTests.material_case(self)
        cap = self.cap(original)
        writer = self.writer(original, remote)
        new = self.other_owner.replace(cap.transport_role, cap.incarnation, cap.generation, lambda _: True)
        with patch('v2_trusted_writer.actuate_fenced', wraps=actuate_fenced) as delegate:
            result = self.invoke(writer, original, remote)
            delegate.assert_called_once()
            self.assertEqual(result['code'], 'OWNER_CAPABILITY_REJECTED')
        current = self.writer(original, remote, capability=new)
        with self.other_owner.fence(new):
            self.assertEqual(self.invoke(current, original, remote)['code'], 'OWNER_BUSY')
        self.assert_untouched(remote)

    def test_missing_checkpoint_and_missing_token_recovery(self):
        original, remote = tf.ActuatorTests.material_case(self)
        unavailable = self.writer(original, remote, runtime_state=None, write_token=None)
        self.assertEqual(self.invoke(unavailable, original, remote, True)['code'], 'NO_CLAIMED_EFFECT')
        self.assert_untouched(remote)
        result = self.invoke(unavailable, original, remote)
        self.assertEqual((result['state'], result['code']), ('PREPARED', 'CHECKPOINT_UNAVAILABLE_OR_STALE'))
        self.assertFalse(remote.sent)
        self.assertIsNone(self.store.claimed(_bound(original)[3]))
        result = self.invoke(self.writer(original, remote, write_token=None), original, remote)
        self.assertEqual((result['state'], result['code']), ('PREPARED', 'WRITE_ACTOR_UNVERIFIED'))
        self.assertFalse(remote.sent)
        post = remote.after
        remote.after = remote.before
        remote.error = True
        self.assertEqual(self.invoke(self.writer(original, remote), original, remote)['state'], 'UNRESOLVED')
        remote.after = post
        self.assertEqual(self.invoke(unavailable, original, remote, True)['state'], 'VERIFIED')
        self.assertEqual(len(remote.sent), 1)

    def test_authority_denied_without_send(self):
        original, remote = tf.ActuatorTests.material_case(self)
        def raise_error(_):
            raise RuntimeError('secret')
        def mutate(descriptor):
            descriptor['request_sha256'] = '0'*64
            return True
        for authority in (lambda _: False, raise_error, mutate):
            result = self.invoke(self.writer(original, remote, authorize=authority), original, remote)
            self.assertEqual((result['state'], result['code']), ('PREPARED', 'AUTHORITY_DENIED'))
            self.assertFalse(remote.sent)
            self.assertIsNone(self.store.claimed(_bound(original)[3]))
            self.assertNotIn('secret', repr(result))

    def test_result_boundary_and_actual_claim_survives_bad_egress(self):
        original, remote = tf.ActuatorTests.control_case(self)
        writer = self.writer(original, remote)
        valid = dict(state='VERIFIED', code='CANONICAL_RECEIPT_RECORDED', action_key='a'*64,
                     receipt_sha256='b'*64, locator=dict(room=34, physical_ref='issue:34#issuecomment-5'))
        bad = [None, DictSubclass(valid), dict(valid, secret='secret'), dict(valid, code='secret'),
               dict(valid, state='secret'), dict(valid, action_key='secret'),
               dict(valid, receipt_sha256='secret'), dict(valid, locator=dict(room=True, physical_ref='issue:1#issuecomment-5')),
               dict(valid, locator=dict(room=34, physical_ref='issue:35#issuecomment-5')),
               dict(valid, locator=dict(room=34, comment_id=5)), dict(valid, locator=dict(valid['locator'], extra='secret'))]
        with patch('v2_trusted_writer.actuate_fenced') as delegate:
            for value in bad:
                delegate.return_value = value
                self.assertEqual(self.invoke(writer, original, remote), UNKNOWN)
            delegate.side_effect = RuntimeError('secret')
            self.assertEqual(self.invoke(writer, original, remote), UNKNOWN)
        self.assert_untouched(remote)
        def corrupt(*args, **kwargs):
            result = actuate_fenced(*args, **kwargs)
            self.assertEqual(result['state'], 'VERIFIED', result)
            return dict(result, secret='secret')
        with patch('v2_trusted_writer.actuate_fenced', side_effect=corrupt):
            self.assertEqual(self.invoke(writer, original, remote), UNKNOWN)
        self.assertEqual(self.store.claimed(_bound(original)[3])['state'], 'VERIFIED')
        self.assertEqual(self.invoke(writer, original, remote, True)['state'], 'VERIFIED')
        self.assertEqual(len(remote.sent), 1)

    def test_uncertain_start_never_rearms(self):
        original, remote = self.case()
        writer = self.writer(original, remote)
        start = self.store.start
        def uncertain(key):
            start(key)
            raise OSError('uncertain durable start')
        with patch.object(self.store, 'start', side_effect=uncertain):
            result = self.invoke(writer, original, remote)
        self.assertEqual(result['state'], 'EFFECT_UNKNOWN', result)
        self.assertEqual(self.store.claimed(_bound(original)[3])['state'], 'STARTED')
        with patch.object(self.store, 'start') as restart:
            result = self.invoke(self.writer(original, remote, runtime_state=None, write_token=None),
                                 original, remote, True)
            restart.assert_not_called()
        self.assertIn(result['state'], ('UNRESOLVED', 'EFFECT_UNKNOWN'))
        self.assertFalse(remote.sent)

    def test_lost_process_response_recovery(self):
        original, remote = tf.ActuatorTests.creation_case(self)
        remote.crash = True
        with self.assertRaises(tf.Crash):
            self.invoke(self.writer(original, remote), original, remote)
        self.assertEqual(self.store.claimed(_bound(original)[3])['state'], 'STARTED')
        result = self.invoke(self.writer(original, remote, runtime_state=None, write_token=None),
                             original, remote, True)
        self.assertEqual(result['state'], 'VERIFIED', result)
        self.assertEqual(len(remote.sent), 1)
