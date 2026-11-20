# VPN-GATE NG3 — host-routing helper / administrative containment gap intermediate review

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-rudiment-cleanup-finish-35m`  
**Base:** `10ce8295b1e12ba73d1dd4f40206691278df48bd`  
**Status:** intermediate requirement/evidence review; no normative requirement or architecture mutation in this review

## Scope

This review records the current human-agreed findings reached while cleaning the obsolete
`VPNG0002-R2.R3.R1` / `VPNG0002-R2.R3.R2` direction decomposition and revalidating the
host-routing architecture/evidence that used to depend on it.

The review deliberately does **not** create requirement IDs, choose final configuration
spelling, or change current architecture. Those changes remain a separate requirement/design
unit.

The local discussion shorthand `AHTUNG` is not proposed as product terminology. In this
review the capability is called **administrative payload containment mode**.

## Accepted boundary correction

The core VPN-GATE managed-forwarding safety contract ends at the explicit ordinary-side
managed boundary unless a separately accepted product capability explicitly extends
responsibility into ordinary host state.

Administrator-owned host routing is therefore not implicitly part of Profile direction
policy and is not made unsafe merely because it bypasses VPN-GATE.

A host-routing convenience/guard facility must be modeled as an optional capability rather
than as an unconditional consequence of `Profile.direction`.

## Host-routing assistance is a separable add-on capability

The agreed model is a conditionally independent host-routing helper/add-on:

- VPN-GATE core exposes the ordinary-side managed boundary and its own managed-domain
  forwarding semantics;
- the helper decides how ordinary host traffic is routed to that boundary;
- core VPN-GATE does not need to know the helper's internal host-routing mechanisms;
- the helper may use only explicitly supported VPN-GATE control operations when it needs the
  gateway to change operational state.

Two distinct helper behaviors are needed because they promise materially different things.

### Simple startup/lifecycle helper

The simple helper exists to reduce routine administrator work.

Its intended semantics are:

- on start/reload, install the host routes required for the current helper intent;
- on stop, remove helper-owned host-routing state;
- between those lifecycle boundaries, no continuous ownership/recovery promise is implied;
- administrator changes may therefore replace or break that routing without forcing core
  VPN-GATE into fail-closed state;
- future diagnostics may report broken/replaced helper routes, but such diagnostics alone do
  not create a recovery or safety guarantee.

This is the appropriate baseline helper for an administrator-owned host.

### Aggressive helper

Aggressive behavior is a different opt-in contract, not a stronger default of the simple
helper.

Its purpose is to make the host-routing area explicitly delegated to the helper authoritative
while the capability is active. The currently agreed decomposition is:

1. **authoritative managed-destination routing** — destinations accepted into the aggressive
   helper's managed set must not silently escape through competing ordinary host routing;
2. **continuous ownership/recovery** — material drift in helper-owned host-routing state is
   observed and repaired when exact safe recovery is possible;
3. **unrecoverable-alarm containment** — if the helper cannot restore or confirm the state
   needed for its routing guarantee, it applies its available host-side fail-closed measures
   and requests the VPN-GATE administrative payload containment mode through the public
   control contract.

The helper remains independent from VPN-GATE internals: requesting containment is use of a
supported administrative API, not direct manipulation of the gateway's forwarding internals.

## Administrative payload containment mode

A separate VPN-GATE administrative safety capability is required independently of the
host-routing helper.

The agreed product-level meaning is intentionally mechanism-neutral:

- managed runtime remains alive for diagnosis and recovery;
- no IP payload is allowed to cross the ordinary-side managed boundary in either direction;
- IP transit that could create cross-VPN leakage is also prevented;
- internal runtime/configuration/path state should be preserved rather than destroyed as by a
  full stop;
- entering and leaving the mode are explicit administrative control operations;
- an administrator may invoke the operation directly;
- an external helper, including the aggressive host-routing helper, may invoke the same
  published operation.

The requirement must describe the traffic/result guarantee, not prescribe
`ip_forward=0`, nftables, a particular boundary gate, or any other lower mechanism.

The current Linux implementation may reuse already-proven forwarding-barrier mechanisms, but
that is architecture/evidence work rather than requirement wording.

## Release-scope decision

The following capabilities are explicitly **not required for Release 1**:

- administrative payload containment mode;
- aggressive host-routing helper, including continuous hostile-drift recovery and
  unrecoverable-alarm containment.

The simple startup/lifecycle host-routing helper is not included in that postponement and
remains a candidate for the normal first-release operator convenience surface.

The eventual requirement tree should express these as constraints rather than by silently
omitting the capabilities from architecture.

## EXP-074 gap and accepted disposition

`EXP-074` is not obsolete evidence. The problem was its previous mapping to unconditional
core host-routing semantics.

Its distinguishing PASS is well matched to the first aggressive-helper child above:
**authoritative managed-destination routing**.

EXP-074 directly demonstrates, for the tested Linux realization, that:

- managed destinations, including managed `0.0.0.0/0`, do not escape through a competing
  more-specific host-`main` route;
- a dynamically added competing more-specific host-`main` route also does not create such an
  escape;
- a nested managed prefix is still directed to the managed boundary;
- packets already arriving from STACK through the managed boundary are not recaptured;
- kernel-local delivery remains local;
- cleanup can leave unrelated host-`main` state unchanged.

A future requirement for this child should state the observable authoritative-routing
semantics without prescribing a dedicated table, RPDB ordering, Linux rule priority, or the
`vpng0` implementation name.

When that requirement exists and its ancestry is accepted, EXP-074 can remain selected and
can close that **narrow child** completely.

EXP-074 does **not** by itself prove:

- periodic/continuous drift detection;
- repair of deleted or corrupted helper-owned routing state;
- response to an unrecoverable ownership conflict;
- the public administrative payload-containment operation;
- the composition `aggressive helper -> containment request`.

Those require separate evidence/closure.

## Earlier host-routing evidence

The older host-routing experiments should no longer be treated as a simple linear progression
where EXP-074 made every previous semantic irrelevant.

In particular:

- EXP-059 proved a specificity-preserving host-routing mechanism where strictly
  more-specific ordinary `main` routes could continue to win;
- EXP-060 proved a production-shaped implementation of that mechanism;
- EXP-072 proved the corresponding behavior on the routed managed-L3 boundary.

Those results remain valid technical evidence and may be useful when closing the simple
administrator-owned helper semantics. Their mechanisms are not automatically reselected as
architecture merely because the evidence is useful.

EXP-074 instead belongs to the opt-in authoritative/aggressive branch.

## Other evidence that requires remapping

The current cleanup must also revalidate the following evidence rather than leaving dangling
references to removed requirement IDs:

- **EXP-054** is already `historical_only` and unexecuted. Its old requirement references
  should become explicit historical context, including the text/meaning of the requirement
  that existed when the experiment was prepared and the fact that it was later removed.
- **EXP-070** remains selected for routed-veth/Proxy-ARP managed-L3 and Debian-12 portability
  evidence. Its old host-bootstrap requirement references must be remapped to live managed-L3
  boundary requirements rather than preserved as dangling IDs.
- **EXP-075 / EXP-076** must be split conceptually between core Profile-SNAT behavior and
  ordinary-host reverse reachability supplied by a host-routing helper. The Profile-SNAT
  requirement already limits its promise to the source identity at the managed boundary.
- **EXP-030** and other historical containment/blackhole evidence should be checked against
  the future administrative payload-containment requirement. Existing lower facts may provide
  partial evidence, but must not be claimed to close a broader new control/API contract that
  they did not test.

## Traceability rule for removed requirements

The cleanup rule agreed during this review is:

- current/live architecture and selected/current evidence must not depend on requirement IDs
  absent from the current requirement tree;
- when the same semantics honestly remain in a live ancestor, traceability may be lifted to
  that ancestor;
- when a live artifact proves a capability that has no honest current requirement mapping,
  that is a requirement gap and must be resolved before claiming current closure;
- historical reviews must not be rewritten to pretend that they reviewed today's requirement
  tree, but dangling historical IDs must be clearly marked as IDs from the then-current tree;
- historical-only experiments may retain the old requirement wording/ID only as explicit
  historical context, including that the requirement was later removed.

This keeps both current traceability and historical truth intact.

## Current architecture finding

The current `Host managed-destination routing` architecture section is in a transitional
state after removal of the obsolete direction decomposition.

Its remaining references (`VPNG0002-R2.R6` and managed-domain isolation requirements)
justify individual return/ownership properties but do not honestly justify the entire
automatic host-routing owner.

The section must therefore be revisited after the helper requirements above are added. It
must not regain authority by mechanically attaching a broad direction ancestor.

Likewise, core runtime composition should later be reviewed for places where exact host
managed-routing state currently controls core managed forwarding. Under the accepted
separation, simple helper failure must not become an internal core-gateway failure merely
because the helper is absent or broken.

## Requirement-work direction

No final IDs are assigned by this review.

The expected requirement shape is:

```text
VPN routing / operator convenience
    host-routing assistance
        simple startup/lifecycle helper
        aggressive helper
            authoritative managed-destination routing   <- EXP-074
            continuous ownership/recovery
            unrecoverable-alarm containment

