# NG3 2026-11-23 — Device firewall path-selector design review

**Scope:** architecture/configuration correction from peer-only path selection to the accepted
three-scope Device firewall model.

## Verdict

**PASS — THE EXISTING COMPONENT ALLOCATION REMAINS SUFFICIENT. EXACT-IF IS A PURE
CURRENT-PATH APPLICABILITY PREDICATE; PRIVATE-PEER RETAINS ITS EXISTING DEMAND-SCOPED
OBSERVATION.**

No new Engine, path registry or VPN-specific integration machinery is required.

## Findings and dispositions

### F1 — one ordered Device policy remains the correct semantic owner

**Decision:** accepted.

The design keeps one ordered Device firewall. For each current path, the same ordered rule
stream is projected by rule applicability:

```text
no selector          -> applicable
via if X             -> applicable iff current path.ifname == X
via peer P           -> applicable iff verified current path.private_peer == P
```

Rules that do not apply are skipped without reordering the survivors. Explicit Device policy
still has terminal no-match DROP even when all explicit rules are skipped for one path.

### F2 — exact-if does not need a new observation contract

**Decision:** accepted.

C.004 already establishes exact current `InterfaceIdentity(ifname, ifindex)` for each
current Device path. `via if <exact-ifname>` compares only against that already accepted
binding.

It therefore:

- cannot select an unrelated interface outside the Device;
- does not require an address/peer snapshot;
- does not create durable ifindex identity;
- does not change Device binding semantics.

### F3 — private-peer remains the only selector with additional runtime evidence

**Decision:** accepted.

`via peer <IPv4>` continues to require fresh generation-correlated private-peer observation
for current Device paths. The previously reviewed fail-closed behavior remains unchanged:
observation failure or duplicate matching peers cannot be treated as proof that the
restriction is absent.

Configurations containing only unqualified and/or `via if` rules retain link-only endpoint
observation.

### F4 — selector alternatives are intentionally mutually exclusive

**Decision:** accepted.

The grammar has one optional `via` clause whose mode is either `if` or `peer`. No
meaning is assigned to `if AND peer`, `if OR peer` or repeated `via` clauses.

This is a deliberate product-scope bound, not an implementation limitation.

### F5 — existing lower firewall realization is unchanged

**Decision:** accepted.

After applicability projection, C.001 continues to materialize the existing exact current
interface-pair chains. Neither selector becomes an nft payload predicate.

Therefore no new nft/kernel feasibility experiment is required for `via if`. Existing
private-peer integration evidence remains sufficient for `via peer`.

## Implementation acceptance boundary

Implementation must add:

1. strict `via if <exact-ifname>` parsing and Linux-ifname validation;
2. normalized exact-if selector field with invariant that it cannot coexist with private-peer;
3. exact-if applicability in per-path Device firewall compilation;
4. preservation of peer-observation demand only for actual `via peer` rules;
5. tests for Device-wide, exact-if and private-peer scopes in one ordered policy;
6. rejection of malformed/repeated/mixed `via` forms;
7. regression evidence that peer-only and unqualified behavior is unchanged.

After implementation evidence and a clean review, the broadened requirement nodes may return
to `closed`.
