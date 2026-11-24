# NG3 2026-11-24 — external requirement-basis registry review

**Scope:** application of the new external-basis methodology to the current NG3 requirement tree.

## Verdict

**PASS — current externally justified requirement statuses are now directly discoverable.**

## Findings and dispositions

### F1 — the registry exactly covers current postponed nodes

**Decision:** accepted.  
**Resolution:** fixed.

The registry contains exactly the eight current `postponed` nodes: five developer-trace nodes
and three resource-envelope nodes. Each entry points to the existing accepted deferral record,
and each target record names the corresponding requirement IDs.

### F2 — the requirement tree has one deterministic outward link

**Decision:** accepted.  
**Resolution:** fixed.

`design/NG3/requirements.md` links directly to
`design/NG3/requirement-status-basis.md`. A reader no longer needs repository-wide search to
locate the basis of a non-local status.

### F3 — traceability enforcement no longer uses repository-wide text search

**Decision:** accepted.  
**Resolution:** fixed.

`test_architecture_traceability.py` now compares current externally justified status nodes
with the canonical registry, verifies every target file exists, and verifies the target record
names the affected requirement.

The previous scan over all `design/deferrals/*.md` and `design/reviews/*.md` is removed.

### F4 — unrelated historical-release CI coupling discovered

**Decision:** accepted as a separate finding.  
**Resolution:** deferred to the immediately following development block.

The NG3 unit/traceability job passes on commit `57a7e35cd12beae60f14e731fe4c42b88c639a71`.
The old `release-0-1-0-deployment-qa` job fails because its validator compares the live current
NG3 requirement file with the frozen 0.1.0 project snapshot. This makes every legitimate
post-release requirement change fail historical release QA.

That release-regression boundary is independent of this registry and must be corrected without
rewriting the frozen 0.1.0 snapshot.
