# NG3 authoritative host-boundary behavior owner review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-alpha-release-blockers-35m`

## Scope

Authoritative host-side nft ownership/convergence for the selected EXP-064 fixed
host-boundary behavior lanes.

This unit implements the host-side behavior owner itself. It does **not** yet wire the
behavior lanes into the alpha lifecycle or remove the alpha `+snat` fail-fast.

## Requirements / accepted design

Implements or supports:

- `VPNG0001-R1.R2.R4.R4.R4`;
- `VPNG0001-R1.R2.R4.R4.R4.R1`;
- `VPNG0004-R4.R6.R1.R6`;
- `VPNG0004-R4.R6.R1.R6.R1`;
- selected EXP-064 fixed behavior-lane carrier.

The host does not recover Profile identity. It consumes only one of the four already-selected
behavior classes:

```text
STATEFUL_NO_NAT
STATEFUL_NAT
ROUTE_NO_NAT
ROUTE_NAT
```

Multiple Profiles with the same required host behavior share the same class and lane owner
rules.

## Implementation

Added `linux_host_boundary_behavior.py` with one strict owned nft table:

```text
inet vpn_gate_host_behavior
    prerouting   filter / mangle
    output       route  / mangle
    postrouting  nat    / srcnat
```

For each active lane:

1. NEW ingress establishes that lane's fixed host conntrack class;
2. every packet arriving from that lane exits this owner's prerouting processing before
   stateful return-mark restore;
3. stateful classes restore the existing common selected-host-boundary return packet mark on
   ordinary-side replies and host-local OUTPUT replies;
4. NAT-enabled classes masquerade only connections carrying their corresponding host class.

The second unconditional per-lane prerouting return is intentional. Without it, later packets
of the original VPN→ordinary direction on an already classified connection could match the
stateful class and acquire the return mark, reflecting them toward the managed stack.

The existing selected-host-boundary return route/RPDB owner remains the common stateful-return
mechanism. The historical source-prefix host-return nft classifier is an alternative
pre-lane realization and must not coexist with the behavior-lane classifier once lanes are
activated. Alpha integration must retain the return route/RPDB dependencies while omitting
that historical nft classifier.

## Numeric ownership

Fixed host behavior class marks are lower Linux allocations:

```text
STATEFUL_NO_NAT  0x30000001
STATEFUL_NAT     0x30000002
ROUTE_NO_NAT     0x30000003
ROUTE_NAT        0x30000004
```

The common return packet mark remains the existing selected-host-boundary mark
`0x56504E47`.

These values are distinct from stack Profile-affinity marks and the probe mark. They are not
user-visible configuration and do not encode Profile identity.

## Observation / convergence

The owner:

- verifies its exact table owner comment;
- verifies the exact three-chain set and chain hook/type/priority/policy;
- verifies exact owned rule identities and per-chain ordering;
- validates classifier, lane-return, stateful return-restore and NAT rule shapes;
- treats foreign objects/rules in its owned table as conflicts;
- replaces from current observation and requires a fresh exact postcondition;
- supports explicit cleanup to complete owner absence.

No foreign host nft state is adopted or deleted.

## Review findings and dispositions

### F1 — cross-chain rule order was initially over-constrained

The first observer compared one global rule-comment sequence. Real nft JSON ordering is
meaningful within a chain but should not be used as a contract across different chains.

**Disposition:** accepted and fixed. Exactness now validates order independently per owned
chain while still requiring the exact rule set.

### F2 — subsequent forward-direction packets need an explicit lane-ingress guard

A stateful connection retains the host class mark. A generic stateful return-restore rule
without an earlier lane-ingress stop could therefore mark later VPN→ordinary packets for the
return table.

**Disposition:** accepted and fixed in the owner contract. Every active lane receives an
unconditional prerouting return immediately after its NEW classifier, before all stateful
return-restore rules.

### F3 — do not duplicate the selected stateful-return route/RPDB owner

EXP-064 needs the same common host return route/RPDB mechanism already selected by the
ordinary host-boundary owner. Creating a second route/rule owner would produce overlapping
ownership without adding semantics.

**Disposition:** rejected as unnecessary machinery. The behavior owner owns only nft
classification/restore/NAT; the existing selected owner keeps route/RPDB responsibility.

### F4 — old source-prefix classifier and lane classifier cannot coexist

The existing host-return nft owner classifies remote traffic by source prefix on the primary
boundary. EXP-064 instead classifies by actual behavior-lane ingress. Running both would
create two competing host connection classifiers.

**Disposition:** accepted as an integration invariant. The next alpha-wiring unit must keep
the selected return route/RPDB dependencies but suppress the old source-prefix nft classifier
when behavior lanes are active.

## Evidence

NG3 Python workflow run `44536827746`:

- `unit`: **PASS**;
- `linux-host-boundary-behavior-owner`: **PASS**;
- `linux-host-boundary-behavior-lanes` (EXP-064 traffic semantics): **PASS**;
- `linux-alpha-smoke`: **PASS**;
- `linux-payload-forward`: **PASS**;
- `linux-exp049-openvpn`: **PASS**.

The new privileged owner job proves:

```text
absent
 -> apply real nft owner
 -> fresh authoritative exact observation
 -> cleanup to exact absence
 -> foreign-owner conflict rejection
```

The workflow remains red only on the existing active-workflow items:

- `linux-nft-marked-host-bootstrap` — EXP-057 historical rejected mechanism;
- `linux-profile-gateway-nat-association` — EXP-063 historical rejected mechanism;
- `linux-selected-host-bootstrap-backend` — selected EXP-060 backend failure and a real
  remaining release blocker.

## Simplification review

No new Manager, userspace proxy, per-Profile host lane, per-Profile host mark allocation,
generic host-firewall framework or duplicate return-route owner was introduced.

The implementation adds only the host-side mutable owner required by the selected EXP-064
carrier.

## Requirement-state inventory

### decomp

Resolved historical links remain:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT.**

The selected fixed behavior-lane carrier now has an authoritative production-shaped host nft
owner with independent ownership/convergence evidence. The next logical unit is alpha
lifecycle/materialization wiring: create the required lane boundaries, suppress the old
source-prefix host nft classifier while retaining return route/RPDB dependencies, compose
lane routes + initial packet selection + host behavior owner, and only then remove the
`+snat` fail-fast.
