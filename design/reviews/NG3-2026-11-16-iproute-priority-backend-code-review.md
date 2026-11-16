# VPN-GATE NG3 — Physical iproute2 Priority Backend Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Implementation/fix commits reviewed:**  
- `f3748c1b2c7f3f34547284ead43c40c8587a251f`
- `f5904085e6d296292f9505de1e244c84b4a6adc1`
- `657b1dbedcf8fec8f9720f8ba654560e52532f0a`

## Scope

This unit implements the first real Linux mutation boundary for the accepted
NetworkPolicyExecutor pure-priority path.

The backend is deliberately scoped to one route-key convergence domain inside the managed
network namespace.

It provides:

- authoritative route observation from iproute2 JSON;
- relevant interface-identity stability checks around each route dump;
- exact physical add/delete command construction;
- make-before-break `RoutePriorityMove` realization;
- exact duplicate-route cleanup;
- fresh verification before and after every semantic mutation.

It does **not** implement structural policy mutation, RPDB/nft ownership, Profile-wide
multi-domain orchestration or daemon lifecycle.

## Requirement / architecture gate

Relevant accepted nodes:

- `VPNG0003-R3.R2`, `R3.R3`, `R3.R4`;
- `VPNG0004-R4.R2`, `R4.R3`, `R4.R3.R1`, `R4.R5`;
- `VPNG0005-R5.R2`, `R5.R3`;
- `VPNG0007-R7.R3`, `R7.R3.R1`, `R7.R5`.

The physical-domain design review already established that one convergence attempt must
operate on one independently observable route key.

No new product semantics were introduced.

## Accepted physical behavior

For one semantic `RoutePriorityMove(path, old, new)`, the backend now performs:

```text
fresh whole-domain observation
  -> require one current metric per path and free new metric
  -> exact ip route add new
  -> fresh whole-domain observation
  -> require exact expected add-before-delete state
  -> exact ip route del old
  -> fresh whole-domain observation
  -> require exact expected final state
```

The route observation itself is:

```text
ip link snapshot A
  -> protocol-filtered route dump
  -> ip link snapshot B
  -> require every relevant bound interface identity unchanged
  -> normalize route-key snapshot
```

Thus a same-name interface replacement during observation cannot silently be attributed to
the old logical path under the accepted `(ifname, ifindex)` identity model.

## Finding F1 — verification initially checked only the moved path

**Severity:** material race / authoritative-state defect  
**Disposition:** accepted and fixed in `f5904085`

The initial backend verified that the moved path had the expected duplicate/final metrics,
but it did not require unrelated paths in the same route-key domain to remain unchanged
between observations.

An external drift on another path could therefore occur after add-new and remain unnoticed
until later.

The fix makes every semantic verification compare the **entire route-key snapshot** against
the exact expected state.

It also:

- rejects cross-path metric ownership collisions;
- requires one metric per path before a normal semantic move;
- preserves duplicate tolerance only for explicit recovery/cleanup;
- verifies duplicate deletion against the whole domain, not only the target path.

This is consistent with the architecture rule that stale current state must not justify
continued mutation.

## Finding F2 — unit regression after stricter error wording

**Severity:** test-only  
**Disposition:** fixed in `657b1dbe`

The stricter whole-domain check changed the expected error message for one negative test.
The code behavior was correct; only the old assertion string was stale.

## Evidence

Final GitHub Actions run:

```text
workflow: NG3 Python
run:      43819982621
commit:   657b1dbedcf8fec8f9720f8ba654560e52532f0a
unit:     137 tests, OK
linux-route-priority: PASS
overall:  success
```

The privileged integration creates a disposable network namespace and real dummy path
interfaces, then proves:

- authoritative owned-route observation;
- real iproute2 make-before-break priority swap;
- final verified desired metrics;
- recovery from an already materialized duplicate route state without stale-plan replay.

This is stronger evidence than the rootless mocks for the Linux behavior that the unit
claims.

## Complexity / safety review

PASS.

The physical backend does not add a journal, retry queue or replay log.

Recovery remains current-state based.

Command execution uses argv sequences rather than shell strings.

Internal route table/protocol identifiers remain constructor inputs below the user-facing
configuration model and are not promoted to product policy.

## Residual boundary

The next material implementation boundary is Profile-level orchestration across all affected
route-key domains and then the guarded structural-policy path.

Other still-open implementation areas include:

- RPDB/nft materialization;
- Device NAT/envelope/publication;
- ICMP probe execution;
- full lifecycle/deployment assembly.

## Final verdict

**PASS AFTER FIX.**

The bounded pure-priority Linux route-key Executor is accepted with both deterministic unit
evidence and real privileged namespace evidence.
