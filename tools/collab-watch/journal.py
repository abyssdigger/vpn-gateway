"""COLLAB v1 journal/signal admission and read-only GC projection.

The v0 semantic reducer is shared; no signal or receipt can create an
independent semantic truth. Physical identities always name real comments.
"""
from __future__ import annotations

import re

from core import (COMMENT_REF, Conflict, canonical, checked_config_hash, digest, holder_input, ident,
                  integrity_state, read_comment, reduce_events, require, strict_json,
                  validate_config, validate_event)

PROTOCOL = 'vpng-collab/1'
JOURNAL_PREFIX = '<!-- vpng-collab-journal/'
JOURNAL_MARKER = JOURNAL_PREFIX + '1 -->'
SIGNAL_PROTOCOL = 'vpng-collab-signal/1'
SIGNAL_MARKER = '<!-- ' + SIGNAL_PROTOCOL + ' -->'
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
SIGNAL_FIELDS = {'protocol', 'journal_epoch', 'signal_id', 'event_id', 'journal_ref',
                 'journal_sha256', 'from', 'to', 'incarnation'}


def validate_m_config(cfg):
    require(isinstance(cfg, dict) and set(cfg) == {'protocol', 'repository', 'signal_room',
            'task_rooms', 'journal_epoch', 'roles', 'projectholder', 'command_registry'},
            'invalid v1 config fields')
    require(cfg['protocol'] == PROTOCOL and ident(cfg['journal_epoch']), 'invalid v1 protocol/epoch')
    # Reuse v0's common structural checks. This is config validation only:
    # no physical refs, ledger, room acquisition or semantic replay use this alias.
    common = {k: v for k, v in cfg.items() if k not in {'protocol', 'journal_epoch', 'signal_room'}}
    validate_config(dict(common, event_room=cfg['signal_room'], legacy_comments=[]))
    return cfg


def semantic_config(cfg):
    """V1 semantic config is fixed within a journal epoch; signal transport is separate."""
    return {k: v for k, v in cfg.items() if k != 'signal_room'}


def framed(body, marker):
    require(isinstance(body, str) and len(body.encode('utf-8')) <= 8192, 'machine frame too large or not text')
    match = re.fullmatch(re.escape(marker) + r'\n```json\n(.*?)\n```', body, re.DOTALL)
    require(match is not None, 'invalid machine framing')
    obj = strict_json(match[1])
    require(isinstance(obj, dict), 'machine object required')
    return obj


def is_journal(body):
    return body.startswith(JOURNAL_PREFIX)


def physical_ref(room, cid):
    return f'issue:{room}#issuecomment-{cid}'


def is_sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def is_ref(value):
    return isinstance(value, str) and COMMENT_REF.fullmatch(value) is not None


def receipt_targets(value):
    require(isinstance(value, list) and 0 < len(value) <= 100, 'invalid handled targets')
    refs = set()
    for target in value:
        require(isinstance(target, dict) and set(target) == {'event_id', 'ref', 'body_sha256'}
                and ident(target['event_id']) and is_ref(target['ref']) and is_sha(target['body_sha256']),
                'invalid handled target')
        require(target['ref'] not in refs, 'duplicate handled physical target')
        refs.add(target['ref'])
    return value


def journal_event(body, actor, room, cfg, payloads):
    event = framed(body, JOURNAL_MARKER)
    require(event.get('journal_epoch') == cfg['journal_epoch'], 'wrong journal epoch')
    # The framing and epoch are transport admission, not semantic rules.
    semantic = {k: v for k, v in event.items() if k != 'journal_epoch'}
    targets = []
    if semantic.get('kind') == 'HANDLED':
        require('event_ids' not in semantic, 'bare handled IDs are not v1 receipts')
        targets = receipt_targets(semantic.pop('handled', None))
        # Existing event validator checks shape, actor, role, and payload.
        # Exact receipt targets will be resolved against the full fact index.
        semantic['event_ids'] = sorted({t['event_id'] for t in targets})
    validate_event(semantic, actor, cfg, payloads, protocol=PROTOCOL, payload_actor_required=False)
    require(semantic['room'] == room, 'journal physical/semantic room mismatch')
    return semantic, targets


