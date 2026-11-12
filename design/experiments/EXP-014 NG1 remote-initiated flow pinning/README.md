# EXP-014 — NG1 remote-initiated flow pinning

**Status:** PREPARED — future extension gate  
**Architecture baseline:** NG1 Draft 5 after 2026-11-12 correction review  
**Type:** conntrack/connmark + RPDB fwmark return-steering experiment

## Purpose

Schema version 1 deliberately limits INBOUND/BIDIRECTIONAL Profiles to active interface
capacity 1. EXP-014 gates any future relaxation to capacity > 1.

The experiment must prove that a remote-initiated flow admitted through one concrete bound
interface returns through that same interface even when another Device/interface has a
lower normal metric.

## Required topology

- one ROU namespace with host0;
- at least two simultaneously bound tunnel-like interfaces A and B;
- one remote prefix reachable through both;
- one host-side responder behind host0;
- rp_filter disabled as in production;
- destination dispatch that would normally prefer A;
- inbound test flow deliberately initiated through B.

## Hypotheses

H1. NEW on Device interface B can set a connection mark M(B).

H2. For the host reply entering on host0, connmark can be restored in a pre-routing hook
before the RPDB routing decision.

H3. An RPDB fwmark rule can select a B-specific return table before ordinary Profile
destination dispatch.

H4. If B disappears while a flow retains M(B), that mark resolves to explicit fail-close
(blackhole/unreachable) and never falls through to ordinary destination dispatch through A.

H5. Mark retirement/reuse policy can prevent an old conntrack entry from selecting a newly
bound unrelated interface generation.

H6. Required conntrack cleanup on unbind is understood and deterministic.

## Evidence required

- iptables/nftables mangle/connmark rules before and after;
- `ip rule` / return tables;
- packet captures on host0, A and B for request/reply;
- conntrack state including marks;
- interface disappearance while a marked flow exists;
- same-name/new-ifindex replacement;
- explicit proof that retired marks fail closed.

## Gate

No production code may admit INBOUND/BIDIRECTIONAL capacity > 1 until EXP-014 is PASS and
the architecture is updated. Schema-v1 capacity-one behavior is production-complete and
does not depend on this experiment.
