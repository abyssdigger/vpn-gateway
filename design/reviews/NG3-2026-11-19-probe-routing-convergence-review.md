# NG3 2026-11-19 — probe route/RPDB convergence review

## Verdict

**PASS — probe-owned route/RPDB state now has bounded fail-closed convergence.**

## Scope

This unit closes the missing coordinator between already existing:

- probe route/RPDB desired state;
- whole-reserved route/RPDB observation;
- probe-owner actual-vs-desired comparison;
- EXP-065-backed exact Linux mutation Driver.

It does not execute ICMP, derive omitted targets, own confirmation hysteresis or modify
payload route order.

## Safety invariant

A probe RPDB selector may point only at an exact current probe table.

If route contents drift while a currently correct selector is installed, the selector is
temporarily withdrawn before any table repair. This is intentional fail-closed behavior.

The safe mutation order is:

```text
selector into drifted table -> withdraw
other stale selector         -> withdraw
missing terminal guard       -> add
stale path route             -> delete
stale terminal guard         -> delete
missing path route           -> add
missing desired selector     -> add last
```

The selector is therefore never installed while the corresponding dedicated probe table is
incomplete.

## Safety rank

Simple object-count distance is insufficient because withdrawing a semantically desired
selector intentionally creates one missing desired rule.

The new lexicographic rank is:

```text
(
    installed selectors pointing into drifted probe tables,
    route differences,
    stale selectors,
    missing selectors,
)
```

Withdrawing an active selector from a drifted table strictly decreases the first component,
even though the final component may increase by one.

Every successful one-step mutation must expose a strictly lower fresh rank.

## Bounded transaction

`probe_routing_convergence.py` provides:

- link-identity-bearing physical snapshots;
- one-step fresh observe/apply/re-observe convergence;
- strict rank-progress validation;
- apply-error + independently observed progress handling;
- conflict/postcondition failure termination;
- bounded multi-step convergence with inter-attempt regression detection.

There is no retry-on-error budget or hidden recovery loop.

## Linux observation

`LinuxProbeRoutingBackend` now owns a link-bracketed route/RPDB observation:

```text
links before
    -> ip -j -N -4 route show table all
    -> ip -j -N -4 rule show
links after
```

If link identity changes inside the observation bracket, observation fails instead of
silently accepting a same-name replacement generation.

The shared authoritative structural route/RPDB parser is reused; no second Linux inventory
format is introduced.

## Regression coverage

New tests cover:

- empty state builds terminal guard before path route before selector;
- a correct active selector is withdrawn before repairing a drifted table;
- the withdrawal strictly improves safety rank despite creating a missing desired rule;
- stale selectors are withdrawn before table mutation;
- stale path routes are removed before stale guards;
- desired selectors are added only after route contents are exact;
- exact state performs no write;
- complete in-memory convergence from empty state;
- drifted path + current selector converges as:
  `delete rule -> delete stale path -> add current path -> add rule`;
- interface-generation change between pre/post observations fails the postcondition;
- reserved probe conflict terminates without mutation.

## Verification

Current code-bearing GitHub Actions run:

```text
run: 44473201586
head: 315b7639e4f728dbeab31b9d5a707a2cfd258775

unit: PASS — 784 tests
linux-probe-runtime: PASS
linux-structural-inventory-shape: PASS
```

The known unrelated privileged failures in EXP-057/060 remain outside this unit.

## Requirement / architecture integrity

No normative Requirement or Constraint changed.

The current preliminary runtime-diagnostic declaration was refined at the beginning of this
cycle, and external Profile network-file sourcing remains explicitly deferred until after the
first release together with managed Device/VPN lifecycle work.

## Requirement-state inventory

No active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

## Next boundary

For an explicit concrete probe target, lower route/RPDB and local nft preconditions can now
both be converged safely.

The next autonomous unit is explicit-target attempt orchestration:

```text
normalized probe intent
    -> converge probe route/RPDB
    -> confirm probe-local nft owner exact
    -> begin current Agent context
    -> execute one-shot ICMP Driver
    -> reject late result if context changed
    -> emit current AvailabilityOutcome
```

Confirmation/hysteresis and effective route-order feedback remain separate bounded steps after
that orchestration seam.

## Conclusion

Probe route/RPDB policy is no longer merely materializable. It now has a fail-closed,
fresh-observation, strictly progressing bounded transaction suitable for use as a real probe
attempt precondition.