Safety / administrative control
    administrative payload containment mode
```

The administrative containment capability should not be made a child of the aggressive
helper: it has independent administrator value and the helper is only one possible caller.

The aggressive helper's unrecoverable-alarm requirement may depend on that independent
capability through an explicit decomposition/constraint relationship once exact requirement
IDs exist.

## Next cleanup work

After this checkpoint, continue read-only requirement/evidence review one candidate at a time.

Before implementing any of the new behavior:

1. draft exact Purpose + Statement + release constraints for the new requirement nodes;
2. validate each node against its immediate ancestry;
3. add the accepted requirement nodes only after explicit write authorization;
4. remap current architecture/evidence to live IDs;
5. mark historical dangling IDs explicitly historical rather than silently rewriting history;
6. re-evaluate current host-routing code/runtime coupling against the simple-helper vs
   aggressive-helper separation;
7. determine which existing containment experiments are sufficient lower evidence and what
   new acceptance evidence is still missing.

## Verdict

**INTERMEDIATE ACCEPTED DIRECTION.**

The previous unconditional core host-routing model was overbroad, but the host-routing work
does not collapse into a single obsolete mechanism.

The corrected model preserves three independently useful ideas:

- simple lifecycle host-routing assistance for routine administration;
- opt-in aggressive authoritative host-routing with continuous guarding and fail-closed
  escalation;
- a separate administrative payload-containment mode that freezes managed IP transit while
  preserving runtime state for diagnosis.

EXP-074 remains useful and can become exact closure evidence for the narrow authoritative
managed-destination child of the aggressive helper after that requirement is formally added.
