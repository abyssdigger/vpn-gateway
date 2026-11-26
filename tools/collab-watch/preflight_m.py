"""Read-only v1 preflight of exact journal and signal bodies; no transport."""
from core import Conflict, canonical, digest, positive, read_comment, require
from journal import (JOURNAL_MARKER, SIGNAL_MARKER, framed, is_journal,
                     physical_ref, project_m)


def _actor(cfg, actor):
    known = {role['actor_id'] for role in cfg['roles'].values()}
    require(positive(actor) and actor in known, 'outgoing actor is not configured')
    return known


def _append(snapshots, room, actor, body):
    cid = max([0, *(read_comment(row)[0] for rows in snapshots.values() for row in rows)]) + 1
    proposed = dict(snapshots)
    proposed[str(room)] = [*snapshots[str(room)], {'id': cid, 'user': {'id': actor}, 'body': body}]
    return proposed, physical_ref(room, cid)


def preflight_journal_fact(cfg, snapshots, actor, body, previous=None):
    """Validate prospective journal replay; never send or persist a synthetic fact."""
    _, state = project_m(cfg, snapshots, previous)
    known = _actor(cfg, actor)
    candidate = framed(body, JOURNAL_MARKER)
    room = candidate.get('room')
    require(positive(room) and room in cfg['task_rooms'], 'outgoing journal room is not configured')
    for task_room in cfg['task_rooms']:
        for row in snapshots[str(task_room)]:
            _, author, text = read_comment(row)
            if author in known and is_journal(text):
                require(framed(text, JOURNAL_MARKER)['event_id'] != candidate.get('event_id'),
                        'outgoing event ID already exists; reconcile delivery instead')
    proposed, ref = _append(snapshots, room, actor, body)
    _, prospective = project_m(cfg, proposed, state)
    del prospective['ledger'][ref]
    return {'event_id': candidate['event_id'], 'kind': candidate['kind'],
            'journal_epoch': cfg['journal_epoch'], 'room': room,
            'body_sha256': digest(body), 'semantic_config_hash': state['semantic_config_hash'],
            'observation_sha256': digest(canonical(state)),
            'prospective_sha256': digest(canonical(prospective))}


def _semantic(projection):
    return {k: v for k, v in projection.items() if k not in {'signal_status', 'gc_candidates', 'integrity'}}


def preflight_signal(cfg, snapshots, actor, body, previous=None):
    """Validate a delivery hint to an already physically admitted journal fact."""
    baseline, state = project_m(cfg, snapshots, previous)
    known = _actor(cfg, actor)
    candidate = framed(body, SIGNAL_MARKER)
    room = cfg['signal_room']
    for row in snapshots[str(room)]:
        _, author, text = read_comment(row)
        if author not in known:
            continue
        try:
            observed = framed(text, SIGNAL_MARKER)
        except Conflict:
            continue
        require(observed.get('signal_id') != candidate.get('signal_id'),
                'outgoing signal ID already exists; reconcile delivery instead')
    proposed, ref = _append(snapshots, room, actor, body)
    after, new_state = project_m(cfg, proposed, state)
    require(any(record['physical_ref'] == ref for record in after['signal_status']['valid']),
            'outgoing signal not admitted')
    require(state == new_state and _semantic(baseline) == _semantic(after),
            'signal changed canonical projection')
    observation = sorted({canonical(read_comment(row)) for row in snapshots[str(room)]})
    return {'signal_id': candidate['signal_id'], 'event_id': candidate['event_id'],
            'journal_epoch': cfg['journal_epoch'], 'signal_room': room,
            'journal_ref': candidate['journal_ref'], 'journal_sha256': candidate['journal_sha256'],
            'recipient': candidate['to'], 'body_sha256': digest(body),
            'semantic_config_hash': state['semantic_config_hash'], 'transport_config_hash': digest(canonical(cfg)),
            'observation_sha256': digest(canonical(state)),
            'signal_observation_sha256': digest(canonical(observation))}
