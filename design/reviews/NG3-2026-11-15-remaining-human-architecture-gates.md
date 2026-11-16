# VPN-GATE NG3 — Remaining Human Architecture Gates

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** the only remaining open requirement branches after autonomous NG3 decomposition.

## Current closure state

The requirement tree contains 77 R/C nodes.

At this review point:

```text
closed: 72
open:    5
```

The only open nodes are:

```text
VPNG-R3
└── VPNG-R3.R6
    └── VPNG-R3.R6.R3

VPNG-R4
└── VPNG-R4.R3
```

All other current NG3 requirement/constraint nodes have accepted architecture closure.

# Gate H1 — What observation is sufficient path-usability evidence?

Affected nodes:

- `VPNG-R3.R6.R3`;
- `VPNG-R3.R6`;
- parent `VPNG-R3`.

## What is already decided

Architecture already defines:

- stable logical path identity;
- stale observation rejection;
- active observation Agent/Driver boundary;
- normalized evidence `positive | negative | no_evidence`;
- bounded degradation/recovery confirmation;
- availability affects priority only.

The remaining question is not hysteresis.

It is:

> **What concrete observed property is strong enough to classify a VPN path as usable or
> unusable for the product scenarios we promise?**

## Why this is not an autonomous architecture detail

A simple active remote probe is attractive, but it introduces a product-envelope assumption:

```text
probe target failure
can be indistinguishable from
VPN path failure
```

Accepting that design normally implies some external contract such as:

- an observation target must exist;
- it must be expected to respond through the tested VPN path;
- the administrator/integration must provide or select it;
- the product must explain how to configure and validate that target.

That is a constraint which moves work to the administrator and narrows the effective product
envelope. Under the current process it requires human acceptance.

## Candidate direction, not yet accepted

The simplest current candidate is:

```text
active observation traverses the concrete VPN path
    ->
reaches a configured/derived target beyond the local VPN endpoint
    ->
expected response => positive evidence
confirmed path-level failure/timeout => negative evidence
local execution uncertainty => no_evidence
```

No concrete ICMP/TCP/protocol mechanism is proposed as a requirement.

If this direction is accepted, the next step is to add the corresponding constraint plus
the compensating administrator/integration requirement.

# Gate H2 — May a safe network-policy transition temporarily block traffic?

Affected nodes:

- `VPNG-R4.R3`;
- parent `VPNG-R4`.

## What is already decided

The lower network architecture already requires:

- observe current authoritative state;
- deterministic convergence planning;
- verified postcondition;
- fail closed when the safe result cannot be confirmed;
- fresh re-observation after partial failure.

The remaining question is transition availability.

## Two materially different product behaviors satisfy the current wording

### Option A — guarded fail-closed transition

Before changing route/policy objects:

1. install/retain a restrictive guard for the affected managed traffic;
2. mutate lower network state behind the guard;
3. verify the desired postcondition;
4. remove/relax the guard only after verification.

Properties:

- simple safety argument;
- avoids complicated cross-subsystem make-before-break machinery;
- a policy transition may temporarily interrupt otherwise allowed managed traffic.

### Option B — hitless / make-before-break transition

The system must preserve allowed forwarding throughout ordinary route/policy transitions.

Properties:

- stronger continuity behavior;
- materially more complicated lower-network transaction machinery;
- may require spare route states, carefully ordered replacements or other kernel-specific
  mechanisms and experiments.

## Why this requires human discussion

The difference is externally observable.

Current requirements strongly prefer safety over unintended forwarding, but do not explicitly
say whether a short planned interruption during reconfiguration is acceptable.

Choosing Option A or B therefore decides product semantics rather than merely implementation.

No constraint or child requirement is added until that decision is accepted.

# Purpose / Reason escalation result

Neither open branch has an unclear existing Purpose:

- R3 evidence adequacy exists so adaptation reflects real path usability;
- R4 safe transition exists so a correct final policy is not reached through an unsafe
  intermediate forwarding state.

The escalation is therefore not caused by meaningless requirements.

It is caused by the next refinement requiring a new product-envelope/user-visible decision.

# Final verdict

**AUTONOMOUS DESIGN PASS COMPLETE — HUMAN GATES REMAIN.**

No further autonomous decomposition of these two branches should be performed.

Independent implementation should remain gated where it depends on the five open nodes.

Once H1 and H2 are decided, the tree can be refined minimally, architecture can be completed,
and the two remaining L1 parents can be reviewed for closure.
