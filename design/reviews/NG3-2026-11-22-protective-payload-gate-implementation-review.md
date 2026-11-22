# NG3 2026-11-22 — C.010 protective payload gate implementation review

**Scope:** production implementation of accepted C.010 `ProtectivePayloadGate`.

**Architecture baseline:** main `7ff737fd252283aadaf7d06166e6386fe664d0f0`  
**Implementation head:** `4c287c127c2436f9504bfb58e1cfaae598c10532`  
**Requirements:** `VPNG-U004-R5`, `.R2`, `.R3`, `.R4`

## Verdict

**PASS — C.010 IS MATERIALIZED AND ITS `<partial>` MARKER MAY BE REMOVED.**

## Findings and dispositions

### F1 — production contract matches the accepted bounded-Enforcer role

**Decision:** accepted.  
**Resolution:** fixed.

`protective_payload_gate.py` implements one bounded fresh-observe -> optional owned mutation
-> fresh-observe attempt. It has no hidden retry or continuous lifecycle. Observation failure,
ownership conflict, apply failure and postcondition failure remain distinct results.

Continuous recovery remains A.011 responsibility.

### F2 — Linux ownership and drift handling are fail-closed

**Decision:** accepted.  
**Resolution:** fixed.

The Linux realization uses one dedicated `inet vpn_gate_protective` table with an explicit
VPN-GATE owner marker. Observation distinguishes:

- absent;
- exact;
- owned drift;
- conflict.

Only absent or proven-owned state may be mutated. Wrong/missing owner marker is conflict and is
not adopted or deleted.

Owned drift may be replaced in one nft transaction; disable deletes only the proven-owned
table.

### F3 — exact postcondition matches selected EXP-083 mechanism

**Decision:** accepted.  
**Resolution:** fixed.

ENABLED requires exact dedicated chains/rules for:

- IPv4 INPUT through the current ordinary-side boundary;
- IPv4 OUTPUT through that boundary;
- all IPv4 FORWARD.

The implementation preserves EXP-083's selected one-gate shape and does not repurpose C.005
`ForwardingGate`.

### F4 — executable evidence is sufficient for the implementation unit

**Decision:** accepted.

Unit/compile job passed on implementation head. The production-shaped live integration in the
`linux-forwarding-barrier` job also passed:

- enable exact gate;
- detect and repair proven-owned drift;
- disable and confirm absence;
- refuse a conflicting foreign table.

The same job reran EXP-083 and existing C.005 integration successfully.

### F5 — traceability is complete

**Decision:** accepted.  
**Resolution:** fixed.

Both new production units trace exactly to C.010 in
`design/NG3/implementation-traceability.md`, and C.010 now contains a concrete
`Implementation` block. No architecture debt or fictitious trace edge is required.

## Result

C.010 is now a materialized current component. A.011, E.003 and E.004 remain explicitly
`<partial>` until their own production implementations are completed.
