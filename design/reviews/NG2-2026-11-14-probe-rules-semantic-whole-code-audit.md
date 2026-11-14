# NG2 — ProbeRules semantic slice whole-code audit

**Дата:** 2026-11-14  
**Тип:** autonomous whole-slice audit  
**Scope:** LOCAL_PROCESS semantic contract, ICMP selector primitive, ProbeRulesCalculator

## Audit criteria

Проверены:

- неиспользуемые/дублирующие artifacts;
- соответствие EXP-021/022/023/024;
- отсутствие Linux uid/mark leakage в semantic model;
- dispatch ambiguity при нескольких probes;
- narrow ICMP admission;
- deterministic output independent of request ordering;
- accidental physical materialization before backend support;
- premature common RulesState abstraction.

## Findings

### S1 — exact ICMP message type was missing from common TrafficSelector

**Disposition:** fixed.

Protocol-only ICMP would be broader than the proven echo request/reply plane.

Added `IcmpType` to common NetworkRules selector semantics and production nft compiler.
Kernel syntax is covered by privileged `nft -c` integration.

### S2 — physical probe plane must not be keyed by logical probe_id

**Disposition:** fixed.

Different logical availability conditions may share one physical target/path/mechanism.
The calculator now deduplicates by:

```text
(mechanism, InterfaceIdentity, target)
```

and derives a stable selector-based routing-domain identity.

Reordering logical probes does not change resulting NetworkRules.

### S3 — same target through different interface generations is not ambiguous

**Disposition:** covered.

The full dispatch selector contains source class, target, bound output and protocol.
Primary/secondary probes to the same target therefore remain distinct.

### S4 — semantic model contains no Linux process identity

**Disposition:** PASS.

`LOCAL_PROCESS` has no uid/gid/cgroup/mark fields.

EXP-024's uid and conntrack mark are first-backend technical machinery only.

### S5 — concrete Linux backend was intentionally incomplete at this audit point

**Disposition:** historical gate now closed.

At the time of this semantic audit the Linux routing compiler rejected `LOCAL_PROCESS`
dispatch to prevent partial materialization.

EXP-024 subsequently passed on the Debian 13 target and a complete routing+nft
LOCAL_PROCESS backend was implemented and reviewed separately. The historical fail-closed
staging decision remains valid; the current backend status is documented in
`NG2-2026-11-14-linux-local-process-backend-review.md`.

### S6 — one unused compiler import appeared during ICMP selector work

**Disposition:** fixed.

`linux_nft.py` imported `IcmpType` but only consumes selector values generically.
The unused import was removed.

### S7 — ProbeRulesState was intentionally absent at this audit point

**Disposition:** historical gate now closed.

Physical LOCAL_PROCESS apply/renew observation now exists. `ProbeRulesStateCalculator`
was implemented from that evidence and reviewed independently.

The mandatory comparison with `PayloadRulesState` was completed afterward; the models
have different domain semantics, so no common `RulesState` was introduced.

## Current derived ICMP plane

For one unique physical probe:

```text
routing:
    target /32 -> exact InterfaceIdentity -> terminal fail-closed path

dispatch:
    LOCAL_PROCESS
    + ICMP
    + exact target
    + bound output InterfaceIdentity
        -> probe routing domain

traffic:
    LOCAL_PROCESS -> interface:
        exact target + ICMP echo-request

    interface -> LOCAL_PROCESS:
        exact source + ICMP echo-reply

flow initiation:
    LOCAL_PROCESS -> interface only

NAT:
    none
```

## Evidence

Green gates on this development line cover:

- common LOCAL_PROCESS semantic contract;
- multi-owner composition of same-target/different-path dispatch;
- exact ICMP selector unit behavior;
- production nft compiler ICMP selector syntax accepted by kernel;
- ProbeRules physical-plane deduplication and request-order invariance;
- explicit Linux backend rejection before materialization support;
- existing NG1 regression suite.

## Final verdict

**PASS.**

The pure ProbeRules semantic slice is coherent and does not require another abstraction.

The originally blocked Linux LOCAL_PROCESS unit and the subsequent ProbeRulesState/common-
state reviews are now complete. See the later focused reviews for current status.
