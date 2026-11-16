# VPN-GATE NG3 — Primary Requirements / CD Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**CYCLE_INTERVAL:** 40m  
**Cycle type:** methodology + requirement migration/review + continuous design/development  
**Checkpoint reason:** Git commit elapsed time reached the configured interval; the current
review unit is complete.

## Cycle clock

```text
CYCLE_START_COMMIT:
56bb09107cb591e9ff8d086c2642c14bc70bb22b
2026-11-16T06:26:32Z
Design: add primary-requirement basis and actor rules

last content head before checkpoint:
07e60355f94496806423b75b0e8f08871c0cc84a
2026-11-16T07:06:35Z
NG3: record shared lower-policy allocation as next boundary

elapsed to last content head:
40m 03s
```

The commit that adds this checkpoint file is the final checkpoint commit for this cycle;
its authoritative SHA/timestamp is read from GitHub after publication and reported in the
human-facing checkpoint message.

## Completed — methodology and process

- generalized `design/requirements-model.md` around:
  - primary Requirement = `Basis / Основание + Statement`;
  - derived Requirement = `Purpose + Statement`;
  - Constraint = `Reason + Statement`;
- introduced stable primary roots such as `VPNG0003` with typed derived paths;
- added an explicit actor-completeness review gate;
- synchronized `CONTINUOUS-DEVELOPMENT.md` with Basis/Purpose/Reason and actor semantics;
- made immediate GitHub publication of every commit an explicit
  `PROJECT-CONVENTIONS.md` rule;
- corrected project conventions to identify NG3, not NG2, as the current normative
  generation.

## Completed — NG3 requirement migration and rationale review

- migrated the current NG3 tree to:
  - 7 primary project requirements;
  - 128 total normative nodes;
  - 6 Constraints;
- migrated architecture and config-model trace references to the new IDs;
- completed a full Basis/Purpose/Reason/actor review of all current nodes;
- corrected three Constraint-rationale weaknesses and the identified ambiguous actor
  formulations;
- revalidated existing Release 1 architecture closure after the wording fixes;
- final mechanical integrity pass:
  - 128 unique requirement IDs;
  - 0 requirements missing from architecture;
  - 0 unknown architecture IDs;
  - 0 unknown config-model IDs;
  - 0 current legacy `VPNG-R...` IDs;
  - 0 primary roots without Basis;
  - 0 Constraints using Purpose-form `Чтобы` instead of Reason.

## Completed — CD implementation progression

The pure-priority NetworkPolicyExecutor path progressed through reviewed executable layers:

```text
clean-state route-priority planner
    ->
partial make-before-break state convergence
    ->
single-attempt observe/apply/re-observe Executor contract
    ->
strict owned route-key inventory
    ->
physical iproute2 route-key backend
    ->
Profile multi-destination coordinator
    ->
lower Adapter route-priority realization contract
```

Accepted properties include:

- make-before-break remains one semantic move boundary;
- stale plan tails are discarded after partial failure;
- each retry starts from fresh authoritative state;
- same-name interface replacement cannot silently impersonate the accepted
  `(ifname, ifindex)` binding during a route observation;
- every physical mutation verifies the whole route-key domain, not only the moved path;
- Profile-level priority success requires a final fresh verification across every affected
  destination domain;
- internal preference metric slots are strictly increasing Linux metrics;
- multi-path realization has disjoint scratch metric space;
- table/protocol/metric identifiers remain lower internal realization, not user config.

## Evidence

Latest accepted GitHub Actions evidence:

```text
workflow: NG3 Python
run:      43821152707
commit:   7fd57fef61804f0ada5f6aa6a4950a1f36445b36
unit:     153 tests, OK
linux-route-priority: PASS
overall:  success
```

The privileged Linux job uses a disposable network namespace and real iproute2 operations.
It exercises:

- physical route-priority swap;
- partial duplicate-state recovery;
- Profile multi-domain convergence and final physical verification.

## Reviews / fixes completed

Cycle reviews include:

- full requirement Basis/Purpose/Reason review;
- partial-state convergence review;
- single-attempt Executor review;
- physical route-domain design review;
- owned route inventory review;
- physical iproute2 backend review;
- Profile multi-domain coordinator review;
- semantic-to-physical boundary review;
- lower realization contract review;
- cycle integrity review;
- allocation-source review.

Material findings were fixed before acceptance. The only failed CI states in the cycle were
test-regression assertions discovered during review; both were corrected and followed by
green full workflow runs.

## Current exact boundary

Do **not** implement a standalone priority-only allocator next.

The next design unit is the shared lower network-policy ownership/allocation layout for:

```text
routing domains / tables
route ownership marker
RPDB priorities
route metric spaces
payload/probe owner scopes
cleanup identity
```

That layout must feed the accepted `RoutePriorityDomainRealization` contract without moving
Linux identifiers into PayloadTrafficManager or user configuration.

After that, the larger remaining implementation boundaries include:

- guarded structural-policy convergence;
- RPDB/nft and Device NAT/envelope/publication materialization;
- availability probe execution;
- lifecycle/runtime assembly.

## Human decisions

None currently required.

The next boundary is internal architecture/implementation work and does not change accepted
user-visible configuration, product scope or Release 1 semantics.

## Checkpoint verdict

**PASS — CURRENT REVIEW UNIT COMPLETE.**

Autonomous development stops after this checkpoint commit and resumes only after the next
user turn, using a new/reset cycle clock as required by `CONTINUOUS-DEVELOPMENT.md`.
