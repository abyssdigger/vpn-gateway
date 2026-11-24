# NG3 2026-11-24 — managed WireGuard Adapter implementation review

**Review unit:** production D.001 WireGuard base lifecycle  
**Reviewed implementation:** `3435600145081f08275a943b1d6a20c544e8398d`  
**Architecture:** D.001 ManagedVPNAdapter  
**Requirements:** `VPNG-U001-R1.R3.R7*`

## Verdict

**PASS — D.001 WIREGUARD CONTRIBUTION IS FULLY MATERIALIZED.**

The product still does not automatically demand managed VPN presence: A.012 remains
unmaterialized. This verdict is component-local and does not close R7/R7.R2/R7.R3 at product
level.

## Findings and dispositions

### F1 — foreign same-name interfaces must not be adopted

**Decision:** accepted.  
**Resolution:** fixed and verified.

The Adapter derives a stable per-Device `ifalias` ownership marker. A same-name interface
without the exact marker is a conflict for `converge_present`, while
`converge_absent` leaves it untouched. A marker attached to a non-WireGuard link kind is
also rejected rather than treated as owned WireGuard.

The marker is not treated as a security boundary against root; the implementation re-observes
link identity and kind before deletion.

### F2 — secret references require a fresh lower precondition

**Decision:** accepted.  
**Resolution:** fixed and verified.

Private and preshared key files are opened with `O_NOFOLLOW`, checked through the opened file
descriptor for regular-file type, effective-UID ownership and absence of group/other
permissions, and validated as canonical 32-byte WireGuard keys before mutation.

The private key is passed to `wg setconf` through stdin and is not written into a generated
configuration file. Secret values are not returned in the public observation.

### F3 — command success is not lifecycle confirmation

**Decision:** accepted.  
**Resolution:** fixed and verified.

Present success requires a fresh link/address/WireGuard observation matching the expected base
state. Changed base state follows owned delete -> freshly confirmed absence -> create ->
fresh exact verification. Stop returns success only after a new ownership observation proves
absence.

The confirmed generation is a digest of non-secret base facts plus irreversible secret-derived
identity/digests. A private-key content change at the same configured path therefore creates a
different generation.

### F4 — peer order does not belong to D.001 base generation

**Decision:** accepted.  
**Resolution:** fixed and verified.

Peer array order is D.002 selection policy. The D.001 generation canonicalizes base peer facts
by public key, and live integration proves that reversing configured peer preference preserves
the same interface generation and D.001 confirmed-generation token.

### F5 — mutable payload AllowedIPs belong to D.002

**Decision:** accepted.  
**Resolution:** fixed and verified.

D.001 verifies each configured peer's permanent probe `/32` but does not police additional
`AllowedIPs` on that peer. The integration test assigns the shared payload prefix after base
creation and proves a subsequent D.001 converge neither recreates the interface nor removes
the dynamic prefix.

A full D.001 base restart still uses `wg setconf` from the base configuration and therefore
returns to the selected no-owner state, as required by the D.001/D.002 boundary.

### F6 — lower execution errors must not leak an incidental subprocess API

**Decision:** accepted.  
**Resolution:** fixed.

Command and stdin-command failures are translated at the Adapter boundary to
`ManagedWireGuardError`. No generic service/process driver was introduced.

### F7 — implementation traceability is explicit

**Decision:** accepted.  
**Resolution:** fixed.

`managed_wireguard_adapter.py` is traced to D.001 in
`design/NG3/implementation-traceability.md`, and the component spec now declares the
production implementation edge. The source file carries the reverse architecture marker.

## Evidence

GitHub Actions run `45477609885` on
`3435600145081f08275a943b1d6a20c544e8398d`:

- `unit`: PASS;
- `linux-wireguard-multipeer` job `138741997228`: PASS;
- production D.001 markers:
  - `D001_WG_FOREIGN_PRESENT_REJECTED=PASS`;
  - `D001_WG_START_CONFIRMED=PASS`;
  - `D001_WG_IDEMPOTENT_PRESENT=PASS`;
  - `D001_WG_PEER_ORDER_NOT_BASE_GENERATION=PASS`;
  - `D001_WG_DYNAMIC_ALLOWEDIPS_IGNORED=PASS`;
  - `D001_WG_SECRET_PRECONDITION=PASS`;
  - `D001_WG_CHANGED_SECRET_RESTART=PASS`;
  - `D001_WG_STOP_CONFIRMED=PASS`;
  - `D001_WG_FOREIGN_STOP_PRESERVED=PASS`;
  - `D001_WG_RESULT=PASS`;
- `linux-alpha-smoke`: PASS;
- frozen Release-0.1.0 isolation: PASS.

Stable evidence address: `EV-00070`.

## Result

The WireGuard-specific production obligation of D.001 is complete. The next dependent block is
A.012 orchestration: derive structural demand, call D.001 present/absent, publish
desired/confirmed generation and problem state, and preserve cleanup ordering. D.002/D.003
remain separate later units.
