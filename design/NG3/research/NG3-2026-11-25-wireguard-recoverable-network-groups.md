# NG3 WireGuard recoverable-network groups — 2026-11-25

## Question

The current D.002 model assigns one complete shared payload-prefix set to one selected
WireGuard peer. Can the same managed `wg0` instead recover independent bundles of remote
networks through different peers, while preserving the current one-bundle behavior as the
degenerate case?

## Evidence already available

The existing production/evidence boundary already separates two facts:

- each managed peer has a permanent unique in-tunnel `probe_target /32`; D.002 can therefore
  obtain peer-specific technical reachability without knowing or probing the peer's public
  transport endpoint;
- D.003 converges and fresh-confirms one exact complete `AllowedIPs` state for all managed
  peers and does not itself choose an owner.

EV-00050/EV-00100 and the current D.003 implementation establish that mutable payload
`AllowedIPs` can move between peers without restarting the common WireGuard interface while
each peer retains its permanent probe `/32`.

The existing Profile availability policy also already establishes the desired preference rule:
ordinary active membership is sticky, while an explicitly `:reserve` active membership may
be preempted when a more-preferred usable ordinary candidate recovers.

## Selected semantic model

### 1. Peer health and remote-network health are different evidence

D.002 needs two independent evidence dimensions.

**Peer health** is technical evidence for one peer:

```text
(device, peer, current base/interface context)
    -> ICMP peer.probe_target /32
    -> reply | no_reply | local_error
```

It answers only whether the WireGuard path to that peer is currently technically usable. It
does not prove reachability of every payload network behind that peer.

**Recoverable-network-group health** is optional end-to-end evidence for one payload bundle
through its current owner:

```text
(device, group, current owner/generation)
    -> optional group endpoint
    -> reply | no_reply | local_error
```

A peer may therefore remain technically reachable while one recoverable group behind it is
unreachable.

As elsewhere in NG3, `local_error` is observation failure, not negative health evidence, and
must not be converted into failover evidence.

### 2. The mutable ownership unit is a recoverable-network group

A recoverable-network group is a semantic bundle of payload prefixes that always moves as one
unit between its allowed peers. D.002 current state generalizes from:

```text
selected_peer = peer-a
```

to:

```text
group-a -> peer-a
group-b -> peer-b
...
```

D.003 still receives one complete exact peer -> AllowedIPs projection. It does not need
group-selection policy: D.002 expands the current group ownership map into the complete
per-peer set and D.003 only converges/fresh-confirms that state.

A payload prefix must not simultaneously belong to two effective recoverable groups whose
ownership can diverge. Configuration normalization must reject ambiguous overlapping ownership
unless a later requirement defines an explicit deterministic nesting rule; this research does
not introduce such a rule.

### 3. Peer failure and group failure cause different recovery scopes

If the current owner peer is confirmed technically unavailable, every group currently owned by
that peer is independently eligible for recovery to another allowed technically available
peer. A group does **not** require an individual end-to-end endpoint for this peer-failure
recovery.

If the current peer remains technically available but a configured group endpoint is confirmed
unavailable through it, only that group is eligible for recovery.

Therefore absence of a group endpoint does not make the group non-recoverable. It only means
that D.002 has no finer health signal than peer health for that group.

### 4. Candidate validation is a bounded ownership trial

Peer health can reject an obviously unusable candidate before changing payload ownership, but
it cannot prove that a particular remote-network group works through that candidate.

For a group with an endpoint, the bounded recovery sequence is therefore:

```text
current group owner confirmed unsuitable
    -> choose next allowed peer with fresh positive peer evidence
    -> D.003 fresh-confirm exact ownership transfer for this group
    -> probe group endpoint through the new owner
       -> reply: confirm group owner/generation
       -> no_reply: candidate is unsuitable for this group; try next candidate
       -> local_error: stop failover decision as unconfirmed/problem
```

This deliberately does not invent a pre-switch candidate-group probe path. Such a mechanism
would itself require temporary/special `AllowedIPs` ownership for the group endpoint and a
new transition contract. The simpler ownership-trial sequence is sufficient for the accepted
scenario and starts only after the prior group realization has already been confirmed
unsuitable.

For a group without an endpoint, fresh positive peer evidence plus confirmed D.003 ownership
is sufficient to confirm the ownership realization, but it is **not** end-to-end evidence that
the remote payload network itself is reachable.

### 5. One implicit/explicit full group degenerates to the current D.002 behavior

If all mutable shared payload prefixes form one recoverable group, all managed peers are
candidates for it, and the group has no individual endpoint, then:

```text
peer-a no_reply
peer-b reply
    -> transfer the complete shared prefix set peer-a -> peer-b
```

This is semantically the current one-owner D.002 model. The generalized model therefore does
not need a separate legacy runtime mode merely to preserve today's behavior.

Because no binding release exists yet, the eventual canonical configuration spelling may be
redesigned directly around the generalized model rather than carrying transitional aliases
solely for pre-binding config forms.

### 6. Preference/failback reuses the Profile reserve semantics

Do not add an independent `sticky=true` switch.

For each recoverable group, candidate peer memberships have baseline order and a local
ordinary/reserve role:

- ordinary current owner is sticky while it remains suitable;
- a recovered more-preferred ordinary peer returns to standby baseline position but does not
  preempt another suitable ordinary owner;
