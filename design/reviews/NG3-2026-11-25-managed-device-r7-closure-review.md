# NG3 managed Device R7 closure review — 2026-11-25

**Review unit:** closure of the explicitly managed Device base-lifecycle requirement branch  
**Baseline:** `bb83fb1a217f757b040b218838307b4b036d23ed`  
**Requirements:** `VPNG-U001-R1.R3.R7*`  
**Architecture:** A.002, A.012, D.001, C.004  
**Evidence basis:** `EV-00070`, `EV-00080`, `EV-00090`

## Scope

Re-review the R7 requirement branch after its architecture and runtime implementation have
both become complete. The review asks whether any unresolved product or architecture decision
still justifies the current `open` / `decomposition: incomplete` markers.

This unit does not add a new Device-manager feature and does not reopen generalized WireGuard
peer ownership under R8.

## Findings and dispositions

### F1 — R7 decomposition is now complete for the accepted scope

**Decision:** accepted.  
**Resolution:** fixed.

The parent is fully partitioned by its existing children:

- R7.R1 owns explicit opt-in and preservation of externally prepared Devices;
- R7.R2 owns desired-vs-confirmed generation and confirmed lifecycle postconditions;
- R7.R3 owns the first demand policy: enabled Device referenced by an enabled Profile.

No accepted R7 behavior is left outside those children. Packet-triggered activation and
idle-time disconnect are explicitly excluded by R7.R3 and therefore are not hidden missing
decomposition.

### F2 — R7.R2 no longer needs further decomposition

**Decision:** accepted.  
**Resolution:** fixed.

R7.R2 is sufficiently atomic for the current product contract. D.001 distinguishes the desired
base generation from freshly confirmed effective state, detects secret-content changes in the
desired generation, confirms present/absent postconditions, and replaces a changed generation
through confirmed old-generation absence before creating and confirming the new one.

A.012 accepts only the matching confirmed generation and exposes problem/waiting state instead
of treating command submission as lifecycle success. C.004 independently confirms whether the
resulting interface is usable as a PathBinding.

A separate hot-reload promise is neither stated nor required. The current product may realize
configuration replacement through the accepted stop/absence/recreate/start sequence.

### F3 — external Device compatibility is still a live product path

**Decision:** accepted.

Absence of `managed_vpn` keeps a Device outside A.012/D.001 ownership. Existing C.004
observation/binding remains the path for externally prepared VPN instances; same-name foreign
WireGuard objects are rejected by D.001 rather than adopted or removed.

### F4 — structural demand has executable lifecycle semantics

**Decision:** accepted.

A.012 requests presence only for explicitly managed Devices in
`CurrentConfig.structural.active_device_ids`. Loss of demand does not immediately destroy the
base VPN: product-owned dependent policy/dynamic state must first be confirmed released, after
which A.012 permits D.001 confirmed absence. Product stop follows the same ownership order.

### F5 — current evidence is sufficient for closure

**Decision:** accepted.

- `EV-00070` proves the production D.001 managed-WireGuard lifecycle and ownership/secret
  preconditions.
- `EV-00080` proves the A.012 orchestration core, desired/confirmed generation handling and
  dependency-release gating.
- `EV-00090` proves Release-1 runtime composition, ordering before path observation, status
  publication and dependency-safe shutdown.

All four R7 nodes have exact `full` architecture edges. No R7 node has an active
decomposition blocker, unrealizability link, broken-solution link or rejected closure.

## Requirement disposition

The accepted result is:

- `VPNG-U001-R1.R3.R7`: `decomposition: complete`, `closed`;
- `VPNG-U001-R1.R3.R7.R1`: `closed`;
- `VPNG-U001-R1.R3.R7.R2`: `decomposition: complete`, `closed`;
- `VPNG-U001-R1.R3.R7.R3`: `closed`.

This is an architecture-closure decision, not a release decision and not a claim that every
future Device lifecycle feature belongs to R7.

## Verdict

**PASS — the current explicitly managed Device base-lifecycle branch has sufficient accepted
architecture and evidence for closure; no additional R7 decomposition or runtime implementation
is required for its present scope.**
