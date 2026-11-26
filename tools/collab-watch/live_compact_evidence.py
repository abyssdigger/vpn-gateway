"""Pilot-only read-only captured-current equivalence evidence."""
import hashlib
import os
from pathlib import Path

BASELINE = "5ea03ac9e0a2114f224ee810a743373ae2669534"
BLOBS = {
    "core.py": "3cb8bccdedd446d3443b56a93ad4671ef4b64b9c",
    "journal.py": "09ba915315ee9290d367538dc27e23e0f8516fb2",
    "collab_watch.py": "21359edf8b91f6616ee82dc993258577780ceff9",
    "preflight_m.py": "5a5d953219a6c24953ea57e683d35382b2333403",
    "compact_observation.py": "c6738b2b03ad30cf2a8f3989f7e3e50de79bdaae",
    "pilot-config-m1.json": "8988c76624884538b204741eb591e258413d32db",
}

def main():
    stage = "baseline"
    try:
        for name, expected in BLOBS.items():
            data = Path(__file__).with_name(name).read_bytes()
            blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
            if hashlib.sha1(blob, usedforsecurity=False).hexdigest() != expected:
                raise ValueError("baseline drift")
        stage = "imports"
        from collab_watch import acquire, observation_key, read_json_file
        from core import canonical, digest, read_comment, require
        from journal import project_m, project_m_compact, JOURNAL_MARKER
        from compact_observation import compact_observation, encode_compact, decode_compact
        from preflight_m import preflight_journal_fact, preflight_journal_fact_compact
        stage = "config"
        cfg = read_json_file(Path(__file__).with_name("pilot-config-m1.json"))
        stage = "stable raw acquisition"
        raw = acquire(cfg, token=os.environ["COLLAB_GITHUB_TOKEN"])
        stage = "exact payload binding"
        rows = {read_comment(x) for x in raw["34"] if x["id"] == 7197283850}
        require(len(rows) == 1, "payload absent or conflicting")
        _, actor, body = next(iter(rows))
        require(actor == 340153730 and digest(body) ==
                "1c71ad57e4717e190d34897877f1dbe0f5d910aefffae7ee2cdd38e08d3a7b98", "payload drift")
        event = {"event_id":"m-f1-a013-result-r1","from":"BUILDER",
                 "incarnation":"builder-gpt62-current","journal_epoch":"collab-m1-20261126",
                 "kind":"INPUT","obligation":{"id":"M-F1-A013","revision":1},
                 "outcome":"ANSWER","payload_ref":"issue:34#issuecomment-7197283850",
                 "protocol":"vpng-collab/1","room":34,"to":["GUARD"]}
        candidate = JOURNAL_MARKER + "\n```json\n" + canonical(event) + "\n```"
        require(len(candidate.encode("utf-8")) == 349 and digest(candidate) ==
                "b841e94e50853a8ee6003bc1734a9a2cf879f2ce6db0bf9d634ac6f526ecc447", "candidate drift")
        stage = "raw projection"
        p_raw, s_raw = project_m(cfg, raw)
        stage = "compact encode and decode"
        wire = encode_compact(cfg, compact_observation(cfg, raw))
        compact = decode_compact(cfg, wire, digest(wire))
        stage = "fresh projection equality"
        p_compact, s_compact = project_m_compact(cfg, compact)
        require((p_raw, s_raw) == (p_compact, s_compact), "projection mismatch")
        stage = "retained replay equality"
        require(project_m(cfg, raw, s_raw) ==
                project_m_compact(cfg, compact, s_compact), "retained replay mismatch")
        stage = "prospective binding equality"
        a = preflight_journal_fact(cfg, raw, actor, candidate, s_raw)
        b = preflight_journal_fact_compact(cfg, compact, actor, candidate, s_compact)
        require(a == b, "binding mismatch")
        stage = "report"
        print("baseline", BASELINE)
        manifest = observation_key(raw)
        for room in sorted(manifest):
            print("room", room, "rows", len(raw[room]), "distinct", len(manifest[room]),
                  "manifest_sha256", digest(canonical(manifest[room])))
        print("raw_bytes", len(canonical(raw).encode("utf-8")))
        print("compact_bytes", len(wire.encode("utf-8")), "compact_sha256", digest(wire))
        print("projection_sha256", digest(canonical(p_raw)))
        print("state_sha256", digest(canonical(s_raw)))
        print("binding", canonical(a))
        print("FRESH_EQUAL=PASS RETAINED_EQUAL=PASS BINDING_EQUAL=PASS fresh-current-only")
        return 0
    except Exception:
        print("FAIL stage:", stage)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
