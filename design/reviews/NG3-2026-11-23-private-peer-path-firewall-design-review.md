# NG3 2026-11-23 — private-peer path firewall design review

**Scope:** requirement changes in `779a0e265168540ac30a1ceb6887a7a3a6099c80`
and the corresponding `architecture-ng.md` / `config-model.md` design through
`4396cedc1f8079a180b347bcc03d497878deb800`.

## Verdict

**PASS — IMPLEMENTATION GATE OPEN.**

The design is deliberately narrower than the previously researched configured-path-key
approach and is sufficient for the clarified user scope.

## Review findings

### F1 — product scope is represented without a universal path identity layer

**Decision:** accepted.

The re-entered requirement promises the one uncovered user case: a dynamic point-to-point
member whose exact interface is not known in advance and whose payload remote network may be
shared with another current member.

The scope constraint explicitly excludes a generic identity framework for WireGuard keys,
OpenVPN CN/session IDs, L2TP session IDs and external transport endpoints. This matches the
owner clarification that those known cases already have simpler interface/network selectors.

### F2 — `via peer` is a rule applicability predicate, not a new firewall dimension

**Decision:** accepted.

The selected grammar:

```text
<ordinary Device firewall rule> [via peer <IPv4>]
```

keeps one ordered Device firewall policy.

For a concrete current path:

- unqualified rules retain their original position and apply;
- a peer-qualified rule retains its original position only when the current path has the
  requested private peer;
- a peer-qualified rule for another peer is skipped;
- an explicit firewall still ends in terminal no-match DROP even when every explicit rule was
  skipped for that path.

This is materially simpler than composing separate Device-wide and path-specific policies and
preserves first-terminal-verdict semantics.

A qualified `allow` is safe under the same model: it can only produce an allow inside the
already restrictive Device policy for the selected path and still cannot create Profile
membership/destination/direction permission.

### F3 — private peer is correctly separated from transport endpoint provenance

**Decision:** accepted.

C.004 now distinguishes:

- current exact endpoint generation `(ifname, ifindex)`;
- optional private/inner P2P peer observed from interface address state;
- optional integration-specific external transport provenance.

EXP-039 proves the distinction: inner peer is visible in generic TUN address observation while
the userspace transport endpoint is not.

The new selector consumes only the first two facts. It does not resurrect external endpoint
provenance.

### F4 — ownership is not inferred from the peer value

**Decision:** accepted.

The path remains owned/selected by the existing Device binding projection. Peer comparison is
performed only after that projection. A matching peer on an unrelated host/private-network
interface cannot acquire Device ownership.

This avoids the VPN-type runtime manager rejected during re-entry review.

### F5 — unknown and absent remain distinct

**Decision:** accepted.

When peer observation is requested:

- confirmed no private peer on a current endpoint is a known non-match;
- a requested peer with no current matching path selects no path at that moment;
- duplicate matching peers are ambiguous;
- command/parse/snapshot-coherence failure is observation failure.

Ambiguity/failure cannot be converted into "rule does not apply" when that conclusion could
widen traffic. Existing structural fail-closed handling remains applicable.

### F6 — additional observation is demand-scoped

**Decision:** accepted.

No `via peer` in accepted Device rules means the old link-only endpoint observation remains
sufficient. Peer/address discovery is not made a new prerequisite for WG or other ordinary
Device paths.

This is an important non-regression boundary and prevents the narrow capability from
expanding the failure surface of unrelated configurations.

### F7 — component allocation is consistent with the component model

**Decision:** accepted.

- A.002 normalizes the human grammar and distinguishes private peer from payload/transport
  endpoint semantics.
- A.005 owns the semantic rule applicability field and keeps Device policy restrictive.
- C.004 provides fresh generation-scoped optional inner-peer observation.
- C.001 lowers the already normalized ordered rule stream per exact current path.
- existing C.003 convergence remains responsible for desired-state application/verification.

No new Manager, Agent, generic VPN Backend, durable path registry or session manager is
justified.

### F8 — historical evidence is sufficient for implementation entry

**Decision:** accepted.

EXP-004.3, EXP-009 and EXP-039 already establish the material platform facts:

- dynamic ocserv interface-family naming;
- simultaneous OpenConnect P2P interfaces with distinct inner peers;
- historical peer-to-exact-interface association;
- generic visibility of inner peer;
- non-equivalence of inner peer and external transport endpoint.

No new live VPN experiment is required before implementing the semantic/config/observation
pipeline. Permanent unit tests plus a disposable Linux namespace integration test are the
cheapest sufficient implementation evidence.

## Implementation acceptance boundary

Implementation must cover at least:

1. strict parse/normalization of optional `via peer <IPv4>`;
2. normalized rule intent carrying the optional private peer;
3. demand-scoped fresh address observation correlated to exact link generation;
4. confirmed-none versus observation-failure distinction;
5. duplicate/private-peer ambiguity rejection;
6. per-current-path ordered rule filtering with unchanged explicit terminal DROP;
7. startup/reconciliation wiring so peer facts are requested only when configured;
8. regression tests proving configurations without `via peer` retain the existing path.

After these pass and implementation review is clean, the four re-entered/changed requirement
nodes may be closed against the accepted architecture and evidence.
