# NG3 generalized R8 materialization-status review — 2026-11-25

**Review unit:** post-R8.R6 component materialization-status consistency  
**Baseline:** `main@d2c54da7d979457489fc4529e1e5f4e2ebc7a68d`  
**Requirement family:** `VPNG-U001-R1.R3.R8*`  
**Evidence:** `EV-00280`, with unchanged-interface lower evidence `EV-00190`

## Verdict

**PASS — the remaining A.004/C.001 R8 `partial` statuses were stale status annotations, not
remaining implementation gaps. They are corrected to `full`.**

Architecture §2.9 defines `partial` as “only part of this component's current architectural
obligation is materialized” and requires a concrete missing remainder. It does not mean “this
component owns only one part of a cross-component requirement”.

## Findings and dispositions

### F1 — A.004 used partial to describe bounded ownership rather than missing implementation

**Decision:** accepted  
**Resolution:** fixed

A.004's current R8 obligation is the effective-order contribution after current A.007 evidence.
EV-00280 closes the D.002-generation currentness ordering before that projection. A.004 has no
remaining component-local R8 implementation remainder, so its broad R8 edge is `full`.

### F2 — C.001 used partial for the same reason

**Decision:** accepted  
**Resolution:** fixed

C.001's R8/R8.R1 obligation is the shared lower probe-policy boundary: typed owner separation,
collision-free full-union allocation/convergence and owner-scoped readiness. Those responsibilities
are fully materialized by EV-00200/EV-00210 and now participate in the accepted runtime ordering
proven by EV-00280. D.002 peer/group selection and A.007 Profile evidence are responsibilities of
other components, not missing C.001 work.

Both C.001 R8 and R8.R1 edges therefore become `full`.

### F3 — materialization status must not encode “share of requirement ownership”

**Decision:** accepted  
**Resolution:** fixed

The stale gap paragraphs are replaced by positive materialization statements. This keeps the
anomaly gate meaningful: a future `partial` R8 edge must again identify a real missing piece of
that component's own obligation rather than merely acknowledge that the requirement is
cross-component.

## Closure consequence

Current architecture has no R8-family component edge marked `partial` or `none` because of
generalized WireGuard recovery work. Any remaining unrelated partial edge retains its own
separate gap and is outside this review unit.
