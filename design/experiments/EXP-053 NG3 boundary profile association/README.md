# EXP-053 — NG3 BoundaryProfileAssociation via skb mark

## Status

PREPARED — evidence pending.

## Requirement trace

This experiment gates physical realization of:

- `VPNG0001-R1.R2.R4.R4.R4` — optional Profile ordinary-side gateway source NAT;
- `VPNG0001-R1.R2.R4.R4.R4.R1` — gateway NAT only after managed firewall acceptance;
- `VPNG0004-R4.R6.R1.R6` — narrow owned host-boundary NAT contributions;
- `VPNG0004-R4.R6.R1.R6.R1` — preserve the already-selected Profile across the common
  host boundary instead of reclassifying by remote source CIDR.

The experiment does not select a production mark range or production nft object names. It
tests whether Linux skb packet marks are a viable carrier for the already accepted semantic
`BoundaryProfileAssociation`.

## Why this evidence is required

Inbound Profile selection is path-relative. Two enabled Profiles may both contain the same
remote prefix while allowing it through different VPN paths. After both flows cross one common
managed/host veth, source-CIDR-only host classification cannot tell which Profile was selected.

The tested carrier therefore has to preserve:

```text
managed policy selected Profile
    ->
packet crosses common veth boundary
    ->
host can observe the same Profile association
    ->
only that Profile's gateway-NAT contribution may apply
```

## Disposable topology

```text
remote-A namespace                       remote-B namespace
source 10.77.0.10                        source 10.77.0.20
Profile A remote prefix 10.77.0.0/24     Profile B remote prefix 10.77.0.0/24
A requests +snat                         B does not
        | vpn-a                                | vpn-b
        +------------------+-------------------+
                           v
                    managed namespace
                    payload_forward
                    priority 0 / policy drop
                           |
                    accepted packets only
                           v
                    association chain
                    forward priority 10
                    A -> skb mark 0x00530001
                    B -> skb mark 0x00530002
                           |
                    common boundary veth
                           v
                       host namespace
                    mark observation
                           |
                    postrouting NAT:
                    mark A -> masquerade
                    mark B -> no NAT
                           |
                           v
                     ordinary LAN
                     203.0.113.2
```

Both Profiles intentionally use the same semantic remote prefix. Only current ingress path
distinguishes them.

The numeric marks are disposable experiment values, not accepted platform allocation.

## Hypotheses

### H1 — accepted-only association

A later managed FORWARD base chain at priority 10 is reached only by packets that survived the
existing priority-0 fail-closed payload filter. An unaccepted source must not acquire a boundary
association or reach the host.

### H2 — skb mark survives the managed/host veth boundary

Packets marked for Profile A/B in the managed namespace arrive on the ordinary host with the
corresponding `meta mark`. Host-side counters independently observe both marks.

### H3 — overlapping remote prefixes remain distinguishable

Profile A and B both use `10.77.0.0/24`, but arrive through distinct managed ingress paths.
The host does not reclassify by source prefix.

Profile A's mark selects MASQUERADE; Profile B's mark does not.

The ordinary LAN listener must therefore observe:

```text
Profile A peer = host ordinary address 203.0.113.1
Profile B peer = original remote address 10.77.0.20
```

### H4 — reverse NAT works for the marked Profile

The Profile-A client must receive the ordinary LAN reply through host conntrack reverse-NAT
without any remote-side return route for its original source being needed by the LAN endpoint.

### H5 — non-SNAT Profile return path stays ordinary routed

The Profile-B client must receive its reply using the explicit ordinary-LAN return route for
`10.77.0.0/24`. No source translation may be inferred merely because another Profile with the
same remote prefix requested `+snat`.

### H6 — host-local termination is not gateway-NATed

Profile-A traffic terminating on the host boundary address may carry the association mark into
the host, but it must not traverse host postrouting gateway NAT. The host-local listener must
observe the original remote source `10.77.0.10`.

### H7 — unrelated host traffic is untouched

Ordinary host-originated traffic to the LAN must retain its normal host source and must not
match the Profile gateway-NAT contribution.

## Procedure

The harness:

1. creates five disposable namespaces: remote A, remote B, managed, host and ordinary LAN;
2. creates two distinct VPN-side veth paths, one common managed/host boundary and one
   host/LAN link;
3. gives both remote paths different concrete source addresses inside the same semantic
   `10.77.0.0/24` remote prefix;
4. installs a priority-0 managed `payload_forward` emulation with policy DROP and path-relative
   accepts;
5. installs a later priority-10 managed association chain that sets one skb mark per selected
   Profile;
6. installs a host observation chain and one mark-selected postrouting MASQUERADE contribution
   for Profile A only;
7. sends real UDP request/reply traffic for A and B;
8. verifies host-local and unrelated-host negative cases;
9. verifies an unaccepted remote source never reaches the host;
10. reads nft JSON counters to prove both Profile marks crossed the common veth;
11. deletes all namespaces in `finally`.

Run:

```sh
sudo python3 "design/experiments/EXP-053 NG3 boundary profile association/exp053_boundary_profile_association.py"
```

## PASS criterion

EXP-053 passes only if H1-H7 all pass in one run.

A PASS would establish skb mark as a viable Linux carrier candidate. It would **not** yet
accept:

- production mark allocation;
- production nft ownership layout;
- lifecycle/reconciliation semantics;
- integration with the current composite managed nft observer;
- alpha runtime `+snat` materialization.

Those require the subsequent architecture/code review.
