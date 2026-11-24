# NG3 2026-11-22 — human runtime status report review

**Scope:** `VPNG-M001-R2.R2` compact human current-state presentation, path-level availability
truthfulness and installed alpha publication.

## Verdict

**PASS — ACCEPT ARCHITECTURE CLOSURE AND IMPLEMENTATION.**

The implementation adds no second status model. `RuntimeStatusAgent` remains the current
authoritative composition boundary; `RuntimeStatusTextRenderer` is a Direct Calculator over
one `RuntimeStatusSnapshot`, and alpha publishes the rendered text atomically beside the
existing JSON presentation.

## Requirements

Reviewed:

- `VPNG-M001-R2.R2`;
- `VPNG-M001-R2.R2.R1`;
- `VPNG-M001-R2.R2.R2`;
- `VPNG-M001-R2.R2.R3`;
- `VPNG-M001-R2.R2.R4`.

Architecture entry: `A.009 RuntimeStatusTextRenderer`.

## Evidence

Source behavior commit: `3f6248101e5ff287745842113ace85a9c5cc4319`.

NG3 Python run `44956806186` supplied the relevant acceptance evidence before the later
documentation-only result commit:

- unit job `137006664951`: **PASS**, 793 tests;
- installed alpha smoke `137006665030`: **PASS**;
- EXP-049 OpenVPN/systemd regression: **PASS**.

Installed alpha markers:

```text
EXP051_RUNTIME_STATUS_TEXT_ZERO_PATH=PASS
EXP051_RUNTIME_STATUS_TEXT_FIRST_PATH=PASS
EXP051_RUNTIME_STATUS_TEXT_NEW_GENERATION=PASS
EXP051_RESULT=PASS
```

Persistent evidence record:
`design/experiments/EXP-051 NG3 first functioning alpha/EXP-051-result-20261122-human-status-pass.md`.

## Findings and dispositions

### F1 — previous status model collapsed path problems to one Profile-level state

**Decision:** accepted.  
**Resolution:** fixed.

`AvailabilityProfileStatus` now retains the bounded set of current problem
`LogicalPathId` values while preserving the existing coarse state for compatibility.
The text renderer can therefore report one path available and another unavailable without
inventing a Profile health verdict.

### F2 — absence of a confirmed effective snapshot must not render as physical absence

**Decision:** accepted.  
**Resolution:** fixed.

The requirement and renderer now use `unknown` for enabled Device/Profile state when the
current effective projection is unconfirmed. `not discovered` is emitted only from a
confirmed projection that contains no current path for the enabled Device.

### F3 — status presentation must remain separate from configuration semantics

**Decision:** accepted.  
**Resolution:** fixed.

The renderer produces exactly the compact current-state view. It is not a configuration dump,
is not round-trippable configuration, and does not inspect kernel state or logs.

### F4 — stable text semantics must not accidentally freeze the alpha pathname

**Decision:** accepted.  
**Resolution:** fixed.

`Devices`/`Profiles`, indentation, effective-order numbering and availability wording are
the required presentation contract. `/run/vpn-gate-alpha/status.txt` is the current alpha
delivery mechanism, not a stable API promise.

## Traceability

`runtime_status.py` now traces to both `A.008` and `A.009`; the structured architecture
declares the renderer implementation, and the existing mechanical structured-architecture
traceability test passes in the 793-test unit job.

No new `unreal`, `broken`, `decomp` or `rejected_closure` state is introduced.

## Closure decision

The five reviewed `VPNG-M001-R2.R2*` nodes may move from `pending_closure` to `closed`.
