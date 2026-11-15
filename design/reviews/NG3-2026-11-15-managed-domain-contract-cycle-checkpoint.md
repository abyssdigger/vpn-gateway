# VPN-GATE NG3 — Managed Domain Contract Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**CYCLE_INTERVAL:** 40m  
**Checkpoint reason:** all autonomous requirement/design work for the current tree is complete; the only remaining open branches require explicit human product decisions.

## Cycle clock

```text
cycle start:
e7ee99f6e3634c52c3690fc8bd817fb84fb66438
2026-11-15T20:50:47Z
NG3: define managed network domain contract

last content head before checkpoint:
586fb92afee8751e636aa111066950a2cc38b216
2026-11-15T21:14:40Z
NG3: trace lifecycle parent requirement

elapsed to last content head:
23m 53s
```

The cycle is checkpointed before 40m because continuing would require making decisions that
the current process explicitly reserves for human acceptance.

## Requirement state

```text
R/C nodes: 77
closed:    72
open:       5
```

Open nodes:

```text
VPNG-R3
└── VPNG-R3.R6
    └── VPNG-R3.R6.R3

VPNG-R4
└── VPNG-R4.R3
```

Mechanical checks:

```text
malformed requirement lines:              0
closed/pending_closure without arch ref:  0
broken decomposition links:               0
active decomp blocks:                     0
active block + invalid closure state:      0
refinement procedure numbering errors:     0
```

## Major closures accepted in this cycle

- managed network domain contract and explicit host/domain boundary;
- externally provisioned VPN-channel onboarding placement contract;
- logical VPN path identity and current concrete-endpoint binding;
- minimal declarative configuration boundary;
- explicit traffic policy normalized contract;
- thin lifecycle control surface;
- local Manager reconciliation for drift/retry;
- runtime observability via non-owning Status Agent;
- complete current implementation-quality R7 subtree;
- bounded availability hysteresis semantics;
- managed-router R1 subtree;
- settled safety nodes except safe transition.

## Requirement-process changes accepted in this cycle

- stable decomposition dependency link:
  `[decomp: blocker -> pending|deblocker]`;
- constraint review must identify who absorbs externalized work and what the product must
  provide that participant;
- architecture closure lifecycle:
  `open -> pending_closure -> closed | rejected_closure`;
- asymmetric closure invariant:
  closure requires architecture reference; architecture reference does not imply closure;
- closure may be documentary/architectural and does not require code;
- unclear `Purpose` / `Reason` is a mandatory human-escalation condition;
- affected ancestry must be reviewed rather than locally inventing a justification;
- Git history remains sufficient editorial history; semantic change journal deferred.

## Human gate H1 — availability evidence adequacy

Affected requirements:

- `VPNG-R3.R6.R3`;
- `VPNG-R3.R6`;
- `VPNG-R3`.

Decision required:

> What observed property is sufficient to call a VPN path usable/unusable?

Current simplest candidate is active reachability observation through the concrete VPN path
to a target beyond the local endpoint.

Accepting that candidate normally introduces a constraint: target failure may be
indistinguishable from path failure, so a suitable expected-responsive target must exist and
the product must provide the administrator/integration contract for it.

This product-envelope constraint has not been accepted autonomously.

## Human gate H2 — safe transition continuity

Affected requirements:

- `VPNG-R4.R3`;
- `VPNG-R4`.

Decision required:

> May an ordinary network-policy transition temporarily block affected managed traffic in
> order to guarantee fail-closed safety?

Two materially different valid-looking semantics remain:

```text
A. guarded fail-closed transition
   temporary interruption allowed
   simpler safety/convergence machinery

B. hitless / make-before-break transition
   ordinary allowed forwarding must remain continuous
   materially more complex lower-network transaction machinery
```

Current requirements do not choose between them. This is user-visible product behavior and
therefore cannot be selected as an implementation detail.

## Verdict

**AUTONOMOUS CYCLE PASS: COMPLETE.**

**Requirement/design gate: BLOCKED only on H1 and H2 human decisions.**

No new implementation cycle should begin for behavior depending on R3/R4 until those
decisions are accepted and the five open nodes are refined/reviewed.
