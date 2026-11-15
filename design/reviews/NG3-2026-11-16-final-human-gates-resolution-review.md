# VPN-GATE NG3 — Final Human Gates Resolution Review

**Cycle:** `ng3-design-cycle-20261116-final-gates-40m`  
**Base checkpoint:** `3bbb2b035468d85254c6ca4476e639b486653366`  
**Scope:** resolve H1 availability-evidence adequacy and H2 safe-transition continuity.

## Accepted human decisions

### H1 — availability criterion belongs to the user

VPN-GATE does not define one universal meaning of "VPN path is good".

For each availability-enabled logical path, the user selects the observation criterion.

First-release scope:

```text
mechanism = icmp
target = explicit IP | derive from current VPN endpoint/network facts
```

Future TCP/UDP/HTTP mechanisms are intentionally not first-release capabilities.

If target is omitted, VPN-GATE attempts to derive one unambiguous target from:

- accepted logical-path/VPN binding;
- current observed VPN endpoint/network state.

Failure or ambiguity during target derivation does not become path failure. It produces
diagnostic/`no_evidence`.

Thus:

```text
successful configured check -> positive evidence
valid configured check with no reply -> negative evidence
cannot resolve/execute criterion -> no_evidence + diagnostic
```

This preserves the user's ownership of what property constitutes practical path usability.

### Historical evidence for H1

Historical NG2 artifacts confirm the same separation of concerns:

- `AvailabilityProbeRequest` carried separate `mechanism + concrete path + target`;
- physical probe-plane identity was `(mechanism, InterfaceIdentity, target)`;
- payload availability contract intentionally excluded target/mechanism/cadence;
- late NG2 first-release mechanism was ICMP.

The exact earlier textual configuration spelling such as `icmp/<ip>` was not found in the
available normative artifacts during this review. NG3 therefore preserves the semantic
contract without making that particular string syntax normative.

## H1 requirement closure

New/accepted nodes:

- `VPNG-R3.R6.R3.R1` — user-selected availability criterion;
- `VPNG-R3.R6.R3.R1.C1` — first-release ICMP-only constraint;
- `VPNG-R3.R6.R3.R1.C1.R1` — user-facing ICMP configuration/onboarding contract;
- `VPNG-R3.R6.R3.R2` — omitted target requests derivation from current VPN endpoint facts.

Architecture:

- `ConfigurationAdapter` normalizes `AvailabilityCheckIntent`;
- `AvailabilityProbeAgent` resolves explicit/default target and owns observation context;
- `VPNPathAdapter` exposes current binding/network facts needed for derivation;
- `ActiveProbeDriver` first-release implementation is ICMP;
- unresolved/failed local check setup maps to `no_evidence`, not negative evidence.

**Verdict:** ACCEPT closure for the complete current `VPNG-R3.R6` subtree and parent
`VPNG-R3`.

## Accepted human decision H2 — preserve forwarding during pure priority permutation

For a transition that changes only route priority/order among the same already-eligible path
set, VPN-GATE must not create a planned outage merely to permute metrics.

The accepted architecture is the historically proven route-slot / "metric hole" model.

For N eligible routes the planner uses N+1 ordinary metric positions.

Primitive:

```text
X at Mold
Mfree free

add X at Mfree
delete X at Mold
```

During the intermediate state:

- every eligible path remains represented;
- X temporarily exists twice at different metrics;
- no ineligible path is introduced.

The old metric becomes the next free slot.

This continues until desired priority order is reached.

### Historical evidence for H2

NG2 `design/NG2/availability-routing-model.md` and the NG2 handoff record this exact
make-before-break model.

EXP-027 demonstrated the material Linux claims:

- one path may simultaneously exist at two metrics for one destination;
- adding the duplicate does not remove the old route;
- exact deletion removes only the old metric copy;
- the complete eligible path set remains present;
- ordinary prefixes and `default` both work.

That kernel evidence is reusable because NG3 makes the same technical claim. The NG2 product
model itself is not inherited automatically.

## Structural transitions remain fail-closed

The route-slot proof applies only when path membership and other structural policy semantics
are unchanged.

If membership, direction, filtering/NAT or another structural dimension changes, the
Executor may temporarily restrict affected forwarding to preserve safety.

Continuity must not be achieved by transiently allowing traffic that old/new policy forbids.

New/accepted nodes:

- `VPNG-R4.R3.R1` — priority-only transitions preserve all eligible paths;
- `VPNG-R4.R3.R2` — structural changes may use restrictive/fail-closed transition.

Architecture:

- priority-only: deterministic N+1 metric-slot make-before-break transaction;
- structural: guarded fail-closed convergence;
- both re-observe authoritative state after partial failure.

**Verdict:** ACCEPT closure for `VPNG-R4.R3` and parent `VPNG-R4`.

## Simplification review

H1 does not require:

- universal health semantics;
- probe plugin framework;
- HTTP/TCP/UDP support in first release;
- evidence history;
- treating local probe errors as path failure.

H2 does not require:

- a staging routing table;
- deletion/re-addition of eligible paths during priority permutation;
- a second availability route executor;
- global route transaction queue;
- hitless guarantees for structural membership/filtering changes.

## Purpose / Reason review

All new Purpose/Reason chains are explicit and were human-approved in this cycle.

No new node relies on a preferred architecture to invent its Purpose.

The ICMP-only node is a constraint because it narrows the user-selectable check-mechanism
envelope for the first release. Its compensating user contract is explicit as a child
requirement.

## Final verdict

**PASS.**

The two human gates from the previous checkpoint are resolved.

Subject to mechanical traceability validation, every current NG3 requirement/constraint node
may now have accepted architecture closure.
