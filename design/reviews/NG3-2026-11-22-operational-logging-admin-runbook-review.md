# NG3 2026-11-22 — operational logging and administrator runbook review

**Scope:** operational logging `VPNG-M001-R2.R3*`, normalized component log identity,
current alpha implementation/evidence, and applicability of `design/NG3/admin-runbook.md`.

## Verdict

**PASS — ACCEPT ARCHITECTURE CLOSURE AND ALPHA IMPLEMENTATION.**

## Architecture

`A.010 OperationalLogAdapter` is a Direct Adapter from semantic operational records to the
deployment logging facility.

The boundary is intentionally separate from:

- `A.008/A.009` current-state status surfaces;
- component internal execution tracing;
- VPN implementation logs.

Current state therefore remains readable without reconstructing it from history, while the
operational log supplies temporal event/reaction context.

## Findings and dispositions

### F1 — previous observability parent wording excluded its new history child

**Decision:** accepted.  
**Resolution:** fixed.

`VPNG-M001-R2` now explicitly separates current state/problem surfaces from temporal
operational history while retaining the guarantee that current truth does not require log or
kernel-state reconstruction.

### F2 — naive DEBUG emission on every RECONCILED return produced audit-period noise

**Decision:** accepted.  
**Resolution:** fixed.

The alpha reconcile result can remain `RECONCILED` across equivalent audits. POLICY
records are therefore emitted only when result/diagnostic semantics change; BIND, AVAIL and
PROF records are driven by their own semantic transitions. EXP-051 proves stable audit does
not add operational records.

### F3 — textual levels alone would not make journal severity filtering operationally useful

**Decision:** accepted.  
**Resolution:** fixed.

A.010 maps DEBUG/INFO/WARNING/ERROR to syslog priorities in the current systemd stream.
EXP-051 proves `journalctl -p info` excludes DEBUG while retaining INFO.

### F4 — A.010 initially duplicated architecture ownership of existing implementation files

**Decision:** accepted.  
**Resolution:** fixed.

Implementation traceability remains one production file -> one architecture owner.
`operational_log.py` is owned by A.010; existing component modules and A.001 composition
keep their existing owners while using A.010 as an interaction boundary.

### F5 — same-name endpoint recreation must remain visible in discovery history

**Decision:** accepted.  
**Resolution:** fixed.

BIND records render current endpoint identity as `ifname@ifindex`, so VPN-only restart
records the concrete generation change even when the Linux interface name is reused.

### F6 — runbook had two applicability defects

**Decision:** accepted.  
**Resolution:** fixed and rechecked.

The guide now lists `procps` because it uses `watch`; the canonical config-model logging
section/example was repaired. The installed EXP-051 path proves the material runbook sequence.

### F7 — developer execution trace must not leak into operational DEBUG scope

**Decision:** accepted.  
**Resolution:** explicitly deferred.

`VPNG-D001-R2` records the accepted need but intentionally leaves coverage, branch tracing,
parameter/result representation, destination, performance and secret-handling contract
undecided. `design/deferrals/NG3-developer-execution-trace.md` is the re-entry gate.

## Data-safety review

The current OperationalLogAdapter accepts only pre-normalized scalar context and rejects
arbitrary complex objects instead of implicitly dumping them. A.010 makes callers responsible
for passing only context already safe for operational disclosure. Reviewed alpha callsites
emit product IDs, logical path identity, interface generation, lifecycle/status values,
network diagnostics and normalized non-secret configuration metadata; VPN credentials/key
material are owned by the external VPN configuration and are not passed to this logging path.

## Evidence

Source/evidence commit: `d3787abfce7bfa9059ba919a9a032d9c09017e4d`.

GitHub Actions run `44989015020`:

- unit: **PASS**, 800 tests;
- installed Debian 13/systemd alpha smoke: **PASS**;
- EXP-051 operational logging markers: **PASS**;
- EXP-051 administrator runbook applicability marker: **PASS**.

Persistent result:
`design/experiments/EXP-051 NG3 first functioning alpha/EXP-051-result-20261122-operational-logging-runbook-pass.md`.

## Closure decision

All twelve `VPNG-M001-R2.R3*` nodes may move from `pending_closure` to `closed`.

`VPNG-D001-R2` remains intentionally decomposition-incomplete and without architecture
closure pending the separate project-holder trace decision.
