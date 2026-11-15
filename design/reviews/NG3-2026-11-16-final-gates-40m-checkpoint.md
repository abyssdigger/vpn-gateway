# VPN-GATE NG3 — Final Human Gates 40m Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261116-final-gates-40m`  
**CYCLE_INTERVAL:** 40m  
**Base:** `3bbb2b035468d85254c6ca4476e639b486653366`

## Cycle clock

```text
first content commit:
5f7b567317cf825ecd557220f178db5f05deadf2
2026-11-15T23:38:52Z
NG3: resolve availability criterion and safe-transition semantics

whole-tree closure review head:
660b34faa32a994bc6aff2f5f6a736fcd17664a2
2026-11-15T23:41:40Z
NG3: record whole-tree architecture closure

elapsed:
2m 48s
```

The cycle is checkpointed before the nominal interval because its complete review unit was
resolved by explicit human decisions supplied at cycle start. No unrelated design unit is
started merely to consume the remaining interval.

## H1 resolved — user-defined availability criterion

Accepted product semantics:

- the user defines the criterion used to assess a VPN path;
- availability configuration carries mechanism plus optional target;
- first release supports ICMP echo;
- explicit target is used directly;
- omitted target requests derivation from accepted VPN binding and current observed VPN
  endpoint/network facts;
- failed/ambiguous derivation or local execution failure yields diagnostic/`no_evidence`;
- future TCP/UDP/HTTP checks remain outside first-release scope.

New requirement nodes:

- `VPNG-R3.R6.R3.R1`;
- `VPNG-R3.R6.R3.R1.C1`;
- `VPNG-R3.R6.R3.R1.C1.R1`;
- `VPNG-R3.R6.R3.R2`.

Architecture:

- `AvailabilityCheckIntent` in the configuration boundary;
- AvailabilityProbeAgent resolves explicit/derived target;
- VPNPathAdapter exposes current endpoint/network facts needed for derivation;
- first-release ActiveProbeDriver is ICMP;
- target/context changes invalidate stale observations.

Historical NG2 architecture confirmed mechanism/path/target separation and ICMP transport.
The exact old textual spelling `icmp/<ip>` was not recovered from retained normative files,
so NG3 does not make that spelling itself normative.

## H2 resolved — make-before-break priority permutation

Accepted product semantics:

- pure priority/order transition over unchanged eligible paths must not temporarily remove
  an eligible path;
- structural policy changes may still use restrictive/fail-closed transition when needed for
  safety.

Accepted Linux architecture for pure priority transition:

```text
N eligible routes
N+1 ordinary metric positions
one emergent free position

move:
    add same route at free metric
    delete old metric copy
```

During the move all eligible paths remain present; one path may temporarily have two route
copies with different metrics.

Historical NG2 `design/NG2/availability-routing-model.md`, NG2 handoff and EXP-027 provide
reusable evidence for the materially identical Linux route behavior.

New requirement nodes:

- `VPNG-R4.R3.R1`;
- `VPNG-R4.R3.R2`.

## Architecture/document cleanup

The architecture was refreshed after gate resolution:

- root R1-R7 document-level traceability is explicit;
- stale statements that path identity/configuration/status/availability evidence were still
  open were removed;
- coverage table now reflects accepted normalized payload, availability and safety
  architecture;
- remaining "gaps" were reframed as implementation freedoms/future extensions where no
  accepted requirement remains unresolved.

## Final current-tree state

```text
requirement/constraint nodes: 83
closed:                       83
pending_closure:               0
rejected_closure:              0
open:                          0
```

Integrity:

```text
unique architecture requirement refs:     83
closed without architecture reference:     0
malformed normative requirement lines:     0
active decomposition blocks:                0
broken decomposition links:                 0
blocked node with invalid closure state:    0
stale architecture open-gap claims:         0
```

Process validation:

```text
requirement refinement steps: contiguous 1..12
Purpose/Reason human escalation gate: present
closure lifecycle model: present
```

## Review artifacts

- `design/reviews/NG3-2026-11-16-final-human-gates-resolution-review.md`
- `design/reviews/NG3-2026-11-16-whole-requirement-architecture-closure-review.md`

Whole-tree verdict:

**PASS — COMPLETE CURRENT NG3 REQUIREMENT/ARCHITECTURE CLOSURE.**

## Next phase boundary

Architecture closure is not implementation completion.

The next cycle may move into implementation/evidence planning by selecting a bounded review
unit and tracing it from the already-closed requirements into code and tests.

Closed requirements should be reopened only when implementation evidence exposes a real
semantic contradiction, newly discovered constraint, or missing requirement — not merely
because implementation prefers another mechanism.
