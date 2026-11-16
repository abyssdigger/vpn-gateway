# NG2 — Linux NetworkRulesAdapter review

**Дата:** 2026-11-14  
**Тип:** autonomous focused implementation review  
**Scope:** concrete Linux lower domain behind NetworkRulesAdapter

## Review criteria

Проверялись:

- соответствие публичному NetworkRulesAdapter contract;
- owner isolation при общем physical backend;
- transactional commit semantics;
- fail-close routing/filtering/NAT behavior;
- generation-aware interface identity;
- exact fresh verification;
- restart ownership evidence;
- consistency with EXP-012 and EXP-017;
- live kernel behavior and payload dataplane semantics;
- component-model boundary Adapter / Driver / pure lower-domain compilation.

## Findings

### L1 — terminal host-ingress RPDB fail-close was missing

**Severity:** safety  
**Disposition:** fixed.

Первая NG2 routing projection устанавливала per-domain terminal blackhole, но не
восстановила подтвержденный NG1/EXP-012 terminal RPDB guard после всех Profile dispatch
rules.

Без него повреждение filtering layer могло позволить unmatched host-ingress traffic
провалиться в namespace main table.

Current invariant for any non-empty owner set:

    owned dispatch rules
    then
    iif <local-interface> -> unreachable

Full cleanup removes the terminal rule.

### L2 — sequential multi-owner same-name/new-ifindex transition could deadlock

**Severity:** correctness / availability  
**Disposition:** fixed.

Если два owners ссылались на одну generation, после recreation интерфейса обычные
последовательные RequestEvents временно создавали composition:

    owner A -> fresh (name,new-ifindex)
    owner B -> stale (same-name,old-ifindex)

Такая exact global desired projection физически невыполнима.

Fix: перед Linux compilation Adapter берет stable fresh interface inventory и строит
fail-closed realisable projection каждого owner:

- absent path removed;
- domain/destination/terminal preserved;
- absent-endpoint filter/flow/NAT permissions removed;
- LOCAL_NETWORK dispatch retained.

Requested owner получает SUCCESS только если его projection полностью равна requested
spec. Другие owners могут одновременно быть freshly KNOWN как conservative divergent
subsets и затем догоняют generation обычным своим apply().

Live integration proves sequential two-owner convergence and per-owner cleanup.

### L3 — RPDB /0 observation was ambiguous

**Severity:** correctness  
**Disposition:** fixed.

Kernel/iproute JSON may serialize a lookup of 0.0.0.0/0 as all/omitted destination.
Terminal unreachable rule likewise has no destination.

Parser now uses action context:

- lookup/to_tbl without explicit dst -> IPv4 0.0.0.0/0;
- terminal unreachable without dst -> no destination.

Live integration verifies a real /0 owner where one table contains both normal unicast
default and terminal blackhole default.

### L4 — foreign nft tables were outside verification scope

**Severity:** safety  
**Disposition:** fixed.

Exact verification of only vpng2_filter/vpng2_nat was insufficient in the dedicated ROU
namespace: foreign prerouting/NAT/filter tables can alter packet semantics before or around
owned policy.

Current first-safe-backend invariant:

- the dedicated ROU namespace is an exclusive network-policy domain;
- nft table inventory must equal the candidate owned table set exactly;
- structural repair removes foreign nft tables while forwarding is closed;
- final exact verification rejects unexpected tables.

Live integration injects table inet foreign_ci, proves drift detection, then proves
barriered repair removes it.

### L5 — cross-owner NEW flow permissions must preserve provenance

**Severity:** safety  
**Disposition:** fixed in initial compiler.

Global:

    union(traffic_allows) AND union(flow_initiation_allows)

is unsafe because traffic permission from one owner and flow permission from another can
synthesize a NEW flow neither owner requested.

Compiler instead realizes:

    OR over owners of
        traffic_allow(owner) AND flow_initiation_allow(owner)

Established/related byte permissions remain the positive union of owner traffic policy.

Live dataplane confirms OUTBOUND blocks remote NEW and reverse flow-initiation permission
opens it only after explicit policy change.

### L6 — owner identity registration and committed rules generation are different states

**Severity:** architecture / transactionality  
**Disposition:** fixed.

First failed apply must still support getLastState(owner) and cleanup(owner), so owner
identity/token may exist before any successful materialization.

