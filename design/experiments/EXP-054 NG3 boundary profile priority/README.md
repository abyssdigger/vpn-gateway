# EXP-054 — NG3 BoundaryProfileAssociation via skb priority

## Status

PREPARED — evidence pending.

## Trigger

EXP-053 rejected nft `meta mark` as the carrier because managed association rules executed
but host-side mark counters remained zero after the cross-network-namespace veth boundary.

Current Linux `skb_scrub_packet(..., xnet=true)` explicitly clears `skb->mark`. The same
scrub function does not clear `skb->priority`, making packet priority a technically distinct
candidate worth testing rather than another spelling of the failed mechanism.

This experiment tests feasibility only. `skb->priority` is also the tc classid/QoS metadata
surface, so a PASS does not by itself establish safe production allocation.

## Requirement trace

Same semantic gate as EXP-053:

- `VPNG0001-R1.R2.R4.R4.R4`;
- `VPNG0001-R1.R2.R4.R4.R4.R1`;
- `VPNG0004-R4.R6.R1.R6`;
- `VPNG0004-R4.R6.R1.R6.R1`.

## Topology and policy

The topology is intentionally identical to EXP-053:

- Profile A and Profile B both use semantic remote prefix `10.77.0.0/24`;
- they arrive through distinct VPN-side managed interfaces;
- both cross one common managed/host veth;
- A requests ordinary-side `+snat`;
- B does not.

After the priority-0 fail-closed managed Profile permission accepts a packet, a later
priority-10 FORWARD chain assigns:

```text
Profile A -> meta priority set 0x54:0x1
Profile B -> meta priority set 0x54:0x2
```

The ordinary host never inspects the remote source prefix. It observes only the carried packet
priority. Only `0x54:0x1` selects the host postrouting MASQUERADE contribution.

The classids above are disposable experiment values, not accepted platform allocation.

## Hypotheses

### H1 — accepted-only association

Traffic dropped by the existing priority-0 managed payload policy never reaches the later
association chain and therefore never reaches host association counters.

### H2 — skb priority survives the veth/netns boundary

Both managed priority-setting rules execute and the corresponding host `meta priority`
counters increment after the common boundary.

### H3 — path-relative Profiles with overlapping prefixes stay distinct

The ordinary LAN sees:

```text
Profile A -> source 203.0.113.1  (host MASQUERADE)
Profile B -> source 10.77.0.20   (no gateway NAT)
```

No host source-CIDR reclassification is permitted.

### H4 — reverse NAT and ordinary routed return both work

A receives the reply through host conntrack reverse NAT. B receives the reply through the
explicit ordinary return route without translation.

### H5 — host-local termination is not gateway-NATed

Profile-A traffic terminating on the ordinary host retains source `10.77.0.10`.

### H6 — unrelated host traffic is untouched

Ordinary host-originated LAN traffic retains ordinary host source and does not depend on the
Profile metadata.

### H7 — no hidden tc/QoS conclusion

A packet-path PASS proves only carrier survival and matchability. Before production selection,
review must establish whether a reserved `skb->priority` classid space can coexist with
administrator/host tc/QoS policy without violating the narrow host ownership constraint.

## PASS criterion

H1-H6 must pass in one privileged Linux run. H7 remains a mandatory architecture/allocation
review gate after a technical PASS.
