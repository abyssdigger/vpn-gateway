#!/usr/bin/env python3
"""Read-only, one-shot COLLAB projection; no wake actuator or authority evaluator."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from core import Conflict, canonical, project, read_comment, require, strict_json, validate_config

from journal import PROTOCOL as M_PROTOCOL, project_m, validate_m_config

API = 'https://api.github.com'
PAGE_SIZE = 100
MAX_PAGES = 50
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_LOCAL_BYTES = 32 * 1024 * 1024
MAX_OBSERVED_COMMENTS = 10000
TIMEOUT = 15


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a credential to a redirected URL.
        return None


def validate_selected_config(cfg):
    require(isinstance(cfg, dict), 'configuration must be an object')
    if 'protocol' in cfg:
        require(cfg['protocol'] == M_PROTOCOL, 'unknown configuration protocol')
        validate_m_config(cfg)
        return True
    validate_config(cfg)
    return False


def configured_rooms(cfg):
    is_m = validate_selected_config(cfg)
    return [cfg['signal_room' if is_m else 'event_room'], *cfg['task_rooms'], cfg['projectholder']['room']]


def read_json_file(path, limit=MAX_LOCAL_BYTES):
    with open(path, 'rb') as source:
        data = source.read(limit + 1)
    require(len(data) <= limit, 'local JSON file exceeds bound')
    return strict_json(data.decode('utf-8'))


def fetch_page(repo, room, page, opener, token):
    url = f'{API}/repos/{repo}/issues/{room}/comments?per_page={PAGE_SIZE}&page={page}'
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'vpng-collab-watch/0',
    }
    if token is not None:
        require(isinstance(token, str) and 0 < len(token) <= 4096
                and re.fullmatch(r'[A-Za-z0-9._~+/-]+=*', token),
                'invalid bearer credential format')
        headers['Authorization'] = 'Bearer ' + token
    try:
        request = Request(url, headers=headers, method='GET')
        with opener.open(request, timeout=TIMEOUT) as response:
            require(response.status == 200 and response.geturl() == url,
                    'unexpected HTTP response or redirect')
            data = response.read(MAX_PAGE_BYTES + 1)
            require(len(data) <= MAX_PAGE_BYTES, 'GitHub page exceeds byte bound')
            # A prematurely closed response with a declared length is incomplete.
            length = response.headers.get('Content-Length')
            if length is not None:
                require(length.isdecimal() and int(length) == len(data),
                        'GitHub page content length mismatch')
            rows = strict_json(data.decode('utf-8'))
            require(isinstance(rows, list) and len(rows) <= PAGE_SIZE,
                    'GitHub response is not a bounded comment list')
            # HTTP permits multiple Link fields; consume all of them.
            headers = response.headers
            links = headers.get_all('Link', []) if hasattr(headers, 'get_all') else (
                [headers['Link']] if 'Link' in headers else [])
            if links:
                link = ','.join(links)
                # Link is a continuation hint only; never request its URL.
                require(len(link) <= 16384, 'GitHub pagination link exceeds bound')
                require(link.isascii() and not re.search(r'[\x00-\x08\x0a-\x1f\x7f]', link), 'invalid GitHub pagination link')
                relations = []
                for field in link.split(','):
                    match = re.fullmatch(r'\s*<[^<>,\s\x00-\x1f\x7f]+>\s*;\s*rel="(next|last|prev|first)"\s*', field)
                    require(match is not None, 'invalid GitHub pagination link')
                    relations.append(match[1])
                require(len(set(relations)) == len(relations), 'duplicate GitHub pagination relation')
                has_next = 'next' in relations
            else:
                has_next = False
            return rows, has_next
    except HTTPError as exc:
        raise Conflict(f'GitHub read failed: HTTP {exc.code} (room {room}, page {page})') from None
    except Conflict:
        raise
    except (URLError, TimeoutError, OSError, UnicodeError, HTTPException, ValueError) as exc:
        # Do not include arbitrary URL/header/body/token values in diagnostics.
        raise Conflict(f'GitHub acquisition failed: {type(exc).__name__} (room {room}, page {page})') from None


def fetch_room(repo, room, opener, token, page_limit=MAX_PAGES):
    rows, seen = [], set()
    byte_count = 0
    for page in range(1, page_limit + 1):
        items, has_next = fetch_page(repo, room, page, opener, token)
        # Include overlapping pages: core validates identical/conflicting bodies.
        ids = set()
        compact = []
        for item in items:
            cid, actor, body = read_comment(item)
            ids.add(cid)
            compact.append({'id': cid, 'user': {'id': actor}, 'body': body})
            byte_count += len(body.encode('utf-8')) + 128
            require(byte_count <= MAX_LOCAL_BYTES and len(rows) + len(compact) <= MAX_OBSERVED_COMMENTS,
                    'GitHub room exceeds observation bound')
        if items and not ids - seen and (has_next or len(items) == PAGE_SIZE):
            raise Conflict(f'pagination made no progress (room {room}, page {page})')
        require(items or not has_next, 'empty GitHub page claims continuation')
        rows.extend(compact)
        seen |= ids
        # Fetch an extra page if a full page has no Link: completeness is explicit.
        if not has_next and len(items) < PAGE_SIZE:
            return rows
    raise Conflict(f'GitHub pagination bound reached (room {room})')


def observation_key(snapshots):
    # Ignore irrelevant API metadata and page order; preserve every distinct
    # observed (room,id,actor,body) tuple, including contradictory duplicates.
    return {room: sorted({canonical(read_comment(x)) for x in rows})
            for room, rows in snapshots.items()}


def acquire(cfg, token=None, opener=None):
    """Two bounded complete reads; matching observations, not atomic snapshot proof."""
    validate_selected_config(cfg)
    if opener is None:
        opener = build_opener(NoRedirect())
    def scan():
        rooms, byte_count, row_count = {}, 0, 0
        for room in configured_rooms(cfg):
            rows = fetch_room(cfg['repository'], room, opener, token)
            byte_count += sum(len(row['body'].encode('utf-8')) + 128 for row in rows)
            row_count += len(rows)
            require(byte_count <= MAX_LOCAL_BYTES and row_count <= MAX_OBSERVED_COMMENTS,
                    'selected rooms exceed total observation bound')
            rooms[str(room)] = rows
        return rooms
    first = scan()
    second = scan()
    require(observation_key(first) == observation_key(second),
            'selected-room observation changed during acquisition; retry fresh')
    return second


@contextmanager
def state_lock(path):
    lock_path = path.with_name(path.name + '.lock')
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Conflict('local state is locked by another reader') from None
        yield
    finally:
        os.close(fd)


def persist(path, value):
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(canonical(value) + '\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def observe_once(cfg, state_path, *, fixture=None, token=None, opener=None):
    is_m = validate_selected_config(cfg)
    state_path = Path(state_path)
    with state_lock(state_path):
        previous = read_json_file(state_path) if state_path.exists() else None
        snapshots = read_json_file(fixture) if fixture is not None else acquire(cfg, token, opener)
        projection, new_state = (project_m if is_m else project)(cfg, snapshots, previous)
        # No state advancement until acquisition and replay both succeed.
        persist(state_path, new_state)
        return projection


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--fixture', type=Path, help='declared-complete offline snapshots, not a live acquisition')
    parser.add_argument('--once', action='store_true', help='one-shot mode (default)')
    args = parser.parse_args(argv)
    try:
        cfg = read_json_file(args.config)
        require(args.config.resolve() != args.state.resolve() and
                (args.fixture is None or args.fixture.resolve() != args.state.resolve()),
                'configuration/fixture and state paths must differ')
        projection = observe_once(cfg, args.state, fixture=args.fixture,
                                  token=os.environ.get('COLLAB_GITHUB_TOKEN'))
    except (Conflict, OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'state': 'CONFLICT', 'diagnostic': str(exc),
                          'authority': 'not evaluated; no readiness recommendation'}, ensure_ascii=True))
        return 2
    print(json.dumps(projection, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
