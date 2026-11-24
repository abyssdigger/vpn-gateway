# NG3 2026-11-24 — EXP-088 WireGuard ten-peer result review

**Review unit:** ten-peer single-interface WireGuard lower mechanism  
**Evidence source:** `25f1e055b30b80aae033f4dc218ab2cd4fa6e8bc`  
**Evidence run:** `45459878834`  
**Evidence job:** `linux-wireguard-multipeer` (`138679341481`)  
**Result record:** `design/experiments/EXP-088 NG3 managed WireGuard ten-peer lifecycle/EXP-088-result-20261124.md`

## Scope

Review whether EXP-088 supplies sufficient lower evidence to proceed with architecture design
for:

- explicit VPN-GATE-owned Device lifecycle under `VPNG-U001-R1.R3.R7*`;
- same-prefix WireGuard peer redundancy under `VPNG-U001-R1.R3.R8`;
- invalidation of stale Profile availability evidence when peer ownership changes behind one
  unchanged `LogicalPathId` / `wg0`.

This review does not close those open requirements and does not authorize production code.

## Verdict

**PASS — LOWER MECHANISM CONFIRMED; ARCHITECTURE SELECTION REMAINS OPEN.**

## Findings and dispositions

### F1 — ten permanent peer identities behind one wg0 are operationally representable

**Decision:** accepted.  
**Resolution:** fixed by evidence.

One `wg0` retained ten peers, each with its own permanent in-tunnel probe `/32`. All ten
probe targets were independently reachable and directly attributable to their intended peer.

The experiment therefore removes the remaining scale concern from the two-peer EXP-087
result for the tested ten-peer shape.

### F2 — base configuration can safely omit shared payload ownership

**Decision:** accepted.  
**Resolution:** fixed by evidence.

The generated base WireGuard configuration contained all permanent peer facts while assigning
the shared `10.77.0.0/24` prefix to no peer.

This is the preferred lower startup boundary for later architecture design: service/interface
existence does not silently select a payload owner before fresh peer observation.

### F3 — ordered same-prefix failover does not require wg0 recreation

**Decision:** accepted.  
**Resolution:** fixed by evidence.

The shared prefix moved through A -> B -> ... -> J using runtime `wg set` updates while
the common WireGuard interface remained in place. Recovery back to A was also successful.

This confirms that peer-owner switching and base Device lifecycle are distinct lower
operations.

### F4 — realization generation is required independently of LogicalPathId

**Decision:** accepted.  
**Resolution:** fixed as an architecture input.

Every freshly confirmed peer-owner change advanced the experiment's realization generation.
Evidence from the previous generation was then rejected as stale.

Because `LogicalPathId` and `wg0` remain unchanged across the peer switch, final
architecture needs an equivalent generation boundary below or alongside `PathBinding`.
Synthetic peer-level `LogicalPathId` values remain rejected.

### F5 — full base restart correctly destroys dynamic peer ownership

**Decision:** accepted.  
**Resolution:** fixed by evidence.

Deleting and recreating `wg0` from the unchanged base configuration restored all permanent
probe prefixes and restored the shared prefix to the no-owner state. A fresh owner had to be
selected afterward.

The observed ifindex changed from 2 to 3. This is useful evidence of a fresh interface
generation in this run, not a guarantee that Linux can never reuse an ifindex.

### F6 — command success is not sufficient confirmation

**Decision:** accepted.  
**Resolution:** fixed as an architecture input.

The experiment advanced its generation only after fresh exact `AllowedIPs` observation.
A deliberately failed `wg set` did not change confirmed state or generation.

Future Machinery for WireGuard peer ownership must therefore have Direct completion semantics:
success means the requested lower postcondition was freshly observed, not merely that a
command was submitted.

### F7 — transition observation does not justify a mandatory extra traffic gate

**Decision:** accepted.  
**Resolution:** fixed for the current design input; re-entry is evidence-gated.

During one 200-packet A-to-B live transition:

- packet loss: 0;
- replies: A=24, B=176;
- confirmation time: approximately 4.7 ms;
- no third peer produced a payload reply;
- after confirmation, payload replies came from B.

This does **not** prove a universal transactional-atomicity guarantee for arbitrary kernels or
future update shapes. It does show no current evidence requiring a separate payload gate
solely for a normal complete-state owner transfer.

The architecture should instead keep the realization unconfirmed during apply and publish the
new generation only after fresh exact observation.

Re-enter a dedicated transition-containment mechanism if later privileged evidence shows any
of:

- payload delivery by an unintended third peer;
- stale old-owner delivery after the new owner has been freshly confirmed;
- a partial apply that can be mistaken for confirmed desired state;
- another concrete safety requirement that cannot tolerate the observed transition.

### F8 — WireGuard transfer counters are not precise enough as sole payload attribution

**Decision:** accepted.  
**Resolution:** fixed in the experiment.

An earlier EXP-088 run observed a small unrelated transfer-counter increment on another
recently probed peer. The final stand therefore used unique peer reply TTLs for direct payload
attribution and retained transfer counters only as secondary observations.

This does not invalidate EXP-086/087, whose smaller topologies did not exhibit ambiguous
counter deltas; it constrains how the ten-peer stand identifies payload ownership.

### F9 — the experiment does not settle secret ownership or configuration surface

**Decision:** accepted.  
**Resolution:** deferred to managed-Device configuration design.

The generated base configuration proves the WireGuard lower shape. It does not select where
private keys are stored, how credentials are referenced, which user-facing fields enable
management, or whether systemd is the final lifecycle realization.

Those questions remain architecture/configuration work under `VPNG-U001-R1.R3.R7*`.

## Experiment disposition

The technical result is accepted, but the final component architecture has not yet been
selected.

Registry disposition: **pending_decision**.

The expected re-entry is the immediately following managed-Device / WireGuard architecture
review. If that review selects this mechanism, the registry may then promote EXP-088 to
`selected`.

## Closure

The experiment review unit is closed.

The next review unit is architecture design, not additional WireGuard feasibility work.
