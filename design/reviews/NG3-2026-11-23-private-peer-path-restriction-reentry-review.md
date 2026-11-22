# NG3 2026-11-23 — private-peer per-path restriction re-entry review

**Scope:** re-enter `VPNG-U001-R1.R4.R2.R1` and
`VPNG-U001-R4.R4.R6.R2.R5` after clarifying the actual user need and recovering
historical RC2/RC3 evidence.

## Verdict

**PASS — RE-ENTER THE POSTPONED CAPABILITY, BUT ONLY FOR THE NARROW DYNAMIC
POINT-TO-POINT MEMBER CASE. DO NOT BUILD A GENERIC VPN-PATH IDENTITY SYSTEM.**

The previous unpublished research direction based on a configured opaque path key is rejected
for this re-entry. It solves a broader identity problem than the user actually has and would
introduce duplicate bookkeeping for cases that already have simpler selectors.

## Findings and dispositions

### F1 — the real user-visible scope is one capability, not a family of different features

**Decision:** accepted.

The relevant user intent is always:

> apply an additional restrictive Device firewall rule only to traffic using one selected
> VPN path, without changing the other current paths of the same Device.

Examples such as "deny OUT DNS on this path", "deny IN SMB on this path" or "allow only one
remote prefix on this path" differ only in the ordinary firewall predicate. They do not
justify separate path-selection mechanisms.

### F2 — most apparent per-path cases already have cheaper ordinary selectors

**Decision:** accepted.

For the supported product shapes discussed with the owner:

- when the exact interface is stable/known, existing exact-interface binding already
  identifies the path;
- when remote networks are distinct, the existing payload network predicate distinguishes
  the traffic without a new path identity;
- WireGuard keeps one stable interface while peer destination ownership is determined by
  non-overlapping `AllowedIPs`; the user already knows the remote prefixes and can restrict
  those prefixes on `wg0`;
- ordinary OpenVPN/L3 and L2TP deployments with a known exact interface and known remote
  network likewise do not need an additional selector.

Therefore a generic selector framework for WireGuard public keys, OpenVPN CN/session identity,
L2TP session IDs, external VPN server endpoints, or arbitrary integration-specific identities
would add transport-specific runtime management without a demonstrated product need.

### F3 — the uncovered case is dynamic interface-family membership plus overlapping remote space

**Decision:** accepted.

The materially different case is OpenConnect/ocserv-like point-to-point runtime membership:

- the Device is configured against a dynamic interface family (`iif*` / historical
  `vpns+`-style shape);
- several concrete members may exist simultaneously;
- the same protected/remote network may be reachable through more than one member;
- the concrete exact ifname for a particular remote end is not known before runtime;
- filtering by remote payload prefix therefore does not identify the intended member.

This is the reason an additional path discriminator has product value. The mechanism must not
be generalized beyond this gap merely because other VPN technologies expose other identities.

### F4 — historical evidence already proved the required correlation

**Decision:** accepted; reuse existing evidence.

Relevant historical evidence:

1. **EXP-004.3** proved that ocserv configured device naming is a runtime family, not a
   durable exact ifname; successive/concurrent sessions may materialize different
   `vpns*` names.
2. **EXP-009.1** observed two simultaneous OpenConnect sessions as independent concrete
   interfaces with the same local VPN address and different point-to-point private peers:
   `vpns00 ... peer 172.20.130.6` and
   `vpns01 ... peer 172.20.130.5`.
3. The first post-EXP-009 RC3 architecture at commit
   `1a887d0ed237` explicitly introduced
   `PeerBinding(peer, name, ifindex)` from unambiguous point-to-point
   `(local_address, peer)` evidence. It explicitly rejected association by creation order,
   numeric suffix, lexical order or array position.
4. Commit `e002313530ae` later removed transport `peers` / `PeerBinding` from the
   **route model** after EXP-009 also proved direct-device OpenConnect routing and WireGuard
   `AllowedIPs` peer ownership. That simplification did not invalidate observation of the
   private point-to-point peer or the `peer -> exact current interface` correlation.

The previously recovered evidence therefore answers the technical association question; a new
VPN-specific runtime manager is not justified.

### F5 — private/inner P2P peer IPv4 is the selected discriminator

**Decision:** accepted.

For the uncovered case, the selector operand is the **private/inner point-to-point peer IPv4**
observable on the already Device-owned current interface.

It is not:

- the external VPN transport/server endpoint;
- a payload source/destination field;
- a durable Linux ifname/ifindex;
- a globally searched host fact;
- a universal identity for every kind of VPN path.

The intended resolution boundary is:

```text
configured Device
    -> its already accepted current candidate/bound interfaces
    -> fresh interface-address observation
    -> private P2P peer == requested IPv4
    -> exact current (ifname, ifindex)
    -> apply the path-scoped restrictive firewall rule
```

The peer IPv4 may appear only in the firewall rule; the user is not required to duplicate it
in a separate path declaration solely to make the restriction addressable.

### F6 — selection is Device-scoped and fail-closed

**Decision:** accepted.

The implementation must never scan arbitrary host interfaces for a matching peer and then
infer Device ownership.

A private-peer selector is resolved only among current interfaces already belonging to the
Device binding projection. For a rule that requires such selection:

- exactly one current Device path with the requested private peer -> selected path;
- no such current path -> the rule currently selects no path;
- observation failure or evidence that cannot distinguish the relevant current candidate
  safely -> do not create allowing policy that assumes the restriction is absent;
- more than one current Device path presenting the same requested peer -> ambiguous and
  fail closed for the affected policy projection rather than choosing one arbitrarily.

This preserves the established unknown-vs-absent safety distinction.

### F7 — the existing requirement wording over-blocks the selected solution

**Decision:** accepted; requirement correction required.

`VPNG-U001-R4.R4.R6.R2.R5` currently says that a transport endpoint/peer must not become
the user identity of the selector. That wording was written while the design was searching
for a universal durable logical-path identity.

The clarified distinction is:

- **external transport endpoint/peer identity** must not be required as a generic path
  identity;
- an **inner/private P2P peer IPv4** may be a narrow rule-local discriminator for a current
  Device path where the exact member is otherwise unknown.

The requirement must be corrected before implementation so architecture is not forced to
violate its current wording.

### F8 — lower filtering itself is already available

**Decision:** accepted.

Current Device-firewall compilation already materializes policy per current exact path
endpoint. The missing pieces are only:

1. normalize an optional private-peer selector on a firewall rule;
2. observe private P2P peer facts for already owned current endpoints;
3. resolve the selector to the exact current logical path;
4. derive the effective rule set for each path;
5. preserve ordinary Device-wide rule semantics for rules without the selector.

No new nft packet discriminator is required: after resolution, existing exact current
interface-pair filtering remains the enforcement mechanism.

## Re-entry disposition

The old Release-1 postponement is no longer the selected product decision for this scope.

The next requirement change should:

1. re-enter both postponed nodes into the active frontier;
2. narrow the promised per-path selection to the demonstrated dynamic P2P-member case;
3. distinguish inner/private peer from external transport endpoint;
4. extend the Device firewall grammar with one optional rule-local private-peer selector;
5. preserve the rule as an additional restriction only;
6. remove the old blanket first-release deferral constraints for this capability.

The next architecture unit should reuse existing `ConfigurationAdapter`,
`PayloadPolicyCalculator`, `VPNPathAdapter` and `NetworkPolicyAdapter` responsibilities
rather than introduce a VPN-type Manager.
