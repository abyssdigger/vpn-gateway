"""One-shot GC rehearsal over an injected transport; no GitHub adapter or authority."""
from dataclasses import dataclass
import hashlib
import json
import re


IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z')
REF = re.compile(r'issue:([1-9][0-9]*)#issuecomment-([1-9][0-9]*)\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
FIELDS = {'physical_ref', 'actor_id', 'body_sha256', 'signal_id', 'event_id',
          'journal_ref', 'journal_sha256', 'recipient', 'receipt_refs'}


class Rejected(ValueError):
    """Invalid scope/candidate/permit; no transport operations attempted."""


def require(condition, message):
    if not condition:
        raise Rejected(message)


def positive(value):
    return type(value) is int and value > 0


def matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def parse_ref(value):
    require(matches(REF, value), 'invalid physical comment reference')
    try:
        return tuple(map(int, REF.fullmatch(value).groups()))
    except ValueError as exc:
        raise Rejected('invalid physical comment identity') from exc


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def candidate_digest(candidate):
    """Bind every candidate field, including receipts, using projector canonical JSON."""
    return digest(json.dumps(candidate, sort_keys=True, separators=(',', ':'), ensure_ascii=False))


@dataclass(frozen=True)
class Observation:
    repository: str
    room: int
    comment_id: int
    actor_id: int
    body: str


@dataclass(frozen=True)
class Result:
    status: str
    delete_attempts: int


def _validate(scope, candidate, permit):
    require(type(scope) is dict and set(scope) == {'repository', 'signal_room'}, 'invalid scope')
    repo, room = scope['repository'], scope['signal_room']
    require(matches(REPO, repo) and all(p not in ('.', '..') for p in repo.split('/')),
            'invalid repository')
    require(positive(room), 'invalid signal room')
    require(type(candidate) is dict and set(candidate) == FIELDS, 'invalid candidate fields')
    candidate_room, cid = parse_ref(candidate['physical_ref'])
    require(candidate_room == room, 'candidate outside signal room')
    require(positive(candidate['actor_id']), 'invalid candidate actor')
    require(all(matches(SHA, candidate[k]) for k in ('body_sha256', 'journal_sha256')),
            'invalid candidate digest')
    require(all(matches(IDENT, candidate[k]) for k in ('signal_id', 'event_id', 'recipient')),
            'invalid candidate identity')
    journal_room, _ = parse_ref(candidate['journal_ref'])
    require(journal_room != room, 'journal target in signal room')
    refs = candidate['receipt_refs']
    require(type(refs) is list and bool(refs), 'no receipt references')
    require(all(parse_ref(ref)[0] != room for ref in refs), 'receipt in signal room')
    require(len(set(refs)) == len(refs), 'duplicate receipt reference')
    require(type(permit) is dict and set(permit) == {'repository', 'signal_room', 'candidate_sha256'},
            'external exact permit required')
    require(type(permit['repository']) is str and permit['repository'] == repo
            and positive(permit['signal_room']) and permit['signal_room'] == room
            and matches(SHA, permit['candidate_sha256'])
            and permit['candidate_sha256'] == candidate_digest(candidate), 'permit mismatch')
    return repo, room, cid, candidate['actor_id'], candidate['body_sha256']


def _matches_observation(observed, repo, room, cid, actor, sha):
    return (type(observed) is Observation and type(observed.repository) is str
            and observed.repository == repo and positive(observed.room) and observed.room == room
            and positive(observed.comment_id) and observed.comment_id == cid
            and positive(observed.actor_id) and observed.actor_id == actor
            and type(observed.body) is str and digest(observed.body) == sha)


def attempt(scope, candidate, permit, transport):
    """Rehearse a single compare/attempt/reconcile sequence with a test transport.

    `read_exact(repo, room, cid)` returns Observation, or None only for confirmed
    absence at that exact target; uncertain reads must raise. `delete_exact`
    is invoked at most once. This unit supplies no real transport. External
    permit matching is not a determination of actual projectholder authority.
    """
    repo, room, cid, actor, sha = _validate(scope, candidate, permit)
    try:
        before = transport.read_exact(repo, room, cid)
        if before is None:
            return Result('ALREADY_ABSENT', 0)
        if not _matches_observation(before, repo, room, cid, actor, sha):
            return Result('STALE', 0)
    except Exception:
        return Result('UNCERTAIN', 0)
    # This is not an atomic compare-and-delete. Reconcile even when the
    # injected mutation raises: the operation might have taken effect.
    try:
        transport.delete_exact(repo, room, cid)
    except Exception:
        pass
    try:
        after = transport.read_exact(repo, room, cid)
        if after is None:
            return Result('CONFIRMED_ABSENT_AFTER_ATTEMPT', 1)
    except Exception:
        pass
    return Result('UNCERTAIN', 1)