def signal_record(obj, actor, cfg, facts):
    require(set(obj) == SIGNAL_FIELDS and obj['protocol'] == SIGNAL_PROTOCOL,
            'invalid signal fields/protocol')
    require(obj['journal_epoch'] == cfg['journal_epoch'], 'wrong signal epoch')
    require(ident(obj['signal_id']) and ident(obj['event_id']) and is_ref(obj['journal_ref'])
            and is_sha(obj['journal_sha256']), 'invalid signal identity/reference')
    sender, recipient = obj['from'], obj['to']
    require(ident(sender) and sender in cfg['roles'] and ident(recipient) and recipient in cfg['roles'],
            'invalid signal roles')
    require(cfg['roles'][sender]['actor_id'] == actor
            and cfg['roles'][sender]['incarnation'] == obj['incarnation'], 'unadmitted signal actor/incarnation')
    fact = facts.get(obj['journal_ref'])
    require(fact is not None, 'signal target not admitted')
    event, sha = fact['event'], fact['body_sha256']
    require(event['kind'] != 'HANDLED' and event['event_id'] == obj['event_id']
            and sha == obj['journal_sha256'] and sender == event['from']
            and obj['incarnation'] == event['incarnation'] and recipient in event['to'],
            'signal target/digest/sender/recipient mismatch')
    return {k: obj[k] for k in ('signal_id', 'event_id', 'journal_ref', 'journal_sha256')} | {'recipient': recipient}


def project_signals(cfg, rows, facts, receipts):
    """Project ephemeral observations only; never update the canonical ledger."""
    known = {spec['actor_id'] for spec in cfg['roles'].values()}
    variants = {}
    for row in rows:
        cid, actor, body = read_comment(row)
        ref = physical_ref(cfg['signal_room'], cid)
        variants.setdefault(ref, set()).add((actor, body))
    records, conflicts, groups, ignored = {}, {}, {}, []
    for ref, observed in sorted(variants.items()):
        if all(actor not in known for actor, _ in observed):
            ignored.append(ref)
            continue
        if len(observed) != 1:
            conflicts[ref] = 'conflicting physical signal comment'
        for actor, body in sorted(observed):
            if actor not in known:
                continue
            try:
                obj = framed(body, SIGNAL_MARKER)
                # Collect even schema-invalid claims with a parseable signal ID;
                # a valid duplicate must not mask a conflicting identity.
                if ident(obj.get('signal_id')):
                    groups.setdefault(obj['signal_id'], []).append((ref, digest(canonical([actor, body]))))
                item = signal_record(obj, actor, cfg, facts)
                records[ref] = dict(item, physical_ref=ref, actor_id=actor, body_sha256=digest(body),
                                    receipt_refs=sorted(receipts.get((item['journal_ref'], item['recipient']), ())))
            except Conflict as exc:
                conflicts.setdefault(ref, str(exc))
    for group in groups.values():
        if len({fingerprint for _, fingerprint in group}) > 1:
            for ref, _ in group:
                conflicts.setdefault(ref, 'conflicting logical signal identity')
    valid = [item for ref, item in sorted(records.items()) if ref not in conflicts]
    return {'valid': valid, 'unconsumed': [item['physical_ref'] for item in valid if not item['receipt_refs']],
            'conflicts': [{'physical_ref': ref, 'reason': reason} for ref, reason in sorted(conflicts.items())],
            'ignored_external': ignored}, [item for item in valid if item['receipt_refs']]


def _raw_row(cfg, room, row):
    cid, actor, body = read_comment(row)
    return cid, actor, body, digest(canonical([actor, body]))


def project_m(cfg, snapshots, previous=None):
    """Replay a complete stable v1 observation. Local state is derivative only."""
    return _project_m(cfg, snapshots, previous, _raw_row)


def project_m_compact(cfg, observation, previous=None):
    """Replay trusted typed compact observations through the same reducer."""
    from compact_observation import compact_snapshots, read_compact_row
    return _project_m(cfg, compact_snapshots(cfg, observation), previous, read_compact_row)


