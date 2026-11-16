# Secondary analysis of external review

Source: independent project review ("мальчик"), archived from project discussion on
2026-11-12.

## Verdict

The external reviewer is substantively correct on the serious findings. The analysis
checked the findings against the architecture, implementation and EXP-013.

### 1. Inbound/bidirectional return path

Confirmed HIGH severity. Outbound return path is naturally asymmetric in the correct
direction: host-originated NEW selects the Profile path and remote reply returns on the
same tunnel into main->host0. Remote-initiated NEW is different: the host reply is routed
again by destination through the Profile table and may choose a lower-metric Device than
the one that admitted the request.

Capacity==1 is a correct first-production solution. General multi-interface support should
use flow pinning and needs a kernel experiment.

Important integration clarification: parser rejection of inbound/bidirectional and the
capacity-1 rule are independent mechanisms. In the current project state the Device
envelope already exists, so total parser rejection is no longer necessarily required.

### 2. ESTABLISHED interface scoping

Confirmed. Architecture wording was ambiguous, while the safe implementation is explicit
bound-interface<->host0 pairs only. Residual cross-bound-interface tuple acceptance is a
flow-pinning problem.

### 3. INPUT and host-side inbound boundary

Confirmed HIGH severity. INPUT must be default DROP and explicit. The current Profile
model only constrains the remote prefix; it does not constrain host-side destination.
Device->ROU-local DROP is defense in depth and does not break relay traffic because the
host-side relay reaches the internal listener via host0.

### 4. Barrier scope

Confirmed, with an additional correction to prior review advice: invariant 62 is not merely
over-scoped, it is wrong if interpreted as requiring a global barrier for ordinary member
disappearance.

With persistent shadow fallback:

- member disappearance removes its direct route and may remove multipath fallback;
- survivor normal routes remain;
- blackhole remains;
- rebuilding fallback is safe without global ip_forward=0;
- member appearance is additive;
- availability transition is supported by persistent fallback;
- structural/unknown drift remains the case requiring barrier.

Recommendation: retain shadow fallback, because it is already implemented and EXP-013
proven, but refine transition classification and remove the incorrect barrier invariant.

### Smaller findings

All are valid:

- bootstrap/publication ordering;
- explicit NAT;
- MTU/MSS production experiment;
- fib_multipath_hash_policy ownership;
- project convention/current-baseline drift.

## Overall recommendation

Integrate the serious findings and barrier correction in one semantic architecture pass,
then review/update implementation before continuing broader production implementation.
