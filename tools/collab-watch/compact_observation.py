"""Typed transport seam after trusted complete raw acquisition; no network or authority."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from core import canonical, digest, positive, read_comment, require, strict_json

WIRE_PROTOCOL = 'vpng-collab-compact-observation/1'


@dataclass(frozen=True, slots=True)
class OpaqueObservationRow:
    kind: str
    comment_id: int
    actor_id: int
    row_sha256: str


@dataclass(frozen=True, slots=True)
class CompactObservation:
    config_hash: str
    rooms: Mapping[str, tuple]


def _rooms(cfg):
    return [*cfg['task_rooms'], cfg['projectholder']['room'], cfg['signal_room']]


def _check_rooms(cfg, rooms):
    require(set(rooms) == {str(room) for room in _rooms(cfg)}, 'missing or unexpected room snapshot')


def compact_observation(cfg, snapshots):
    """Classify trusted raw rows, preserving their exact canonical row digests.

    Completeness/stability must already have been established by acquisition.
    The compact form cannot establish provenance or restore a lost ledger.
    """
    from journal import is_journal, validate_m_config
    validate_m_config(cfg)
    require(isinstance(snapshots, dict), 'invalid raw snapshot')
    _check_rooms(cfg, snapshots)
    require(all(isinstance(rows, list) for rows in snapshots.values()), 'snapshot is not a complete comment list')
    result = {}
    for room in _rooms(cfg):
        rows = []
        for raw in snapshots[str(room)]:
            cid, actor, body = read_comment(raw)
            kind = None
            if room in cfg['task_rooms'] and not is_journal(body):
                kind = 'task_payload'
            elif room == cfg['projectholder']['room'] and actor != cfg['projectholder']['actor_id']:
                kind = 'holder_ignored'
            if kind is None:
                rows.append({'id': cid, 'user': {'id': actor}, 'body': body})
            else:
                rows.append(OpaqueObservationRow(kind, cid, actor, digest(canonical([actor, body]))))
        result[str(room)] = tuple(rows)
    return CompactObservation(digest(canonical(cfg)), MappingProxyType(result))


def read_compact_row(cfg, room, row):
    """Return identity/body-or-None/digest. Only opaque non-semantic rows omit body."""
    from journal import is_sha
    if not isinstance(row, OpaqueObservationRow):
        cid, actor, body = read_comment(row)
        return cid, actor, body, digest(canonical([actor, body]))
    require(positive(row.comment_id) and positive(row.actor_id) and is_sha(row.row_sha256),
            'invalid opaque observation row')
    require((row.kind == 'task_payload' and room in cfg['task_rooms'])
            or (row.kind == 'holder_ignored' and room == cfg['projectholder']['room']
                and row.actor_id != cfg['projectholder']['actor_id']), 'opaque row in forbidden partition')
    return row.comment_id, row.actor_id, None, row.row_sha256


def compact_snapshots(cfg, observation):
    from journal import validate_m_config
    validate_m_config(cfg)
    require(isinstance(observation, CompactObservation) and observation.config_hash == digest(canonical(cfg)),
            'compact observation/config mismatch')
    require(isinstance(observation.rooms, Mapping), 'invalid compact rooms')
    _check_rooms(cfg, observation.rooms)
    result = {}
    for room in _rooms(cfg):
        rows = observation.rooms[str(room)]
        require(isinstance(rows, tuple), 'invalid compact room rows')
        # Validate partition/shape before returning any observation. Duplicate
        # physical semantics remain owned by the same canonical projector.
        for row in rows:
            read_compact_row(cfg, room, row)
        result[str(room)] = list(rows)
    return result


def encode_compact(cfg, observation):
    snapshots = compact_snapshots(cfg, observation)
    rooms = {}
    for room, rows in snapshots.items():
        items = []
        for row in rows:
            if isinstance(row, OpaqueObservationRow):
                items.append([row.kind, row.comment_id, row.actor_id, row.row_sha256])
            else:
                cid, actor, body = read_comment(row)
                items.append(['raw', cid, actor, body])
        rooms[room] = items
    return canonical({'protocol': WIRE_PROTOCOL, 'config_hash': observation.config_hash, 'rooms': rooms})


def decode_compact(cfg, text, expected_sha256):
    from journal import is_sha, validate_m_config
    validate_m_config(cfg)
    require(isinstance(text, str) and is_sha(expected_sha256) and digest(text) == expected_sha256,
            'compact transfer digest mismatch')
    value = strict_json(text)
    require(isinstance(value, dict) and set(value) == {'protocol', 'config_hash', 'rooms'}
            and value['protocol'] == WIRE_PROTOCOL and isinstance(value['rooms'], dict)
            and canonical(value) == text, 'invalid compact wire object')
    _check_rooms(cfg, value['rooms'])
    rooms = {}
    for room, rows in value['rooms'].items():
        require(isinstance(rows, list), 'invalid compact wire room')
        items = []
        for row in rows:
            require(isinstance(row, list) and len(row) == 4 and row[0] in ('raw', 'task_payload', 'holder_ignored'),
                    'invalid compact wire row')
            kind, cid, actor, data = row
            if kind == 'raw':
                items.append({'id': cid, 'user': {'id': actor}, 'body': data})
            else:
                items.append(OpaqueObservationRow(kind, cid, actor, data))
        rooms[room] = tuple(items)
    observation = CompactObservation(value['config_hash'], MappingProxyType(rooms))
    compact_snapshots(cfg, observation)
    return observation
