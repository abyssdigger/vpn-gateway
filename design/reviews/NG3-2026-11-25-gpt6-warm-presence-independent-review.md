# NG3 GPT-6 warm-presence evaluation — independent review — 2026-11-25

**Review unit:** evaluation branch `gpt6-eval-warm-paths-reserve-cdc-20261125` at
`e252e29a91b83f3a858b5c46be22568619d6e16f`.

**Compared against:** source design branch
`ng3-warm-paths-reserve-cdc-20261125@8021fc07f32d3f9e4945c1c1a1ce3408baeb2d70`.

**Purpose:** independent review of the GPT-6 evaluation implementation before any adoption into
the main development line.

This document records the findings from the independent review performed before reading the
evaluator's later self-review. It intentionally does not incorporate later findings from that
self-review so the two review passes remain comparable.

## Verdict

**DO NOT ADOPT AS-IS.**

The evaluation branch is substantive and technically strong. Its CI and kernel evidence are
real, the warm/reserve model is materially implemented, and most of the implementation
frontier is coherent. However, one adoption-blocking cross-component conflict remains, plus
one important release-path race and two smaller evidence/documentation gaps.

The primary blocker is partly inherited from the architecture already present at
`8021fc07...`: the evaluator implemented that accepted A.013 decision faithfully enough to
expose its conflict with the older sticky-path contract.

## Verification performed

The evaluation branch remained isolated:

- `main` remained outside the evaluation line;
- `ng3-warm-paths-reserve-cdc-20261125` remained at `8021fc07...`;
- `gpt6-eval-warm-paths-reserve-cdc-20261125` was reviewed at `e252e29a...`.

The final GitHub Actions run `45646087827` was inspected directly.

Confirmed:

- **25/25 jobs PASS**;
- unit job: **940/940 PASS**;
- Linux managed-runtime integration contained the expected markers:
  - `A012_RUNTIME_START_BEFORE_PATH_OBSERVATION=PASS`;
  - `A012_RUNTIME_STATUS_PROJECTION=PASS`;
  - `A012_RUNTIME_RESERVE_AFTER_FAILED_ORDINARY=PASS`;
  - `A012_RUNTIME_STALE_REPLACEMENT_BLOCKS_RELEASE=PASS`;
  - `A012_RUNTIME_PEER_RELEASE_FAILURE_BLOCKS_STOP=PASS`;
  - `A012_RUNTIME_DYNAMIC_PEER_DEPENDENCY_REMOVED_BEFORE_STOP=PASS`;
  - `A012_RUNTIME_POST_RELEASE_DEMAND_STATUS=PASS`;
  - `A012_RUNTIME_MAKE_BEFORE_BREAK=PASS`;
  - `A012_RUNTIME_DEPENDENCY_RELEASE_AND_STOP=PASS`;
  - `A012_RUNTIME_PRIVATE_NETWORK_TEARDOWN=PASS`;
  - `A012_RUNTIME_RESULT=PASS`.

A fresh independent rerun through the GitHub Actions connector was attempted, but the connector
timed out and no new run attempt appeared. Therefore no fresh rerun is claimed here.

## Findings and dispositions

### F1 — warm-surplus retirement can bypass ordinary active-path stickiness

**Severity:** HIGH / adoption-blocking.  
**Decision:** accepted.  
**Resolution:** unresolved; requires architecture/product discussion before adoption.

The current A.013 surplus selection treats a numeric warm target as a reason to retain only a
minimal set of currently present managed ordinary Devices, preferring baseline order.

That interacts badly with the existing sticky ordinary path contract.

Consider:

```toml
[profile.corp]
device_order = ["a", "b"]
warm_paths = 1
```

Both memberships are ordinary.

Suppose:

```text
a = present, baseline #1
b = present, baseline #2, CURRENT ACTIVE
```

The accepted sticky behavior under `VPNG-U003-R3.R8` is that a usable non-reserve active path
remains active merely because a more-preferred ordinary path is present again.

But the current A.013 selection can produce:

```text
desired managed Devices = {a}
```

and remove `b` from managed demand.

The critical chain is then:

```text
A.013
    -> desired = {a}

A.012 convergence
    -> confirmed managed interfaces = {a}

AlphaPreparedPolicy.eligible_interfaces()
    -> b is filtered out from current managed endpoints

C.004 / payload-profile projection
    -> b disappears from current structural path membership

A.006 sticky routing
    -> previous active b is no longer in current membership
    -> active state is reset
    -> a becomes active
```

Thus A.006 itself can remain correct while lifecycle retirement bypasses it entirely.

This conflicts with:

- `VPNG-U003-R3`;
- `VPNG-U003-R3.R4`;
- especially `VPNG-U003-R3.R8`;
- the agreed principle that numeric `warm_paths` is a cardinality target, not proactive
  ordinary identity rebalance.

#### Root cause

The architecture already present at `8021fc07...` contained the problematic A.013 decision:

> when surplus managed ordinary memberships are present, keep the minimal deterministic set,
> preferring baseline order.

The evaluation implementation largely materializes that decision. Therefore this is not merely
an implementation mistake by the evaluator; materialization exposed a conflict in the accepted
cross-component design.

#### Recommended direction

A.013 should determine the amount of managed capacity required to satisfy warm presence, but
must not independently gain authority to retire the currently usable non-reserve active path
in a way that bypasses A.004/A.006 sticky semantics.

The unresolved architectural question is where retirement eligibility belongs and how it is
represented without making availability outcome an input to warm demand.

Do not solve this by silently changing sort order inside A.013.

---

### F2 — post-D.003 generation race can leave a retained reserve without payload ownership

