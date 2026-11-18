# VPN-GATE — Release 2 evidence backlog

**Status:** future-release evidence register  
**Created from:** NG3 Release 1 constraint review  
**Primary candidate feature:** multi-path inbound/bidirectional Profiles

This document collects evidence that is intentionally **not required to ship Release 1** after
the first-release inbound path-capacity constraint was accepted.

It exists so that Release 2 work can start from preserved experimental questions/results
instead of reopening historical archaeology.

# 1. Release 2 feature target

Candidate capability:

```text
Profile:
    direction = inbound | bidirectional
    maximum eligible logical-path capacity > 1
```

Release 1 rejects this configuration before network actuation.

Release 2 may remove that constraint only after:

1. product semantics for remote-initiated flow return-path behavior are explicit;
2. architecture implements those semantics without widening Profile permission;
3. target evidence proves the required Linux behavior;
4. failure/recovery behavior remains fail-closed;
5. requirements are explicitly revised and re-reviewed.

# 2. EXP-014 — remote-initiated multi-path flow pinning

**Role for Release 2:** primary evidence gate for multi-path inbound/bidirectional.

Historical status:

```text
PREPARED / UNPROVEN
```

Original question:

> Can a remotely initiated flow that arrives through one of several eligible Profile paths
> have its return traffic deterministically and safely kept compatible with that ingress path?

Historical intended mechanism class:

```text
ingress path
    -> flow/connection identity
    -> mark/policy state
    -> return-path steering
```

Potential evidence obligations include:

- two or more simultaneously eligible inbound paths;
- NEW flow accepted through a non-primary path;
- reply is forced through the required compatible path;
- established flow remains stable while unrelated effective priority changes;
- disappearance of the pinned path fails closed according to accepted product semantics;
- stale mark/state retirement does not redirect flow through a forbidden path;
- Profile/device restrictions remain enforced;
- no ambient/main-table escape;
- ordinary outbound multi-path policy remains unaffected.

The exact mechanism is **not predetermined**. connmark/fwmark is historical hypothesis, not
an accepted Release 2 architecture.

## Result slot

When EXP-014 or an equivalent experiment is run, record here:

```text
environment:
commit:
result:
mechanism tested:
positive findings:
negative findings:
scope limitations:
requirement consequences:
architecture consequences:
```

# 3. EXP-026 — probe-class conntrack cleanup

**Role for Release 2:** optional supporting runtime/probe-generation hardening evidence; not a
substitute for payload flow-affinity evidence and not a Release-1 dependency.

Current status:

```text
privileged CI: PASS
Debian 13 target confirmation: OPEN
```

Known CI finding:

- mark-filtered probe-class conntrack cleanup removes dedicated probe entries;
- differently marked control state is retained;
- subsequent fixed-id probe returns to NEW + mark-set behavior.

Why keep this with Release 2 evidence:

A future broader multi-path runtime will rely on stronger confidence that path-generation
changes do not inherit stale lower state. EXP-026 is specifically about the probe plane, not
payload return-path pinning, but its target result informs safe generation-boundary design.

It does **not** prove:

- payload flow pinning;
- remote-initiated return-path correctness;
- general conntrack cleanup policy for payload flows.

## Optional future result slot

If a future release re-enters this mechanism and chooses to obtain Debian 13 target evidence,
record the result here. No target run is currently required.

# 4. Evidence separation rule

Do not merge these experiments semantically:

```text
EXP-014
    -> payload-flow return-path semantics

EXP-026
    -> probe-plane stale conntrack remediation
```

A PASS of EXP-026 cannot close multi-path bidirectional support.

A PASS of EXP-014 cannot by itself close probe-generation cleanup.

# 5. Release 1 non-dependency

Release 1 remains valid regardless of the future outcome of EXP-014 because unsupported
multi-path inbound/bidirectional configuration is rejected at normalization.

Release 1 does not depend on Debian 13 confirmation or production adoption of EXP-026.
The accepted probe implementation must instead prove current subject/path isolation and
non-interference with payload routing/return affinity. EXP-026 may be re-entered if later
evidence demonstrates material harm from stale probe conntrack identity.

# 6. Release 2 promotion rule

Evidence moves from this backlog into normative Release 2 requirements/architecture only
through an explicit review.

Do not silently remove the Release 1 constraint merely because an experiment passes.
A passing experiment proves a technical claim; product support still requires an accepted
Requirement/Constraint change.