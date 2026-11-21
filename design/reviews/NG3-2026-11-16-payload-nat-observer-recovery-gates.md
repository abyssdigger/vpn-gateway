# NG3 — requirement and component gates: authoritative payload NAT observer

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-nat-observer-recovery-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Review unit:** read-only authoritative payload NAT observation/comparison; no actuation.

## Recovery context

The previous cycle produced five GitHub commits after accepted design commit
`943f20d1`, but implementation was written without a correctly documented requirement
and component gate or a fresh CD cycle. Those commits remain historical candidate code
only. This review establishes the normative gates **before** adopting any of that code
on the new branch. It does not retroactively declare the earlier workflow compliant.

## Requirement gate

**Implements:**
- `VPNG-U001-R1.R2.R4.R6.R1` — explicit `none / masquerade` Device NAT need;
- `VPNG-U001-R1.R3.R2` — current binding identifies the actual endpoint;
- `VPNG-U001-R1.R3.R3` — same-name replacement never inherits stale identity;
- `VPNG-U004-R4.R3.R2` — NAT change is a guarded structural transition;
- `VPNG-U004-R4.R4` — forwarding not ready before safe initial boundary;
- `VPNG-U004-R4.R5` — authoritative observation after failure/uncertainty.

**Constrained by:**
- `VPNG-U001-R1.R2.R4.R6.C1` — unaccepted human-facing Device grammar must not be inferred.

The complete ancestry was checked in `design/NG3/requirements.md`.
The primary roots `VPNG-U001` and `VPNG-U004` have an externally sourced
2026-11-15 customer-interview **Basis** and normative **Statement**, both `[closed]`.
For the Device NAT chain the derived ancestry is
`VPNG-U001 -> R1 -> R1.R2 -> R1.R2.R4 -> R1.R2.R4.R6 ->
R1.R2.R4.R6.R1`. The binding chain is
`VPNG-U001 -> R1 -> R1.R3 -> R1.R3.R2/R3`.
For safety the ancestry is
`VPNG-U004 -> R4 -> R4.R3 -> R4.R3.R2`, plus
`VPNG-U004 -> R4 -> R4.R4/R5`.
Every relevant derived node has distinct **Purpose** and **Statement**;
the applicable `...R6.C1` has **Reason** and **Statement**. All selected
nodes are `[closed]`, and the normative actor is explicitly VPN-GATE or
unambiguously the user/configuration boundary.

No product promise or user-facing grammar changes in this review unit.
Accepted evidence: strict parser comparison tests and existing EXP-033
kernel-platform evidence for interface operand representation. No semantic
ambiguity remains at this limited read-only scope.

**Requirement gate verdict: PASS for this unit only.**

## Component-design gate

**Scenario:** A previously used VPN endpoint is replaced with the same ifname but a
different ifindex; old masquerade state may remain in the owned nft chain. The system
must distinguish stale owned NAT from matching current desired state without
accidentally adopting a replacement endpoint.

**Component type and boundary:** A **Direct Calculator** under
`design/component-model.md`. Existing `LinuxNftNamespaceBackend` is a
read-only lower Adapter supplying canonical nft objects; independent fresh
interface inventory and pure `PayloadNatDesiredState` are explicit inputs.
The Calculator performs strict normalization/classification and returns
immutable `confirmed/missing/stale/conflicts` values; no kernel I/O or mutation.

**Responsibilities / interactions / traceability:** `VPNG-U001-R1.R3.R2/R3`
requires exact current identity; `VPNG-U001-R1.R2.R4.R6.R1` requires mapping
explicit desired NAT to current paths; `VPNG-U004-R4.R3.R2/R4/R5` requires no
mutation or forwarding authorization on uncertainty. All processing is direct:
adapter observation -> confirmed scaffold -> pure classification -> result for
later structural Executor. Handles identify actual rule objects only.

**External environment:** EXP-033 proves nft live interface operands display
names, disappeared ifindices display decimal strings, and same-name replacement
does not match old ifindex. No unverified platform claim is introduced.

**Necessity and simplification:** Desired-state projection cannot establish
kernel-owned actual state; strict observer is required. Reuse existing
`NftNamespaceObservation`, scaffold and interface identity. No new Agent,
Manager, event, cache, async retry, persistence, second policy-classification
component or user NAT grammar.

**Constraints / lifting:** Observed conflicts and unclassified state prevent
future mutation authority. This limits an internal recovery procedure, not the
accepted product capability. Read-only observation preserves existing
`ForwardingGate` boundary. Unfinished physical NAT materialization remains a
separate gated unit.

**Evidence plan:** Run explicit unit regression for exact iif/oif/action,
current and stale numeric/name operands, duplicate handles/physical rules,
unknown owner, extra expression, missing scaffold, invalid inputs and drift.
Run GitHub NG3 CI; inspect actual result, then complete expert review and
resolve accepted findings.

**Component-design gate verdict: PASS for adopting/reviewing a read-only
Calculator. Physical NAT mutation is NOT authorized.**

## Next step

Review the historical candidate code at `e110276f` against the above contract;
adopt only fitting changes, execute evidence and record autonomous expert review.
