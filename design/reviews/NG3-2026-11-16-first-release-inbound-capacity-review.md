# VPN-GATE NG3 — First-release inbound path-capacity CD review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-first-release-inbound-constraint-40m`

# 1. Decision reviewed

Release 1 deliberately excludes multi-path remote-initiated payload semantics.

Accepted rule:

```text
direction = outbound
    -> multi-path allowed

direction = inbound | bidirectional
    -> configured maximum eligible logical-path capacity <= 1
```

The limitation is represented as `VPNG-R2.R3.C1`, not hidden in implementation.

# 2. Why this is a Constraint

The product need still includes explicit inbound/bidirectional direction policy.

The restriction exists because safe return-path semantics for a remote-initiated flow across
multiple simultaneously eligible paths are not yet target-proven.

Historical EXP-014 was prepared for that exact class of behavior and was not completed.

Therefore the Release 1 limitation narrows supported topology without redefining the meaning
of `inbound` or `bidirectional`.

**Verdict:** correct Requirement/Constraint placement.

# 3. Fail-fast validation

`VPNG-R2.R3.C1.R1` derives the compensating product behavior:

> reject unsupported topology before dependent network actuation.

Validation is based on configuration capacity, not runtime coincidence.

For one enabled inbound/bidirectional Profile:

```text
max eligible path capacity
    = sum(
        quota of every expected-interface selector
        of every currently enabled referenced Device
      )
```

Exact selector contributes 1. Prefix selector contributes its explicit positive quota.

Consequences:

- a Profile with configured capacity 2 is rejected even if only one endpoint exists now;
- an enabled referenced Device with two exact selectors already gives capacity 2;
- one prefix selector with quota 2 gives capacity 2;
- a disabled referenced Device contributes zero current capacity;
- enabling that Device is a config change and must pass validation again;
- outbound-only Profiles are unaffected.

This prevents ordinary runtime discovery from turning an accepted Release 1 configuration
into an unsupported multi-path inbound topology.

**Verdict:** PASS.

# 4. Architecture review

The ConfigurationAdapter performs the validation before network actuation.

No return-path pinning mechanism is introduced in Release 1.

No runtime state machine guesses what to do when multiple inbound paths appear, because such
a configuration is rejected before it becomes accepted intent.

The existing Profile, Device binding and availability architecture remains unchanged:

- Profile still names ordered Devices;
- binding still derives logical paths from Device selector slots;
- availability still changes priority only;
- outbound multi-path failover/failback remains supported;
- inbound/bidirectional capacity<=1 remains valid through endpoint disappearance/replacement.

**Verdict:** PASS.

# 5. Evidence boundary

Release 1 no longer depends on EXP-014.

EXP-014 is moved to the Release 2 evidence backlog as the primary future experiment for
multi-path inbound/bidirectional return-path behavior.

EXP-026 remains a separate probe-generation evidence track. Its future Debian 13 result is
stored in the same backlog for convenience but does not prove payload return-path pinning.

Canonical backlog:

`design/NG3/release2-evidence-backlog.md`

**Verdict:** PASS.

# 6. Transition-tip consistency

The accepted rule resolves the previous transition tip that prohibited silently assuming
multi-path inbound return correctness.

Current guidance now explicitly says:

- reject capacity>1 inbound/bidirectional in Release 1;
- do not weaken validation to current observed path count;
- do not remove the constraint for Release 2 merely because an experiment passes;
- revise requirements explicitly before promoting the capability.

**Verdict:** PASS.

# 7. Blocker search

Checked for:

- unresolved Purpose/Reason;
- configuration/runtime mismatch;
- hidden fallback to currently-one-path behavior;
- architecture references missing for the new nodes;
- conflict with outbound multi-path requirements;
- dependency on EXP-014 for Release 1;
- dependency on EXP-026 for this product semantic.

No blocker found.

# 8. Closure decision

Accept closure for:

- `VPNG-R2`;
- `VPNG-R2.R3`;
- `VPNG-R2.R3.R3`;
- `VPNG-R2.R3.C1`;
- `VPNG-R2.R3.C1.R1`.

Release 2 multi-path inbound/bidirectional remains outside the current Release 1 promise and
is tracked as future requirement/evidence work rather than an open Release 1 requirement.

# Verdict

**PASS — FIRST-RELEASE INBOUND/BIDIRECTIONAL PATH-CAPACITY CONSTRAINT IS COMPLETE.**