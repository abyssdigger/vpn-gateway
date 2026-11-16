# VPN-GATE NG3 — First-release inbound constraint CD checkpoint

**Cycle:** `ng3-design-cycle-20261116-first-release-inbound-constraint-40m`  
**Date:** 2026-11-16

# 1. Product decision

Release 1 explicitly constrains inbound/bidirectional Profiles:

```text
outbound
    -> multi-path allowed

inbound | bidirectional
    -> configured maximum eligible logical-path capacity <= 1
```

The limit is represented by `VPNG-R2.R3.C1`.

# 2. Fail-fast behavior

`VPNG-R2.R3.C1.R1` requires config normalization to reject unsupported topology before
dependent network actuation.

Capacity is computed from currently enabled referenced Devices and their expected-interface
selector quotas.

This is configuration capacity, not current runtime interface count.

Consequences:

- exact selector contributes 1;
- prefix selector contributes explicit positive quota;
- several selectors of one Device sum;
- several enabled referenced Devices sum;
- disabled referenced Device contributes zero until a configuration change enables it;
- runtime discovery cannot turn an already accepted Release 1 Profile into unsupported
  multi-path inbound topology.

# 3. Architecture result

No Release 1 return-path pinning mechanism is introduced.

Existing architecture remains:

- Profile defines payload need and Device order;
- Device binding derives logical paths;
- availability modifies priority only;
- outbound multi-path remains supported;
- inbound/bidirectional is supported only within the accepted capacity constraint.

ConfigurationAdapter performs fail-fast validation.

# 4. Future Release 2 evidence

Created:

`design/NG3/release2-evidence-backlog.md`

Tracks separately:

```text
EXP-014
    -> remote-initiated multi-path payload return-path semantics
    -> primary Release 2 multi-path inbound/bidirectional evidence gate

EXP-026
    -> probe-class conntrack generation cleanup
    -> supporting probe-runtime hardening evidence
```

A PASS of either experiment does not substitute for the other.

Experiment ledger entries now link to the Release 2 backlog.

# 5. Reminder state

Scheduled for 2026-11-16 08:05 UTC:

- EXP-014 return-path experiment/evidence follow-up;
- EXP-026 Debian 13 confirmation.

Both reminders request recording results in the future evidence backlog.

# 6. CD review

Review:

`design/reviews/NG3-2026-11-16-first-release-inbound-capacity-review.md`

Result:

**PASS — no current blocker.**

# 7. Requirement state

```text
R/C nodes:          121
closed:             121
pending_closure:      0
rejected_closure:     0
open:                 0
```

Integrity:

```text
closed without exact architecture ref: 0
extra architecture refs:                0
active decomposition blocks:            0
broken decomposition links:             0
stale inbound-gate statements:           0
```

# Verdict

**PASS — COMPLETE CURRENT RELEASE 1 REQUIREMENT/ARCHITECTURE CLOSURE RESTORED.**

Release 2 multi-path inbound/bidirectional remains explicit future work rather than an
unresolved Release 1 promise.