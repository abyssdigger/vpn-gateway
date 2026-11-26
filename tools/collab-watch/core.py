"""COLLAB v0 deterministic coordination projection; never an authority evaluator."""
from __future__ import annotations

import hashlib
import json
import re

PROTOCOL = 'vpng-collab/0'
IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z')
COMMENT_REF = re.compile(r'issue:([1-9][0-9]*)#issuecomment-([1-9][0-9]*)\Z')
ARTIFACT_REF = re.compile(r'[^\s@:\\]+@[0-9a-f]{40}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
BASE = {'protocol', 'event_id', 'kind', 'room', 'from', 'to', 'incarnation', 'payload_ref'}
SCHEMAS = {
    'OPEN': ({'obligation'}, {'wait_for_event_id', 'artifact_ref'}),
    'INPUT': ({'outcome'}, {'obligation', 'artifact_ref'}),
    'HANDLED': ({'event_ids'}, set()),
    'BLOCK': ({'obligation', 'wait_for_event_id'}, set()),
    'DISPOSITION': ({'obligation', 'disposition', 'closure_ref'}, {'artifact_ref'}),
    'DORMANT': (set(), {'wait_for_event_id'}),
    'PING': ({'ping_id'}, set()),
    'PONG': ({'ping_id'}, set()),
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
    require(isinstance(cfg, dict) and set(cfg) == {'repository', 'event_room', 'task_rooms', 'roles', 'legacy_comments', 'projectholder', 'command_registry'}, 'invalid config fields')
    require(isinstance(cfg['repository'], str) and REPO.fullmatch(cfg['repository']) and all(x not in ('.', '..') for x in cfg['repository'].split('/')), 'invalid repository')
    require(positive(cfg['event_room']), 'invalid event room')
    rooms = cfg['task_rooms']
    require(isinstance(rooms, list) and rooms and all(positive(x) for x in rooms) and len(set(rooms)) == len(rooms) and cfg['event_room'] not in rooms, 'invalid task rooms')
    roles = cfg['roles']
    require(isinstance(roles, dict) and roles, 'no roles')
    for role, spec in roles.items():
        require(ident(role) and isinstance(spec, dict) and set(spec) == {'actor_id', 'incarnation'}, 'invalid role config')
        require(positive(spec['actor_id']) and ident(spec['incarnation']), 'invalid actor/incarnation')
    holder = cfg['projectholder']
    require(isinstance(holder, dict) and set(holder) == {'actor_id', 'room', 'route_to'}, 'invalid projectholder config')
    require(positive(holder['actor_id']) and holder['actor_id'] not in {spec['actor_id'] for spec in roles.values()}, 'holder must have distinct transport actor')
    require(positive(holder['room']) and holder['room'] not in [cfg['event_room'], *rooms], 'invalid holder room')
    route = holder['route_to']
    require(isinstance(route, list) and route and all(isinstance(role, str) and role in roles for role in route) and len(set(route)) == len(route), 'invalid holder routing')
    require('PROJECTHOLDER' not in roles, 'holder is not a scheduled role')
    legacy = cfg['legacy_comments']
    require(isinstance(legacy, list) and all(positive(x) for x in legacy) and len(set(legacy)) == len(legacy), 'invalid legacy comments')
    validate_registry(cfg['command_registry'], roles)
    return cfg


def key_list(value):
    return isinstance(value, list) and all(ident(x) for x in value) and len(set(value)) == len(value)


def validate_registry(registry, roles):
    require(isinstance(registry, dict) and set(registry) == {'cycle', 'capability_scopes', 'condition_keys', 'utc_keys', 'model_scopes'}, 'invalid command registry fields')
    require(ident(registry['cycle']), 'invalid cycle key')
    require(key_list(registry['condition_keys']) and key_list(registry['utc_keys']), 'invalid condition/utc keys')
    caps = registry['capability_scopes']
    require(isinstance(caps, dict) and all(ident(k) and key_list(v) for k, v in caps.items()), 'invalid capability/scope registry')
    models = registry['model_scopes']
    require(isinstance(models, dict) and all(role in roles and isinstance(m, dict) and all(ident(k) and key_list(v) for k, v in m.items()) for role, m in models.items()), 'invalid role/model/scope registry')


def classify_holder_command(body, registry):
    """Recognize only registered whole-comment syntax; do not evaluate authority."""
    key = r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}'
    forms = (
        ('STOP', rf'!COLLAB STOP cycle=(?P<cycle>{key})'),
        ('DENY', rf'!COLLAB DENY capability=(?P<capability>{key}) scope=(?P<scope>{key})'),
        ('ALLOW', rf'!COLLAB ALLOW capability=(?P<capability>{key}) scope=(?P<scope>{key})(?: condition=(?P<condition>{key}))?(?: until=(?P<until>{key}))?'),
        ('MODEL', rf'!COLLAB MODEL role=(?P<role>{key}) model=(?P<model>{key}) scope=(?P<scope>{key})'),
    )
    for kind, pattern in forms:
        match = re.fullmatch(pattern, body)
        if match is None:
            continue
        args = {k: v for k, v in match.groupdict().items() if v is not None}
        if kind == 'STOP':
            valid = args['cycle'] == registry['cycle']
        elif kind in ('DENY', 'ALLOW'):
            valid = (args['scope'] in registry['capability_scopes'].get(args['capability'], [])
                     and ('condition' not in args or args['condition'] in registry['condition_keys'])
                     and ('until' not in args or args['until'] in registry['utc_keys']))
        else:
            valid = args['scope'] in registry['model_scopes'].get(args['role'], {}).get(args['model'], [])
        return {'id': kind, 'args': args} if valid else None
    return None


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
    require(ident(e.get('event_id')) and not e['event_id'].startswith('holder:'), 'invalid or reserved event_id')
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
    if kind in {'PING', 'PONG'}:
        require(recipients != [role], 'health event must address one other worker')
        require(ident(e['ping_id']), 'invalid ping_id')
        require((e['ping_id'] == e['event_id']) == (kind == 'PING'), 'health event identity mismatch')
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
        require(isinstance(e['artifact_ref'], str) and ARTIFACT_REF.fullmatch(e['artifact_ref']) and all(part not in ('', '.', '..') for part in e['artifact_ref'].rsplit('@', 1)[0].split('/')), 'invalid exact artifact ref')
    for field in ('payload_ref', 'closure_ref'):
        if field not in e:
            continue
        ref = e[field]
        match = COMMENT_REF.fullmatch(ref) if isinstance(ref, str) else None
        require(match is not None and int(match[1]) == e['room'] and ref in payloads, 'missing or wrong-room payload')
        require(payloads[ref][0] == actor, 'payload actor mismatch')
    return e


def project_health(events):
    """Replay the complete event set, independently of physical order."""
    pings = {mid: {'ping_id': mid, 'room': e['room'], 'from': e['from'],
                   'to': e['to'][0], 'payload_ref': e['payload_ref'], 'pongs': []}
             for mid, e in sorted(events.items()) if e['kind'] == 'PING'}
    for mid, e in sorted(events.items()):
        if e['kind'] != 'PONG':
            continue
        ping = pings.get(e['ping_id'])
        require(ping is not None, f'PONG references missing admitted PING: {mid}')
        require(e['room'] == ping['room'] and e['from'] == ping['to']
                and e['to'] == [ping['from']], f'PONG room/role mismatch: {mid}')
        ping['pongs'].append({'event_id': mid, 'payload_ref': e['payload_ref']})
    return {'pending': [p for p in pings.values() if not p['pongs']],
            'matched': [p for p in pings.values() if p['pongs']]}


def project(cfg, snapshots, previous=None):
    """Replay complete selected-room snapshots; caller must not pass partial scans."""
    validate_config(cfg)
    rooms = [cfg['event_room'], *cfg['task_rooms'], cfg['projectholder']['room']]
    require(isinstance(snapshots, dict) and set(snapshots) == {str(x) for x in rooms}, 'missing or unexpected room snapshot')
    ledger, payloads, event_comments, ignored, holder_inputs = {}, {}, [], [], {}
    known_actors = {spec['actor_id'] for spec in cfg['roles'].values()}
    seen = {}
    for room in rooms:
        rows = snapshots[str(room)]
        require(isinstance(rows, list), 'snapshot is not a complete comment list')
        for row in rows:
            cid, actor, body = read_comment(row)
            ref = f'issue:{room}#issuecomment-{cid}'
            key = digest(canonical([actor, body]))
            if ref in seen:
                require(seen[ref] == key, f'conflicting physical comment: {ref}')
                continue
            seen[ref] = key
            if room == cfg['event_room']:
                if actor not in known_actors:
                    ignored.append(ref)
                    continue
                ledger[ref] = key
                event_comments.append((cid, actor, body))
            elif room == cfg['projectholder']['room']:
                if actor == cfg['projectholder']['actor_id']:
                    ledger[ref] = key
                    command = classify_holder_command(body, cfg['command_registry'])
                    holder_inputs[f'holder:{cid}'] = {
                        'kind': 'INPUT', 'room': room,
                        'to': sorted(cfg['roles']) if command else list(cfg['projectholder']['route_to']),
                        'payload_ref': ref, 'outcome': 'HOLDER_COMMAND' if command else 'PRODUCT_MANAGER',
                    }
                    if command:
                        holder_inputs[f'holder:{cid}']['command'] = command
                    elif body.startswith('!COLLAB'):
                        holder_inputs[f'holder:{cid}']['command_diagnostic'] = 'unregistered or non-exact syntax; product-manager input only'
                else:
                    ignored.append(ref)
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
    # A complete snapshot is a set of claims. Neither physical IDs nor the
    # order in which pages were fetched constitute a semantic causal clock.
    current, revisions, inputs, handled, dormant, stale = {}, {}, dict(holder_inputs), set(), {}, set()
    events = dict(sorted(events.items()))
    health = project_health(events)

    # Pass 1: collect unique OPEN declarations keyed by explicit revision.
    for mid, e in events.items():
        if e['kind'] != 'OPEN':
            continue
        spec = e['obligation']
        key = (e['room'], spec['id'], spec['revision'])
        require(key not in revisions, f'multiple OPEN claims for revision: {key}')
        ob = dict(room=e['room'], id=spec['id'], revision=spec['revision'],
                  kind=spec['kind'], opened_by_role=e['from'], assignee=spec['assignee'],
                  disposition_by=spec['disposition_by'], status='OPEN',
                  wait_for_event_ids=[e['wait_for_event_id']] if 'wait_for_event_id' in e else [],
                  subject=e['payload_ref'], opened_by=mid)
        if 'artifact_ref' in e:
            ob['artifact_ref'] = e['artifact_ref']
        revisions[key] = ob

    def revision_for(e):
        spec = e['obligation']
        key = (e['room'], spec['id'], spec['revision'])
        require(key in revisions, f'unknown obligation/revision: {e["event_id"]}')
        return revisions[key]

    # Pass 2: terminal claims, independent of delivery ordering. No last-write-wins.
    for mid, e in events.items():
        if e['kind'] != 'DISPOSITION':
            continue
        ob = revision_for(e)
        require(ob['disposition_by'] == e['from'] and e['to'] == [ob['assignee']], f'DISPOSITION not from configured closer: {mid}')
        if ob['status'] != 'OPEN':
            require(ob['status'] == e['disposition'] and ob['closure_ref'] == e['closure_ref'] and ob.get('closure_artifact_ref') == e.get('artifact_ref'), f'conflicting terminal disposition: {mid}')
            continue
        ob.update(status=e['disposition'], closure_ref=e['closure_ref'])
        if 'artifact_ref' in e:
            ob['closure_artifact_ref'] = e['artifact_ref']

    # Pass 3: validate contiguous, explicitly superseded revision chains.
    revisions = dict(sorted(revisions.items()))
    for key, ob in revisions.items():
        oid = key[:2]
        prior = current.get(oid)
        require((prior is None and ob['revision'] == 1) or (
            prior is not None and prior['status'] == 'SUPERSEDED'
            and ob['revision'] == prior['revision'] + 1
            and ob['opened_by_role'] == prior['opened_by_role']
        ), f'invalid OPEN/revision: {ob["opened_by"]}')
        current[oid] = ob

    # Pass 4: validate INPUT and BLOCK references against complete revisions.
    # BLOCK is monotone within a revision: all named dependencies must arrive.
    # An abandoned unresolved dependency requires an explicit new revision.
    for mid, e in events.items():
        kind, sender = e['kind'], e['from']
        if kind not in {'INPUT', 'BLOCK'}:
            continue
        ob = revision_for(e) if 'obligation' in e else None
        if kind == 'INPUT':
            if ob:
                parties = {ob['opened_by_role'], ob['assignee'], ob['disposition_by']}
                require(sender in parties and set(e['to']) <= parties, f'INPUT outside obligation roles: {mid}')
            inputs[mid] = e
        else:
            require(ob['assignee'] == sender, f'BLOCK not from assignee: {mid}')
            ob['wait_for_event_ids'] = sorted(set(ob['wait_for_event_ids']) | {e['wait_for_event_id']})
        if ob and (current[(ob['room'], ob['id'])] is not ob or ob['status'] != 'OPEN'):
            stale.add(mid)

    # Pass 5: handling references exact input identities, not publication order.
    for mid, e in events.items():
        kind, sender = e['kind'], e['from']
        if kind == 'HANDLED':
            for target in e['event_ids']:
                item = inputs.get(target)
                require(item is not None and sender in item['to'] and (e['room'] == item['room'] or target in holder_inputs), f'HANDLED references non-addressed input: {mid}')
                handled.add((sender, target))
        elif kind == 'DORMANT':
            dormant.setdefault(sender, []).append({'event_id': mid, 'payload_ref': e['payload_ref'], 'wait_for_event_id': e.get('wait_for_event_id')})
    roles = {role: {'state': 'WAITING', 'reasons': [], 'blocked': [], 'dormant_claims': dormant.get(role, [])} for role in cfg['roles']}
    for mid, e in sorted(inputs.items()):
        if mid in stale:
            continue
        for role in e['to']:
            if (role, mid) not in handled:
                reason = {'input': mid, 'payload_ref': e['payload_ref'], 'outcome': e['outcome']}
                for field in ('artifact_ref', 'command', 'command_diagnostic'):
                    if field in e:
                        reason[field] = e[field]
                roles[role]['reasons'].append(reason)
    for ob in current.values():
        if ob['status'] != 'OPEN':
            continue
        role = ob['assignee']
        missing = []
        for pred in ob['wait_for_event_ids']:
            if pred in events or pred in inputs:
                target = inputs.get(pred)
                require(target is not None and pred not in stale and target['room'] == ob['room'] and role in target['to'] and target.get('obligation') == {'id': ob['id'], 'revision': ob['revision']}, f'wait predicate does not match obligation: {pred}')
            else:
                missing.append(pred)
        if not missing:
            reason = {'obligation': ob['id'], 'revision': ob['revision'], 'payload_ref': ob['subject']}
            if 'artifact_ref' in ob:
                reason['artifact_ref'] = ob['artifact_ref']
            roles[role]['reasons'].append(reason)
        else:
            roles[role]['blocked'].append({'obligation': ob['id'], 'revision': ob['revision'], 'awaiting': missing})
    for item in roles.values():
        if item['reasons']:
            item['state'] = 'READY'
    projection = {'protocol': PROTOCOL, 'roles': roles, 'health': health, 'obligations': list(revisions.values()), 'stale_events': sorted(stale), 'ignored_external': sorted(ignored), 'integrity': 'fresh observation' if previous is None else 'prior observed comments matched', 'authority': 'not evaluated; coordination claims only'}
    return projection, {'config_hash': config_hash, 'ledger': ledger}
