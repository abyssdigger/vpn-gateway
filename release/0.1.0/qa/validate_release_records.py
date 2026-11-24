#!/usr/bin/env python3
"""Release-record consistency gate for VPN-GATE 0.1.0."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "release" / "0.1.0"
REQ = ROOT / "design" / "NG3" / "requirements.md"
ARCH = ROOT / "design" / "NG3" / "architecture-ng.md"
CHANGELOG = ROOT / "CHANGELOG-NG3.md"
SCOPE = RELEASE / "RELEASE-SCOPE.md"
COVERAGE = RELEASE / "REQUIREMENTS-COVERAGE.md"

NODE_RE = re.compile(
    r"\*\*\[(VPNG-[A-Z0-9.-]+)\]\*\*.*?"
    r"\[\`decomposition\`: \`(complete|incomplete)\`\] "
    r"\[\`(closed|postponed|permanent|open|pending_closure|rejected_closure)\`\]"
)
def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    version = read(ROOT / "VERSION").strip()
    assert version == "0.1.0", version

    scope = read(SCOPE)
    assert "**Status:** `approved`" in scope
    assert "VPNG-U004-R5.C1" in scope and "**not exercised**" in scope
    assert "VPNG-U001-R5.R2.C1" in scope and "**is exercised**" in scope

    pairs = (
        (REQ, RELEASE / "project-snapshot" / "requirements.md"),
        (ARCH, RELEASE / "project-snapshot" / "architecture-ng.md"),
        (CHANGELOG, RELEASE / "project-snapshot" / "CHANGELOG-NG3.md"),
    )
    for source, snapshot in pairs:
        assert source.read_bytes() == snapshot.read_bytes(), (
            f"stale project snapshot: {snapshot.relative_to(ROOT)}"
        )

    nodes = NODE_RE.findall(read(REQ))
    assert len(nodes) == 220, len(nodes)
    node_map = {node_id: (decomp, status) for node_id, decomp, status in nodes}
    assert len(node_map) == len(nodes)

    rows = []
    for line in read(COVERAGE).splitlines():
        if not line.startswith("| `VPNG-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 7, (len(cells), line)
        node_id = cells[0].strip("`")
        decomp = cells[1].strip("`")
        status = cells[2].strip("`")
        disposition = cells[4].strip("`")
        rows.append((node_id, decomp, status, disposition))

    assert len(rows) == len(nodes), (len(rows), len(nodes))
    row_ids = [row[0] for row in rows]
    duplicates = [item for item, count in Counter(row_ids).items() if count != 1]
    assert not duplicates, duplicates
    assert set(row_ids) == set(node_map), (
        sorted(set(node_map) - set(row_ids)),
        sorted(set(row_ids) - set(node_map)),
    )

    dispositions = {}
    for node_id, decomp, status, disposition in rows:
        assert node_map[node_id] == (decomp, status), node_id
        dispositions[node_id] = disposition

    aggressive = {
        node_id
        for node_id, _, status in nodes
        if status == "closed"
        and node_id.startswith("VPNG-U001-R5.R2")
        and node_id != "VPNG-U001-R5.R2.C1"
    }
    assert aggressive
    for node_id in aggressive:
        assert dispositions[node_id] == "excluded-by-approved-scope", node_id

    for node_id, _, status in nodes:
        if node_id.startswith("VPNG-U004-R5"):
            assert dispositions[node_id] == "covered", node_id
        if status == "postponed":
            assert dispositions[node_id] == "excluded-postponed", node_id
        if status == "permanent":
            assert dispositions[node_id] == "conformance-applicable", node_id

    architecture = read(ARCH)
    nonfull_edges = [
        line
        for line in architecture.splitlines()
        if re.match(
            r"^- \`VPNG-[A-Z0-9.-]+\` — \[\`(?:partial|none)\`\]$",
            line,
        )
    ]
    assert not nonfull_edges, nonfull_edges

    qa = read(RELEASE / "QA-REPORT.md")
    if "**Status:** **PENDING**" in qa:
        assert "no PASS verdict" in qa
    else:
        assert "Tested release-set head:" in qa
        assert "**PASS" in qa or "result:** **PASS**" in qa

    print("RELEASE_RECORDS_SCOPE=PASS")
    print("RELEASE_RECORDS_SNAPSHOT=PASS")
    print("RELEASE_RECORDS_COVERAGE_220=PASS")
    print("RELEASE_RECORDS_ARCHITECTURE_FULL=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