- if the current owner membership is `reserve`, a more-preferred usable ordinary candidate
  may trigger failback;
- reserve is a **membership role of the peer inside this group**, not a global property of the
  peer.

This is the same policy shape already accepted for `Profile.device_order`. The normalized
configuration model should reuse one small ordered-membership/reserve representation if doing
so remains type-safe, but Profile and recoverable-network-group remain distinct semantic
owners because their candidates and data-plane effects differ.

### 7. Probe-plane reuse extends by semantic owner, not by collapsing evidence

Peer probes already have `WireGuardPeerProbeOwner`. A group endpoint probe should be a
separate semantic owner (conceptually `WireGuardGroupProbeOwner(device_id, group_id)`) even
when its physical ICMP rule/route can be shared with an A.007 Profile probe or another accepted
owner.

The previously selected shared C.001 design still applies:

- all accepted probe owners participate in one full physical convergence union;
- one fresh physical snapshot is authoritative;
- readiness is projected separately per requested semantic owner subset;
- sibling accepted state is not stale;
- unattributed state in the reserved probe ownership boundary remains fail-closed.

Adding group probes therefore strengthens the need for the already planned owner-scoped
readiness implementation; it does not invalidate that design.

### 8. Generations and stale evidence

At minimum D.002 needs:

- current D.001 base generation;
- current interface identity/generation;
- current peer-definition/probe context;
- current normalized recoverable-group definitions and candidate policy;
- current confirmed group -> peer ownership map.

A change of confirmed group ownership must produce fresh D.002 realization evidence only after
D.003 confirms the exact new `AllowedIPs` state and, when configured, the group endpoint
check confirms the candidate.

A first implementation may conservatively change one Device-wide D.002 generation whenever
any group ownership changes. This safely invalidates dependent A.007 evidence but may cause
extra Profile re-probing. A later optimization may use group-scoped generations only if the
mapping from a Profile availability subject to the relevant group/owner context is explicit
and mechanically safe.

No evidence obtained for a previous group owner may remain authoritative merely because
`LogicalPathId`, `wg0` and ifindex did not change.

## Configuration implications

The current config derives one complete shared prefix set from all enabled Profile
`destinations` that reference the managed WireGuard Device. That is insufficient for
independent group ownership and must be redesigned before D.002 is generalized in code.

The product semantics require, regardless of final TOML spelling:

- stable group identity;
- a non-empty prefix bundle;
- an ordered set/subset of allowed peer memberships;
- ordinary/reserve role local to each group membership;
- optional explicit group availability endpoint;
- no ambiguous effective payload-prefix ownership;
- peer definitions retaining permanent unique technical `probe_target /32` values.

The exact user-facing spelling is intentionally not selected by this research. A promising
direction is to factor the existing Profile `device_order` and future group peer order through
one normalized ordered-membership policy shape while keeping their candidate types distinct.

The existing config heading “Обратная совместимость” for externally managed Device behavior
must also be renamed when this section is edited: after `VPNG-M001-R4*`, that phrase now has
a project-wide inter-version meaning. The intended local concept is preservation of the
externally managed Device mode when product lifecycle management is not enabled.

## Architectural impact

### D.002

D.002 changes materially. Its semantic selection state becomes group ownership rather than one
global selected peer. Peer health is shared technical input; optional group health is
owner-specific end-to-end input. Selection/failover is independently evaluated per group,
subject to one exact combined D.003 state.

The current Python manager core is therefore useful evidence/prototype for the one-group
degenerate case, not the final generalized D.002 contract.

### D.003

D.003 responsibility remains exact complete `AllowedIPs` convergence. Its current typed
desired state can already represent different payload prefix sets on different peers; no
selection semantics should move into D.003.

The semantic expansion nevertheless warrants focused review/evidence that simultaneous split
group ownership is accepted exactly, rather than assuming the existing single-common-prefix
kernel case proves every generalized composition.

### C.001 / C.008

C.008 physical ICMP remains reusable. C.001 needs the already designed owner-aware scoped
readiness before alpha/runtime composition, now with peer and group semantic owners in
addition to A.007 Profile owners.

## Requirement impact

`VPNG-U001-R1.R3.R8` is currently phrased as one remote network / one common prefix and has
incomplete decomposition. The generalized behavior is a product-level extension of the same
user need, not an unrelated implementation feature.

The next requirement-design unit should refine R8 so that it covers:

1. multiple independently recoverable network groups on one managed WireGuard interface;
2. distinct peer technical health and optional group end-to-end health;
3. peer-failure recovery even when the group has no endpoint;
4. group-only recovery when its endpoint fails while the peer remains healthy;
5. ordered allowed peer memberships with ordinary sticky / reserve failback semantics;
6. exact postcondition confirmation and invalidation of evidence tied to a previous owner.

The requirement should define these semantics without freezing the TOML spelling or naming
Linux/WireGuard lower resources beyond the already user-visible `AllowedIPs` capability.

## Recommended next unit

Refine/decompose `VPNG-U001-R1.R3.R8` and then update D.002/D.003 architecture against that
accepted normative shape **before** implementing owner-aware scoped C.001 readiness or further
D.002 runtime wiring. The scoped probe-plane design remains required, but coding it against the
one-global-owner D.002 model first would create avoidable rework.