Candidate rules and routing allocation, however, commit only after verified physical
SUCCESS.

Consequences:

- failed first apply -> registered owner, no committed rules, UNKNOWN state;
- failed replacement -> previous committed generation remains;
- failed cleanup -> owner remains committed;
- shared mutation failure -> all registered owners become UNKNOWN until fresh observation.

### L7 — exact nft verification needs policy plus generation markers

**Severity:** safety  
**Disposition:** implemented.

EXP-017 showed nft can display a numeric live interface reference by name.

Verification therefore checks both:

1. complete normalized table policy;
2. exact rule-marker multiset carrying owner and numeric ifindex generation.

Neither check alone is authoritative.

### L8 — routing ownership survives process-history loss sufficiently for structural repair

**Severity:** lifecycle  
**Disposition:** implemented for structural baseline.

Protocols 201/202 tag owned terminal/unicast routes.

Structural observation discovers tagged tables even outside in-memory allocator history.
Those tables are included in cleanup/rebuild scope.

A tagged owned route in a reserved routing table is fatal and is never flushed blindly.

Persistent table-allocation state across daemon restart is not yet implemented; the
structural path does not depend on it to discover stale tagged route state.

### L9 — Driver failure must close forwarding, not guess rollback

**Severity:** safety  
**Disposition:** implemented.

Structural materialization:

1. closes forwarding;
2. rebuilds owned routing/RPDB/nft state;
3. exact-verifies while closed;
4. opens forwarding only if effective traffic policy requires it;
5. exact-verifies final state.

Any exception after mutation starts causes best-effort ip_forward=0 and FAILURE.

No speculative rollback to a presumed prior kernel snapshot is attempted.

### L10 — live kernel and dataplane evidence required before PASS

**Severity:** evidence  
**Disposition:** satisfied.

The NG2 workflow now runs disposable privileged namespace gates against real iproute2,
nftables, conntrack and IPv4 forwarding.

Structural gate covers:

- initial apply and exact renew;
- terminal RPDB guard;
- same-name/new-ifindex drift;
- sequential multi-owner generation transition;
- route drift repair behind forwarding barrier;
- foreign nft drift repair;
- /0 routing domain;
- per-owner cleanup preserving survivor;
- final physical cleanup.

Dataplane gate covers:

- local-initiated NEW;
- return ESTABLISHED traffic;
- blocked remote-initiated NEW under OUTBOUND policy;
- explicit reverse flow-initiation enablement;
- semantic EGRESS_ADDRESS source NAT / MASQUERADE;
- forwarding closure after cleanup.

## Component-model review

Current lower-domain graph:

    LinuxNetworkRulesAdapter
        -> owner composition / semantic projection
        -> Linux desired-state compilers
        -> LinuxNetworkDriver
            -> iproute2 / nft / sysctl

NetworkRulesAdapter remains the Direct Adapter boundary visible to upper domains.

LinuxNetworkDriver is the direct technical boundary.

Composition/allocation/filter/NAT/verification helpers are synchronous lower-domain
calculations, not Engines and not participants in event space.

No Linux table ID, RPDB priority, route metric, nft syntax, conntrack realization or
barrier phase escapes through NetworkRulesSpec or PayloadTrafficManager.

## Non-blocking lifecycle requirement

The current Adapter unit assumes a dedicated ROU namespace and proves fail-close behavior
from the first Adapter operation onward.

Runtime/bootstrap assembly must additionally ensure that forwarding is protectively closed
before the first owner request after daemon/process startup, so stale physical state cannot
forward during the interval before the first reconcile.

This is a bootstrap/lifecycle integration requirement, not a defect in the
NetworkRulesAdapter owner contract.

## Deferred work

Not required for this baseline:

- incremental transition optimizer;
- richer interface-origin dispatch;
- persistent allocation across daemon restart;
- non-Linux backend;
- runtime/bootstrap assembly;
- RuntimeStateManager Profile-state mapping.

## Evidence

Latest NG2 workflow after foreign-nft repair:

- rootless unit suite: PASS;
- privileged structural Linux integration: PASS;
- privileged live payload dataplane/NAT integration: PASS.

NG1 validation remains green on the same development line.

## Final verdict

**PASS.**

No unresolved finding blocks the concrete structural Linux NetworkRulesAdapter baseline.

Next review scope should be a whole lower-domain code audit before any incremental
transition optimization.
