"""COLLAB v0 deterministic coordination projection; never an authority evaluator."""
from __future__ import annotations

import hashlib
import json
import re

PROTOCOL = 'vpng-collab/0'
IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z')
COMMENT_REF = re.compile(r'issue:([1-9][0-9]*)#issuecomment-([1-9][0-9]*)\Z')
ARTIFACT_REF = re.compile(r'[^\s@]+@[0-9a-f]{40}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
BASE = {'protocol', 'event_id', 'kind', 'room', 'from', 'to', 'incarnation', 'payload_ref'}
SCHEMAS = {
    'OPEN': ({'obligation'}, {'wait_for_event_id', 'artifact_ref'}),
    'INPUT': ({'outcome'}, {'obligation', 'artifact_ref'}),
    'HANDLED': ({'event_ids'}, set()),
    'BLOCK': ({'obligation', 'wait_for_event_id'}, set()),
    'DISPOSITION': ({'obligation', 'disposition', 'closure_ref'}, {'artifact_ref'}),
    'DORMANT': (set(), {'wait_for_event_id'}),
}


class Conflict(ValueError):
    """The observation must not yield a new readiness recommendation."""


def require(condition, message):
    if not condition:
        raise Conflict(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def strict_json(value):
    def pairs(items):
        result = {}
        for key, val in items:
            require(key not in result, f'duplicate JSON field: {key}')
            result[key] = val
        return result

    def bad_constant(value):
        raise Conflict(f'invalid JSON constant: {value}')

    try:
        return json.loads(value, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise Conflict(f'invalid JSON: {exc}') from exc


def positive(value):
    return type(value) is int and value > 0


def ident(value):
    return isinstance(value, str) and IDENT.fullmatch(value) is not None


def validate_config(cfg):
    require(isinstance(cfg, dict) and set(cfg) == {'repository', 'event_room', 'task_rooms', 'roles', 'legacy_comments'}, 'invalid config fields')
    require(isinstance(cfg['repository'], str) and REPO.fullmatch(cfg['repository']), 'invalid repository')
    require(positive(cfg['event_room']), 'invalid event room')
    rooms = cfg['task_rooms']
    require(isinstance(rooms, list) and rooms and all(positive(x) for x in rooms) and len(set(rooms)) == len(rooms) and cfg['event_room'] not in rooms, 'invalid task rooms')
    roles = cfg['roles']
    require(isinstance(roles, dict) and roles, 'no roles')
    for role, spec in roles.items():
        require(ident(role) and isinstance(spec, dict) and set(spec) == {'actor_id', 'incarnation'}, 'invalid role config')
        require(positive(spec['actor_id']) and ident(spec['incarnation']), 'invalid actor/incarnation')
    legacy = cfg['legacy_comments']
    require(isinstance(legacy, list) and all(positive(x) for x in legacy) and len(set(legacy)) == len(legacy), 'invalid legacy comments')
    return cfg


def read_comment(comment):
    require(isinstance(comment, dict) and positive(comment.get('id')), 'invalid comment identity')
    require(isinstance(comment.get('user'), dict) and positive(comment['user'].get('id')), 'invalid comment actor')
    require(isinstance(comment.get('body'), str), 'missing comment body')
    return comment['id'], comment['user']['id'], comment['body']


def envelope(body):
    require(len(body.encode('utf-8')) <= 8192, 'event too large')
    match = re.fullmatch(r'```json\n(.*?)\n```(?:\n(.*))?', body, re.DOTALL)
    require(match is not None, 'expected one fenced JSON control event')
    note = match[2] or ''
    require(len(note.encode('utf-8')) <= 512 and '```' not in note, 'invalid control note')
    event = strict_json(match[1])
    require(isinstance(event, dict), 'event must be an object')
    return event


def validate_event(e, actor, cfg, payloads):
    require(e.get('protocol') == PROTOCOL, 'unknown protocol')
    require(ident(e.get('event_id')), 'invalid event_id')
    kind = e.get('kind')
    require(isinstance(kind, str) and kind in SCHEMAS, 'unknown event kind')
    mandatory, optional = SCHEMAS[kind]
    require(BASE | mandatory <= set(e) <= BASE | mandatory | optional, 'missing/unknown fields')
    require(positive(e['room']) and e['room'] in cfg['task_rooms'], 'unknown task room')
    role = e['from']
    roles = cfg['roles']
    require(isinstance(role, str) and role in roles, 'unknown sender role')
    require(roles[role]['actor_id'] == actor and roles[role]['incarnation'] == e['incarnation'], 'unadmitted actor/incarnation')
    recipients = e['to']
    require(isinstance(recipients, list) and recipients and all(isinstance(x, str) and x in roles for x in recipients) and len(set(recipients)) == len(recipients), 'invalid recipients')
    if kind != 'INPUT':
        require(len(recipients) == 1, 'expected a single recipient')
    if kind in {'HANDLED', 'BLOCK', 'DORMANT'}:
        require(recipients == [role], 'self control claim must address self')
    if 'obligation' in e:
        ob = e['obligation']
        keys = {'id', 'revision'} | ({'kind', 'assignee', 'disposition_by'} if kind == 'OPEN' else set())
        require(isinstance(ob, dict) and set(ob) == keys and ident(ob['id']) and positive(ob['revision']), 'invalid obligation')
        if kind == 'OPEN':
            require(ident(ob['kind']) and ob['assignee'] == recipients[0] and isinstance(ob['disposition_by'], str) and ob['disposition_by'] in roles, 'invalid obligation roles/kind')
    if 'wait_for_event_id' in e:
        require(ident(e['wait_for_event_id']) and e['wait_for_event_id'] != e['event_id'], 'invalid wait predicate')
    if kind == 'INPUT':
        require(e['outcome'] in ('ANSWER', 'PARTIAL', 'NEEDS_INFO', 'REJECTED'), 'invalid input outcome')
    if kind == 'HANDLED':
        ids = e['event_ids']
        require(isinstance(ids, list) and ids and len(ids) <= 100 and all(ident(x) for x in ids) and len(set(ids)) == len(ids), 'invalid handled IDs')
    if kind == 'DISPOSITION':
        require(e['disposition'] in ('CLOSED', 'CANCELLED', 'SUPERSEDED'), 'invalid terminal disposition')
    if 'artifact_ref' in e:
        require(isinstance(e['artifact_ref'], str) and ARTIFACT_REF.fullmatch(e['artifact_ref']), 'invalid exact artifact ref')
    for field in ('payload_ref', 'closure_ref'):
        if field not in e:
            continue
        ref = e[field]
        match = COMMENT_REF.fullmatch(ref) if isinstance(ref, str) else None
        require(match is not None and int(match[1]) == e['room'] and ref in payloads, 'missing or wrong-room payload')
        require(payloads[ref][0] == actor, 'payload actor mismatch')
    return e


def project(cfg, snapshots, previous=None):
    """Replay complete selected-room snapshots; caller must not pass partial scans."""
    validate_config(cfg)
    require(isinstance(snapshots, dict) and set(snapshots) == {str(x) for x in [cfg['event_room'], *cfg['task_rooms']]}, 'missing or unexpected room snapshot')
    ledger, payloads, event_comments, ignored = {}, {}, [], []
    known_actors = {spec['actor_id'] for spec in cfg['roles'].values()}
    seen = {}
    for room in [cfg['event_room'], *cfg['task_rooms']]:
        rows = snapshots[str(room)]
        require(isinstance(rows, list), 'snapshot is not a complete comment list')
        for row in rows:
            cid, actor, body = read_comment(row)
            ref = f'issue:{room}#issuecomment-{cid}'
            key = digest(canonical([actor, body]))
            if cid in seen:
                require(seen[cid] == (ref, key), f'conflicting physical comment: {ref}')
                continue
            seen[cid] = (ref, key)
            if room == cfg['event_room']:
                if actor not in known_actors:
                    ignored.append(ref)
                    continue
                ledger[ref] = key
                event_comments.append((cid, actor, body))
            else:
                payloads[ref] = (actor, body)
    events, fingerprints = {}, {}
    for cid, actor, body in sorted(event_comments):
        if cid in cfg['legacy_comments']:
            continue
        try:
            e = validate_event(envelope(body), actor, cfg, payloads)
            mid = e['event_id']
            fingerprint = digest(canonical([actor, body]))
            for field in ('payload_ref', 'closure_ref'):
                if field in e:
                    ref = e[field]
                    ledger[ref] = digest(canonical(list(payloads[ref])))
            if mid in fingerprints:
                require(fingerprints[mid] == fingerprint, f'conflicting logical event: {mid}')
                continue
            fingerprints[mid] = fingerprint
            events[mid] = e
        except Conflict as exc:
            raise Conflict(f'event comment {cid}: {exc}') from exc
    config_hash = digest(canonical(cfg))
    if previous is not None:
        require(isinstance(previous, dict) and set(previous) == {'config_hash', 'ledger'} and previous['config_hash'] == config_hash and isinstance(previous['ledger'], dict), 'state/config mismatch; explicit operator reconciliation required')
        for ref, old in previous['ledger'].items():
            require(ledger.get(ref) == old, f'prior observed comment missing or changed: {ref}')
    current, revisions, inputs, handled, dormant, stale = {}, {}, {}, set(), {}, []
    for mid, e in events.items():
        kind, room, sender = e['kind'], e['room'], e['from']
        spec = e.get('obligation')
        oid = (room, spec['id']) if spec else None
        rev = spec['revision'] if spec else None
        ob = current.get(oid)
        historical = revisions.get((*oid, rev)) if oid else None
        if kind == 'OPEN':
            require((ob is None and rev == 1) or (ob is not None and ob['status'] == 'SUPERSEDED' and rev == ob['revision'] + 1 and sender == ob['opened_by_role']), f'invalid OPEN/revision: {mid}')
            ob = dict(room=room, id=spec['id'], revision=rev, kind=spec['kind'], opened_by_role=sender, assignee=spec['assignee'], disposition_by=spec['disposition_by'], status='OPEN', wait_for_event_id=e.get('wait_for_event_id'), subject=e['payload_ref'], opened_by=mid)
            if 'artifact_ref' in e:
                ob['artifact_ref'] = e['artifact_ref']
            current[oid] = ob
            revisions[(*oid, rev)] = ob
        elif kind in {'INPUT', 'BLOCK', 'DISPOSITION'}:
            if oid:
                require(historical is not None, f'unknown obligation/revision: {mid}')
            if kind == 'INPUT':
                if historical:
                    parties = {historical['opened_by_role'], historical['assignee'], historical['disposition_by']}
                    require(sender in parties and set(e['to']) <= parties, f'INPUT outside obligation roles: {mid}')
                inputs[mid] = e
                if historical and (historical is not ob or ob['status'] != 'OPEN'):
                    stale.append(mid)
            elif kind == 'BLOCK':
                require(historical['assignee'] == sender, f'BLOCK not from assignee: {mid}')
                if historical is not ob or ob['status'] != 'OPEN':
                    stale.append(mid)
                    continue
                ob['wait_for_event_id'] = e['wait_for_event_id']
            else:
                require(historical['disposition_by'] == sender and e['to'] == [historical['assignee']], f'DISPOSITION not from configured closer: {mid}')
                if historical['status'] != 'OPEN':
                    require(historical['status'] == e['disposition'] and historical.get('closure_ref') == e['closure_ref'], f'conflicting terminal disposition: {mid}')
                    stale.append(mid)
                    continue
                require(historical is ob, f'non-current open revision: {mid}')
                ob.update(status=e['disposition'], closure_ref=e['closure_ref'])
                if 'artifact_ref' in e:
                    ob['closure_artifact_ref'] = e['artifact_ref']
        elif kind == 'HANDLED':
            for target in e['event_ids']:
                item = inputs.get(target)
                require(item is not None and sender in item['to'] and room == item['room'], f'HANDLED references non-addressed input: {mid}')
                handled.add((sender, target))
        elif kind == 'DORMANT':
            dormant[sender] = {'event_id': mid, 'payload_ref': e['payload_ref'], 'wait_for_event_id': e.get('wait_for_event_id')}
    roles = {role: {'state': 'WAITING', 'reasons': [], 'blocked': [], 'dormant_claim': dormant.get(role)} for role in cfg['roles']}
    stale_set = set(stale)
    for mid, e in inputs.items():
        spec = e.get('obligation')
        if mid in stale_set or (spec and current[(e['room'], spec['id'])]['revision'] != spec['revision']):
            continue
        for role in e['to']:
            if (role, mid) not in handled:
                reason = {'input': mid, 'payload_ref': e['payload_ref'], 'outcome': e['outcome']}
                if 'artifact_ref' in e:
                    reason['artifact_ref'] = e['artifact_ref']
                roles[role]['reasons'].append(reason)
    for ob in current.values():
        if ob['status'] != 'OPEN':
            continue
        role = ob['assignee']
        pred = ob['wait_for_event_id']
        target = inputs.get(pred) if pred else None
        if pred and pred in events:
            require(target is not None and pred not in stale_set and target['room'] == ob['room'] and role in target['to'] and target.get('obligation') == {'id': ob['id'], 'revision': ob['revision']}, f'wait predicate does not match obligation: {pred}')
        if pred is None or target is not None:
            reason = {'obligation': ob['id'], 'revision': ob['revision'], 'payload_ref': ob['subject']}
            if 'artifact_ref' in ob:
                reason['artifact_ref'] = ob['artifact_ref']
            roles[role]['reasons'].append(reason)
        else:
            roles[role]['blocked'].append({'obligation': ob['id'], 'revision': ob['revision'], 'awaiting': pred})
    for item in roles.values():
        if item['reasons']:
            item['state'] = 'READY'
    projection = {'protocol': PROTOCOL, 'roles': roles, 'obligations': list(revisions.values()), 'stale_events': stale, 'ignored_external': sorted(ignored), 'integrity': 'fresh observation' if previous is None else 'prior observed comments matched', 'authority': 'not evaluated; coordination claims only'}
    return projection, {'config_hash': config_hash, 'ledger': ledger}
