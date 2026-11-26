"""Read-only preview of an exact outgoing COLLAB event against a complete snapshot."""
from core import canonical, digest, envelope, positive, project, require


def preflight(cfg, snapshots, actor, body, previous=None):
    """Return a binding to the exact body; raise Conflict on unsafe replay.

    Caller supplies a fresh complete observation (and the prior integrity ledger
    when available). No acquisition, persistence, authority or sending is done.
    A successful preview cannot prevent concurrent changes before publication.
    """
    _, state = project(cfg, snapshots, previous)
    require(positive(actor) and actor in {r['actor_id'] for r in cfg['roles'].values()},
            'outgoing actor is not configured')
    require(isinstance(body, str), 'outgoing body must be text')
    candidate = envelope(body)
    room = str(cfg['event_room'])
    legacy = set(cfg['legacy_comments'])
    for row in snapshots[room]:
        if row['user']['id'] in {r['actor_id'] for r in cfg['roles'].values()} and row['id'] not in legacy:
            require(envelope(row['body'])['event_id'] != candidate.get('event_id'),
                    'outgoing event ID already exists; reconcile delivery instead')
    # Never choose an existing or legacy physical identity. The ID is synthetic
    # and is neither returned nor persisted.
    cid = max([0, *legacy, *(row['id'] for rows in snapshots.values() for row in rows)]) + 1
    proposed = dict(snapshots)
    proposed[room] = [*snapshots[room], {'id': cid, 'user': {'id': actor}, 'body': body}]
    _, prospective = project(cfg, proposed, state)
    # Bind newly referenced payloads without binding a fictitious comment ID.
    del prospective['ledger'][f'issue:{room}#issuecomment-{cid}']
    return {'event_id': candidate['event_id'], 'kind': candidate['kind'],
            'body_sha256': digest(body), 'config_hash': state['config_hash'],
            'event_room': cfg['event_room'], 'observation_sha256': digest(canonical(state)),
            'prospective_sha256': digest(canonical(prospective))}
