# NG3 2026-11-23 — Device firewall path-scope clarification review

**Scope:** owner clarification after completion of the peer-only per-path firewall block.

**Supersedes only the product-scope conclusion** of
`NG3-2026-11-23-private-peer-path-restriction-reentry-review.md` and the corresponding
peer-only design/implementation closure. The historical evidence and implementation facts in
those reviews remain valid.

## Verdict

**ACCEPTED — DEVICE FIREWALL RULES HAVE THREE USER-VISIBLE SCOPES: DEVICE-WIDE,
EXACT CURRENT INTERFACE, OR PRIVATE/INNER P2P PEER.**

The existing peer-only implementation is a valid subset but is no longer sufficient for the
accepted product scope.

## Findings and dispositions

### F1 — firewall ownership remains Device-wide, not Profile-wide

**Decision:** accepted.

The firewall continues to belong to Device policy. Profile-specific copies of the same
firewall grammar are not introduced.

Current product need does not justify different firewall rules for the same Device path merely
because that path is used by different Profiles. Adding Profile-local firewall would multiply
configuration and policy-composition semantics without a demonstrated user case.

Effective permission therefore remains:

```text
Profile permission
AND
ordered Device firewall verdict for the current Device/path
```

### F2 — a rule may be unqualified or path-qualified in exactly one way

**Decision:** accepted.

One ordered Device firewall rule has exactly one of these scopes:

```text
no path selector
    -> every current path of the Device

via if <exact-ifname>
    -> only the current path of this Device realized by that exact interface name

via peer <private-IPv4>
    -> only the current point-to-point path of this Device whose observed
       private/inner peer IPv4 equals the operand
```

`via if` and `via peer` are mutually exclusive. The current product has no accepted
use case for conjunction/disjunction of path selectors inside one rule, so the grammar must
not invent such semantics.

### F3 — exact-if selection is not host-wide interface policy

**Decision:** accepted.

`via if <exact-ifname>` is evaluated only against current paths already owned by the Device.
A same-named interface outside that Device cannot make the rule applicable and the selector
does not turn Device firewall into a generic host firewall.

This is a direct rule-applicability predicate over the already selected concrete Device path;
it requires no additional runtime observation beyond the existing exact
`InterfaceIdentity(ifname, ifindex)` binding.

### F4 — private-peer selection is the dynamic counterpart of exact-if selection

**Decision:** accepted.

`via peer <IPv4>` remains the narrow solution for the case where the exact runtime
interface name cannot be known in advance, especially a dynamic point-to-point interface
family with overlapping remote payload address space.

Resolution remains:

```text
current Device paths
    -> fresh private-peer observation for their exact interface generations
    -> unique requested peer match
    -> selected current exact path
```

The operand is the private/inner point-to-point peer, not an external VPN transport/server
endpoint and not a payload packet address predicate.

### F5 — the previous archaeology still supplies the necessary evidence

**Decision:** accepted.

EXP-004.3 and EXP-009 remain directly relevant:

- dynamic OpenConnect/ocserv interface-family members exist;
- exact concrete interfaces are the lower enforcement units;
- point-to-point peer evidence can associate a configured private peer with one current exact
  interface;
- the historical removal of `PeerBinding` was a routing-model simplification, not a
  disproof of that association.

The exact-if scope needs no new platform experiment. The private-peer scope continues to rely
on the already accepted historical + EXP-039 evidence and the current Linux integration test.

### F6 — the peer-only closure must be reopened, not rewritten away

**Decision:** accepted.

The peer-only implementation/review was correct for its then-accepted scope. The owner
clarification expands that scope after closure.

Therefore:

- retain the existing commits/reviews as historical development evidence;
- change the affected requirement semantics and return them to `open`;
- extend architecture/config/code/tests with exact-if selection;
- perform a new review and only then close the broadened nodes again.

No history rewrite or retrospective falsification of the peer-only review is appropriate.

## Required correction

The next normative change must express one optional path selector on a Device firewall rule:

```text
[via if <exact-ifname> | via peer <IPv4>]
```

with these invariants:

1. omission means Device-wide rule applicability;
2. `via if` and `via peer` are mutually exclusive;
3. both selectors are Device-scoped;
4. exact-if uses the already current exact Device path;
5. peer uses fresh generation-correlated private-peer observation;
6. rule order and terminal no-match DROP semantics remain unchanged;
7. no Profile-local firewall and no generic VPN-specific path-identity framework are added.
