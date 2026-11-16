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

### S5 — concrete Linux backend must remain explicitly incomplete

**Disposition:** retained with regression.

The Linux routing compiler rejects `LOCAL_PROCESS` dispatch.

This prevents the new semantic model from becoming a partially implemented probe plane
whose firewall/routing semantics differ from EXP-024.

### S6 — one unused compiler import appeared during ICMP selector work

**Disposition:** fixed.

`linux_nft.py` imported `IcmpType` but only consumes selector values generically.
The unused import was removed.

### S7 — ProbeRulesState is still intentionally absent

**Disposition:** retained.

Without physical LOCAL_PROCESS apply/renew observation there is no evidence-based
`ProbeRulesStateCalculator`.

The mandatory comparison with `PayloadRulesState` remains pending and must happen only
after the second real state model exists.

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

Next blocked implementation unit is the Linux LOCAL_PROCESS physical backend. Its design is
known from EXP-024, but target evidence on Debian 13 remains required before that unit is
declared production-proven.
