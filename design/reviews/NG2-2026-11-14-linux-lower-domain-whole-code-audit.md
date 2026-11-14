# NG2 — Linux lower-domain whole-code audit

**Дата:** 2026-11-14  
**Тип:** autonomous whole-slice implementation review  
**Scope:** owner composition through concrete Linux NetworkRulesAdapter

## Review criteria

Проверялись:

- dead/test-only production artifacts;
- duplicate implementation logic;
- unjustified abstractions;
- Adapter/Driver/component-model separation;
- transaction consistency between committed semantic state and physical state;
- generation replacement behavior;
- exact verification coverage;
- experiment contradictions;
- Linux details leaking above NetworkRulesAdapter.

## Findings

### W1 — rejected incomplete candidate could become physical without becoming committed

**Severity:** correctness / transactionality  
**Disposition:** fixed.

When requested rules referenced an unavailable concrete interface generation, the Adapter
could successfully materialize the candidate's fail-closed projection and only afterwards
return FAILURE because projected requested rules differed from the request.

Candidate rules and routing allocation were then intentionally not committed, leaving
physical state derived from a semantic generation that was not the committed owner
generation.

Fix:

- detect incomplete requested-owner projection before candidate materialization;
- reconcile the physical backend to the fail-closed projection of the last committed owner
  composition instead;
- return FAILURE for the rejected candidate;
- first rejected apply therefore proves a fresh empty owned scope;
- rejected replacement restores/proves the previous committed generation;
- subsequent renew cannot accidentally adopt the rejected candidate.

Unit tests cover first-apply and replacement cases.

### W2 — closed-state and final verification were duplicated

**Severity:** maintainability  
**Disposition:** fixed.

LinuxNetworkDriver had a separate _verify_closed implementation duplicating route, nft and
inventory checks from verify_linux_network.

The verifier now accepts an explicit expected_ip_forward override:

- closed structural checkpoint -> False;
- normal/final verification -> desired.ip_forward_required.

One exact verification implementation now owns all other invariants.

### W3 — backend Protocol and interface observation types were underspecified

**Severity:** boundary clarity  
**Disposition:** fixed.

LinuxNetworkBackend and LinuxNetworkDriver.observe_interfaces() used bare tuple/untyped
desired parameters.

Contracts now explicitly use:

- tuple[InterfaceIdentity, ...];
- LinuxNetworkDesired;
- LinuxDriverResult;
- LinuxNetworkVerification.

Private Adapter projection/state helpers are likewise explicitly typed.

### W4 — OwnerRulesRegistry retained test-only API surface

**Severity:** dead code  
**Disposition:** fixed.

OwnerRulesRegistry.get() and __len__() were not used by LinuxNetworkRulesAdapter.

They existed only because earlier focused registry tests exercised the helper as a generic
container.

Both surfaces were removed; tests now use the actual Adapter-consumed contracts:

- snapshot();
- registered_rules();
- token/identity lifecycle;
- staged preview operations.

One stale test reference caused a visible intermediate red CI run and was corrected without
production changes.

### W5 — generation validation remains deliberately defensive in more than one compiler

**Severity:** duplication review  
**Disposition:** retained.

Whole-network compilation validates that the physical snapshot does not contain conflicting
same-name/different-ifindex identities.

The standalone nft compiler also validates interface identity consistency.

This is intentional defensive validation because the nft compiler remains independently
testable/callable below the Adapter and must not assume every future caller used the
aggregate LinuxNetworkDesired compiler first.

No shared helper abstraction is introduced merely to remove a small duplicate guard.

### W6 — boolean predicate compiler complexity is justified

**Severity:** complexity review  
**Disposition:** retained.

The DNF compiler in linux_nft.py is nontrivial but directly implements already-required
semantic TrafficPredicate forms:

- first-match envelope projection;
- default allow/drop complements;
- nested ALL/ANY/NOT;
- more-specific Profile exclusion.

It is bounded by MAX_DNF_CLAUSES and has no generic implication solver.

Replacing it with nft syntax above the Adapter would violate the semantic boundary;
flattening policy earlier would increase payload-domain complexity.

### W7 — exact-ifindex reuse remains an evidence boundary, not hidden state

**Severity:** known kernel identity limitation  
**Disposition:** retained/documented.

The implementation distinguishes generations by (ifname, ifindex), matching EXP-017 and
the existing availability experiments.

If Linux later reuses the exact same ifindex for a same-name interface, this identity model
cannot distinguish the generations without another kernel-visible generation token.

No speculative timestamp/history heuristic is added.

### W8 — no component-model leak found

**Severity:** architecture review  
**Disposition:** PASS.

Current lower-domain decomposition is:

    LinuxNetworkRulesAdapter
        -> owner composition / interface projection
        -> routing/filter/NAT desired compilers
        -> exact observation/verifiers
        -> LinuxNetworkDriver
            -> iproute2 / nft / sysctl

The Adapter owns semantic/domain translation and transaction state.

The Driver owns direct technical effects.

Pure compilers/verifiers do not publish Events, retain caller-domain policy history or
participate in asynchronous control flow.

No table ID, RPDB priority, route metric, nft rule text, conntrack state or barrier phase is
visible above NetworkRulesAdapter.

### W9 — bootstrap forwarding closure remains outside this slice

**Severity:** lifecycle requirement  
**Disposition:** non-blocking for this unit.

Every Adapter mutation starts by closing ip_forward, and structural recovery remains
fail-closed after errors.

A later runtime/bootstrap unit still must guarantee forwarding is protectively closed before
the first owner request after process/namespace startup, including restart with stale
physical state.

This is not solved by inventing more Adapter state.

## Regression/evidence

After accepted fixes the expected gate set is:

- NG2 rootless unit suite;
- privileged structural Linux integration;
- privileged live payload dataplane/NAT integration;
- NG1 Python validation.

Live evidence from the preceding focused review already covers:

- owner lifecycle;
- generation replacement;
- multi-owner sequential transition;
- /0 routing;
- terminal RPDB guard;
- route and foreign-nft drift;
- stateful flow direction;
- source NAT;
- final cleanup.

No incremental transition behavior was added during this audit.

## Final verdict

**PASS after cleanup.**

The audit-clean code baseline `d56feb60d3e0b0cf7efe0686059e87044975cfcf`
passed NG2 unit + privileged Linux integration and NG1 Python validation.

No unresolved lower-domain finding of minor severity or higher requires design
coordination.

The next implementation unit should be runtime/bootstrap assembly, not an incremental
transition optimizer.
