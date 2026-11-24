# NG3 2026-11-24 — EXP-086 WireGuard same-prefix multi-peer availability review

**Cycle:** `ng3-wg-multipeer-availability-cdc-20261124`  
**Baseline main:** `6284d7862d64d1722366d5d3ab073cd3c8aa2727`  
**Experiment:** `EXP-086 NG3 WireGuard same-prefix multi-peer availability`  
**Privileged evidence:** GitHub Actions run `45320595770`, job
`linux-wireguard-multipeer` (`138198006146`) — **PASS**  
**Experiment source:** `70d44af5388b7d0d2ad8d5b76dfbde5729ec59bf`

## Scope

Review the projectholder feasibility question:

> Can one WireGuard interface with two alternative peers for the same remote subnet replace
> WireGuard's own peer-routing decision with the ordinary VPN-GATE availability / Linux
> route-priority mechanism?

This review is intentionally not a product-scope decision to add a new WireGuard redundancy
feature. It evaluates whether the requested realization can reuse the current generic mechanism.

## Verdict

**PASS — NEGATIVE FEASIBILITY FINDING. DO NOT IMPLEMENT THE PROPOSED SINGLE-INTERFACE
ROUTE-PRIORITY SUBSTITUTION.**

One `wg0` with two alternative peers for the same remote prefix cannot hand peer selection to
the existing generic availability route-priority mechanism.

The result confirms the current NG3 architecture boundary. No normative requirement or
architecture correction is justified by this investigation alone.

## Findings and dispositions

### F1 — same-prefix ownership inside one WireGuard interface is exclusive

**Finding:** confirmed by privileged evidence.

EXP-086 configured one real `wg0` with two peers and assigned
`10.77.0.0/24` first to peer A and then to peer B.

The observed `wg show wg0 allowed-ips` state retained the exact prefix on only one peer. The
second assignment moved ownership; it did not create two simultaneous alternatives for the
same destination prefix inside one WireGuard cryptokey-routing trie.

**Disposition:** accept as selected negative feasibility evidence.

### F2 — ordinary Linux route priority stops at the common `wg0`

**Finding:** confirmed by privileged dataplane evidence.

EXP-086 installed same-destination Linux routes through the common `wg0`, changed their metric
ordering, and sent real ICMP payload. Per-peer WireGuard transfer counters showed that the
selected peer did not change.

The Linux route lookup remained:

```text
10.77.0.1 dev wg0 src 10.200.0.1
```

This is the relevant abstraction boundary: the generic FIB can select the WireGuard netdevice,
but it does not encode which peer of that netdevice should encrypt a packet whose IP
destination is `10.77.0.1`.

**Disposition:** reject the proposed reuse of ordinary availability route-priority as a
peer-selection mechanism.

### F3 — changing WireGuard ownership changes the dataplane peer

**Finding:** confirmed by privileged dataplane evidence.

With the Linux egress still `wg0`, EXP-086 reassigned `10.77.0.0/24` to the other peer.
The next real payload moved to that peer, again identified by transfer-counter deltas.

Therefore peer selection is controlled by WireGuard cryptokey-routing state, not by the relative
priority of ordinary routes that all terminate on the same WireGuard interface.

**Disposition:** retain the existing architecture statement that WireGuard destination ownership
is an integration-specific `AllowedIPs` concern.

### F4 — current NG3 logical path identity independently prevents direct peer reuse

**Finding:** accepted from current implementation/architecture inspection.

Current `LogicalPathId` is projected from Device selector slots, while `PathBinding` binds a
logical path to one exact `InterfaceIdentity(ifname, ifindex)`.
`project_device_bindings()` obtains those bindings from the interface inventory.

Two WireGuard peers inside one `wg0` therefore do not become two generic concrete paths merely
because WireGuard has two peer records. Both peers share one observed interface generation.

The current architecture also explicitly states that demand-scoped private peer facts are not
path identity. That statement was introduced for point-to-point endpoint observation and must
not be reinterpreted as generic WireGuard peer identity.

**Disposition:** no change. Creating peer-level logical paths would be a new architecture
decision, not a missing implementation detail.

### F5 — `Table = off` does not remove WireGuard cryptokey routing

**Finding:** accepted.

The documented WireGuard integration uses `Table = off` so `wg-quick` does not create its own
ordinary Linux payload routes/RPDB policy. This is compatible with VPN-GATE owning ordinary
route priority.

It does not disable the separate WireGuard `AllowedIPs` lookup that selects the peer after a
packet has been handed to `wg0`.

**Disposition:** retain the documented `Table = off` integration contract; do not describe it as
delegating peer selection to VPN-GATE.

### F6 — two distinct WireGuard interfaces are the natural generic-availability realization

**Finding:** architecture-compatible, not newly selected as a product requirement by this review.

If each alternative peer has its own WireGuard interface, each alternative has a distinct
`InterfaceIdentity`. Each WireGuard interface may then own the same remote prefix independently
inside its own peer table, while the generic VPN-GATE route-priority layer can choose between
the two different egress interfaces.

That shape matches the existing path/availability abstraction instead of piercing it.

**Disposition:** this is the preferred design candidate if the productholder later requires
same-prefix WireGuard redundancy while preserving the generic availability model. A product
decision and focused integration acceptance should precede claiming it as supported behavior.

### F7 — dynamic `AllowedIPs` switching on one interface is technically different machinery

**Finding:** accepted.

A single-interface design could in principle keep one peer as the current owner and have a
WireGuard-specific lower component move the remote prefix to another peer after availability
changes.

That design does not replace WireGuard routing. It makes WireGuard peer ownership an explicitly
managed state. It would require at least:

- stable supported peer identity/provenance;
- exact observation of current `AllowedIPs` ownership;
- guarded mutation/confirmation and failure semantics;
- coordination with probe reachability and payload route convergence;
- administrator-visible configuration/diagnostics;
- new architecture and acceptance evidence.

**Disposition:** do not introduce this machinery without an explicit accepted product need.
The present feasibility question is not sufficient authority.

## Requirements and architecture impact

No current normative node is contradicted by EXP-086.

The current protocol-neutral Profile/availability model does not promise that multiple peers
inside one VPN netdevice become independent generic paths. The current WireGuard integration
boundary already preserves cryptokey-routing ownership below generic route realization.

Accordingly:

- **requirements change:** none;
- **architecture change:** none;
- **production implementation change:** none;
- **new selected evidence:** EXP-086 negative feasibility result.

## Review-unit closure

The requested feasibility question is closed.

For the exact requested form:

```text
one wg interface
+ two peers
+ same remote subnet
+ generic availability route-priority selects peer
```

the answer is **no**.

A future product decision may separately choose either distinct WireGuard interfaces per
alternative peer or new WireGuard-specific `AllowedIPs` ownership management.
