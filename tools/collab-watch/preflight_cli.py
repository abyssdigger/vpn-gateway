#!/usr/bin/env python3
"""Read-only M preflight composition; never publish, activate, or evaluate authority."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from collab_watch import acquire, observation_key, read_json_file, validate_selected_config
from core import Conflict, canonical, digest, positive, require
from preflight_m import preflight_journal_fact, preflight_signal

MAX_CANDIDATE_BYTES = 65536


def preflight_once(cfg, actor, body, kind, *, previous=None, fixture=None,
                   token=None, opener=None):
    """Compose the existing acquisition and canonical projector; no persistence."""
    require(validate_selected_config(cfg), 'M configuration required')
    require(positive(actor), 'invalid actor')
    require(kind in ('journal', 'signal'), 'invalid outgoing kind')
    require(isinstance(body, str) and len(body.encode('utf-8')) <= MAX_CANDIDATE_BYTES,
            'candidate exceeds byte bound')
    snapshots = acquire(cfg, token, opener) if fixture is None else fixture
    binding = (preflight_journal_fact if kind == 'journal' else preflight_signal)(
        cfg, snapshots, actor, body, previous)
    key = observation_key(snapshots)
    return {
        'state': 'PASS', 'protocol': cfg['protocol'], 'candidate_kind': kind,
        'actor': actor, 'acquisition': 'stable-double-scan' if fixture is None else 'declared-fixture',
        'history': 'retained-ledger' if previous is not None else 'fresh-current-only',
        'config_sha256': digest(canonical(cfg)),
        'rooms': {room: {'distinct_rows': len(rows), 'sha256': digest(canonical(rows))}
                  for room, rows in key.items()},
        'full_observation_sha256': digest(canonical(key)), 'binding': binding,
        'authority': 'not evaluated; no mutation or activation authorized',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--actor', required=True, type=int)
    parser.add_argument('--kind', required=True, choices=('journal', 'signal'))
    parser.add_argument('--candidate', required=True, type=Path)
    history = parser.add_mutually_exclusive_group(required=True)
    history.add_argument('--state', type=Path, help='existing retained ledger; never modified')
    history.add_argument('--fresh', action='store_true', help='explicitly no historical integrity claim')
    parser.add_argument('--fixture', type=Path, help='declared-complete offline fixture; never live evidence')
    args = parser.parse_args(argv)
    try:
        cfg = read_json_file(args.config)
        previous = read_json_file(args.state) if args.state is not None else None
        require(args.state is None or isinstance(previous, dict), 'retained ledger must be an object')
        with args.candidate.open('rb') as source:
            raw = source.read(MAX_CANDIDATE_BYTES + 1)
        require(len(raw) <= MAX_CANDIDATE_BYTES, 'candidate exceeds byte bound')
        body = raw.decode('utf-8')
        fixture = read_json_file(args.fixture) if args.fixture is not None else None
        require(args.fixture is None or isinstance(fixture, dict), 'fixture must be an object')
        result = preflight_once(cfg, args.actor, body, args.kind, previous=previous,
                                fixture=fixture, token=os.environ.get('COLLAB_GITHUB_TOKEN'))
    except (Conflict, OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        # Do not expose arbitrary input body, path, token, or exception text to a transport client.
        print(canonical({'state': 'CONFLICT', 'error_type': type(exc).__name__,
                         'authority': 'not evaluated; no mutation or activation authorized'}))
        return 2
    print(canonical(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
