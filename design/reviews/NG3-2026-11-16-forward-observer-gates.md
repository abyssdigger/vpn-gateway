# NG3 — design gate: authoritative payload_forward observation + EXP-037

**Дата:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`

## Requirement gate

**Implements:** `VPNG0002-R2.R1.R2`, `VPNG0002-R2.R3.R3`,
`VPNG0002-R2.R5.R1`, `VPNG0001-R1.R3.R2`,
`VPNG0001-R1.R3.R3`, `VPNG0004-R4.R1`,
`VPNG0004-R4.R2`, `VPNG0004-R4.R5`.

**Constrained by:** `VPNG0002-R2.R3.C1`,
`VPNG0001-R1.R2.R4.R6.C1`.

Current NG3 ancestry was rechecked: primary roots carry Basis + Statement,
derived nodes Purpose + Statement, constraints Reason + Statement, all
required nodes are closed. No product ambiguity is being decided here.

**Requirement gate: PASS** for strict read-only lower observation.

## Component design

**Scenario:** structural recovery encounters existing rules in the marked
`payload_forward` chain. It must distinguish exactly recognized current or
stale VPN-GATE rule shapes from foreign/unsupported state before mutation.

**Component:** Direct Calculator. Inputs are immutable
`NftNamespaceObservation` plus one fresh tuple of `InterfaceIdentity`.
Output is immutable recognized NEW/RETURN rules and explicit conflicts.
No I/O, lifecycle, policy choice or mutation.

**Responsibilities / interactions:** scaffold proves table/chain identity;
observer owns only rule decoding. It preserves state class, iif/oif generation,
remote prefix selector field and handle. Higher Calculator/Executor later owns
desired comparison and convergence.

**Technical ambiguity:** EXP-035/036 used `/24` and test-only counters.
Production owner shape should omit counters by simplification, but strict
parser behavior for `/32` and no-counter nft JSON must be proven rather than
guessed. EXP-037 is the cheapest sufficient privileged verification.

**Constraints:** unknown rule forms remain conflicts. This is internal
ownership safety, not a user-facing product restriction. It cannot be used to
reduce accepted Profile functionality.

**Simplification:** no counter ownership, no generic nft AST, no Profile
compiler, no stored handles, no mutation.

**Evidence:** EXP-037 + parser unit regression + one live observer integration,
then expert review.

**Component-design gate: PASS conditional on EXP-037; implementation remains
GATED until that experiment passes.**


## Amendment — EXP-038 prefix-boundary representation

After EXP-037 PASS, review identified a remaining external representation gap:
the accepted Profile destination contract allows any strict IPv4 CIDR, and
`/0` may be optimized specially by nft. Generalizing the observed `/24`
prefix-object form to all non-`/32` values is not sufficient evidence.

The implementation gate is therefore **re-closed** until EXP-038 records
canonical NEW/RETURN JSON for `/0`, `/1`, `/31`, and `/32`.
This is technical parser evidence only; no product semantic change.