**Severity:** MEDIUM.  
**Decision:** accepted.  
**Resolution:** unresolved; corrective release-path design required before adoption.

The evaluation correctly adds a second exact replacement-generation check around reserve
release.

The intended sequence is:

```text
verify replacement generation
    -> remove retiring reserve dynamic D.003 AllowedIPs
    -> verify replacement generation again
    -> only then allow D.001 stop
```

The second guard is useful. It prevents physical removal of reserve when the replacement
changed between policy convergence and actual stop.

However, consider this interleaving:

```text
first replacement check = OK

D.003 cleanup:
    dynamic payload AllowedIPs removed from reserve

replacement changes or disappears

second replacement check = FAIL
```

The implementation correctly cancels D.001 stop, but the D.003 mutation has already happened.

The function then returns with the reserve still physically present while the payload ownership
that made it useful may already have been removed.

Because the caller performs the post-release payload reconciliation only when
`released == True`, this aborted release path does not immediately restore the removed
dependency.

The result is fail-closed rather than unsafe, so this is not a security violation. But it
undermines the purpose of retaining reserve precisely when the replacement ceased to be
trustworthy.

#### Required corrective shape

One of these equivalent safety shapes is needed:

```text
post-D.003 guard fails
    -> immediately restore/reconverge the retained reserve dependencies
```

or:

```text
post-D.003 guard fails
    -> immediately enter a full fresh normal reconciliation
```

Waiting for the next periodic audit is weaker than the intended make-before-break release
contract.

Existing `STALE_REPLACEMENT_BLOCKS_RELEASE` evidence does not cover this race because its stale
generation is introduced before the first check, so D.003 is never mutated in that case.

---

### F3 — A.004 materialization text is stale on the final evaluation head

**Severity:** LOW.  
**Decision:** accepted.  
**Resolution:** straightforward documentation correction.

The final `architecture-ng.md` still says, in A.004 materialization, that the new
configuration-driven Device-presence projection is not yet materialized as a separate
boundary.

On the same final head:

- A.013 exists;
- A.012 consumes it;
- two-phase warm/reserve composition exists;
- EV-00300 documents the materialization.

A.012/A.013 and the evaluator review describe the new implementation correctly, so A.004 is
simply stale intermediate wording.

This should be corrected before adoption.

---

### F4 — cold-start reserve fallback is not directly proven by current kernel evidence

**Severity:** LOW / evidence gap.  
**Decision:** accepted.  
**Resolution:** add targeted evidence before adoption if this branch is used as implementation
candidate.

EV-00300 proves the important runtime sequence:

```text
ordinary present
    -> ordinary fails
    -> reserve activates
    -> ordinary recovers
    -> reserve is safely released
```

But the kernel scenario begins with a successfully running ordinary Device and breaks it only
after startup is READY.

It does not directly prove:

```text
process cold start
    -> preferred ordinary managed Device cannot become present
    -> bounded ordinary attempt fails
    -> reserve is brought up in the same startup lifecycle
    -> product reaches usable/ready state through reserve
```

Static inspection suggests startup calls the same managed-presence convergence path, so no
specific bug was established here. This remains an evidence gap, not a defect finding.

A small targeted kernel case would remove the ambiguity.

---

### F5 — CDC clock ordering process deviation

**Severity:** process-only.  
**Decision:** accepted.  
**Resolution:** already acknowledged by the evaluator.

The first UTC reading was taken after initial methodology reading rather than before it.

The evaluator reported this accurately. It does not invalidate the technical result, but the
next CDC should obtain the authoritative clock before preparatory reads, as required by the
methodology.

## What the evaluation implementation did well

The branch should not be discarded.

The following parts are materially useful and appear coherent:

- `warm_paths` is introduced as a current-only extension without changing frozen Release-1
  grammar;
- reserve is excluded from ordinary warm capacity and does not reduce regular deficit;
- current external ordinary paths satisfy warm presence without becoming actuation subjects;
- shared Device demand is aggregated across Profiles;
- failed ordinary candidate actuation does not poison the entire reconciliation trigger;
- exact managed-interface identity/generation is checked rather than trusting same-name
  interfaces;
- D.003 ownership cleanup must be confirmed before D.001 stop;
- stale replacement generation blocks physical reserve removal;
- post-release status is recomputed from fresh confirmed state rather than blindly retaining
  the pre-release projection.

The evaluator's independent decisions around exact interface generation, D.003 ownership and
bounded candidate attempts are largely derivable from existing contracts and do not appear to
invent a new hidden product policy.

## Evaluation of the evaluator's own review

The evaluator's own final review stated that no material unresolved finding remained.

This independent review does not accept that conclusion because F1 and F2 remain unresolved.

The CI and evidence claims themselves were found to be honest and supported; no fake or
misrepresented PASS was identified.

## Adoption recommendation

Keep `gpt6-eval-warm-paths-reserve-cdc-20261125` as an implementation candidate.

Do **not** snapshot or merge it as-is.

Before adoption:

1. resolve F1 at the architecture boundary:
   - who is allowed to decide that an already-present ordinary managed Device is surplus;
   - how that decision respects current non-reserve active-path stickiness;
   - how this remains separate from availability as a source of warm demand;
2. fix the F2 D.003 rollback/reconciliation race;
3. correct stale A.004 materialization;
4. add cold-start reserve fallback evidence.

The first discussion should focus on F1. The current A.013 answer — baseline-preferred survivor
selection — is not sufficient because lifecycle retirement can otherwise override the accepted
sticky ordinary path contract.

## Review boundary

No adoption or implementation changes were made as part of this review.

The intended evaluation branch, source design branch and `main` remained unchanged during the
review. A separate review branch was used only as an isolation target for review artifacts.