def _project_m(cfg, snapshots, previous, reader):
    validate_m_config(cfg)
    semantic_cfg = semantic_config(cfg)
    if previous is not None:
        require(isinstance(previous, dict) and set(previous) == {'protocol', 'semantic_config_hash', 'ledger'}
                and previous['protocol'] == PROTOCOL, 'invalid v1 retained state')
        previous = {'config_hash': previous['semantic_config_hash'], 'ledger': previous['ledger']}
    checked_config_hash(semantic_cfg, previous)
    rooms = [*cfg['task_rooms'], cfg['projectholder']['room'], cfg['signal_room']]
    require(isinstance(snapshots, dict) and set(snapshots) == {str(room) for room in rooms},
            'missing or unexpected room snapshot')
    require(all(isinstance(rows, list) for rows in snapshots.values()), 'snapshot is not a complete comment list')
    known = {spec['actor_id'] for spec in cfg['roles'].values()}
    seen, ledger, payloads, journal_rows, ignored, holder_inputs, holder_facts = {}, {}, {}, {}, [], {}, {}
    opaque_refs = set()
    # Partition before admitting any fact, so payload references can resolve
    # regardless of physical comment order, including forward references.
    for room in rooms[:-1]:
        for row in snapshots[str(room)]:
            cid, actor, body, key = reader(cfg, room, row)
            ref = physical_ref(room, cid)
            if ref in seen:
                require(seen[ref] == key and (ref in opaque_refs) == (body is None),
                        f'conflicting physical comment: {ref}')
                continue
            seen[ref] = key
            if body is None:
                opaque_refs.add(ref)
            if room == cfg['projectholder']['room']:
                if actor != cfg['projectholder']['actor_id']:
                    ignored.append(ref)
                    continue
                ledger[ref] = key
                mid = f'holder:{cid}'
                item = holder_input(cfg, ref, body)
                holder_inputs[mid] = item
                holder_facts[ref] = {'event': dict(item, event_id=mid), 'body_sha256': digest(body)}
            elif body is not None and is_journal(body):
                if actor not in known:
                    ignored.append(ref)
                    continue
                journal_rows[ref] = (room, actor, body)
            else:
                payloads[ref] = (actor, body)
    events, fingerprints, facts, pending_receipts = {}, {}, {}, {}
    for ref, (room, actor, body) in sorted(journal_rows.items()):
        try:
            event, targets = journal_event(body, actor, room, cfg, payloads)
            mid, key = event['event_id'], seen[ref]
            require(mid not in fingerprints or fingerprints[mid] == key, f'conflicting logical event: {mid}')
            fingerprints[mid] = key
            events[mid] = event
            facts[ref] = {'event': event, 'body_sha256': digest(body)}
            ledger[ref] = key
            for field in ('payload_ref', 'closure_ref'):
                if field in event:
                    ledger[event[field]] = seen[event[field]]
            if targets:
                pending_receipts[ref] = targets
        except Conflict as exc:
            raise Conflict(f'journal comment {ref}: {exc}') from exc
    receipts = {}
    for ref, targets in sorted(pending_receipts.items()):
        event = facts[ref]['event']
        semantic_ids = set()
        for target in targets:
            tref = target['ref']
            fact = facts.get(tref) or holder_facts.get(tref)
            require(fact is not None, f'HANDLED target not admitted: {ref}')
            item = fact['event']
            require(item['kind'] != 'HANDLED' and item['event_id'] == target['event_id']
                    and fact['body_sha256'] == target['body_sha256'] and event['from'] in item['to']
                    and (tref in holder_facts or item['room'] == event['room']),
                    f'HANDLED target identity/content/recipient mismatch: {ref}')
            receipts.setdefault((tref, event['from']), set()).add(ref)
            if item['kind'] == 'INPUT':
                semantic_ids.add(item['event_id'])
        # Keep HANDLED in the reducer's logical event set (e.g. so a BLOCK
        # cannot mistake a delivery-only HANDLED identity for missing INPUT).
        # Only semantic INPUT targets are passed to its handled-set logic.
        events[event['event_id']] = dict(event, event_ids=sorted(semantic_ids))
    state = integrity_state(semantic_cfg, ledger, previous)
    projection = reduce_events(cfg, events, holder_inputs, ignored,
                               'fresh observation' if previous is None else 'prior observed comments matched', PROTOCOL)
    signal_status, gc = project_signals(cfg, snapshots[str(cfg['signal_room'])], facts, receipts)
    projection.update(journal_epoch=cfg['journal_epoch'], signal_status=signal_status, gc_candidates=gc)
    return projection, {'protocol': PROTOCOL, 'semantic_config_hash': state['config_hash'], 'ledger': state['ledger']}
