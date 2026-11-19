# NG3 2026-11-19 — probe materialization gate consistency review

## Verdict

**PASS — stale architecture claim corrected.**

## Finding

Current NG3 architecture already contains the accepted 2026-11-18 Release-1 decision that
EXP-026 probe-class conntrack cleanup is **not** required before ordinary ICMP probe
materialization. Section 8.1 explicitly states that the former implementation deferral no
longer blocks Release-1 probe work.

A later Executor paragraph still said that probe-owned local/system materialization
"remains behind" the same deferral artifact. That sentence was a stale pre-supersession
statement and contradicted the active architecture.

## Correction

The Executor paragraph now states the current boundary:

- local probe policy is not protected by `ip_forward=0` and therefore must enter the explicit
  owned local-policy exactness boundary when implemented;
- the historical deferral remains as an evidence/decision record only;
- EXP-026 cleanup is not a Release-1 prerequisite;
- section 8.1 remains the active Linux probe evidence contract.

No requirement, constraint, component responsibility or product behavior changed.

## Consequence for this cycle

Autonomous implementation may proceed with the already accepted EXP-021/022/024 evidence:

```text
current availability subject/path/target
    -> dedicated probe routing resources
    -> exact current path
    -> narrow probe-process OUTPUT admission
    -> dedicated probe conntrack mark
    -> exact reverse INPUT admission
```

The implementation must still preserve the section 8.1 non-interference invariants and must
not add namespace-wide conntrack cleanup or generic ct-mark restoration into payload traffic.

## Requirement-state inventory

This correction creates no active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

All current normative R/C closure remains unchanged.
