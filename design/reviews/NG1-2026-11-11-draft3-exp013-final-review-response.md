# Response to NG1 Draft 3 + EXP-013 final review

Disposition: **accepted; C1 fixed; minor observations incorporated.**

## C1 — explicit NEW verdicts

Accepted as a real fail-open materialization risk.

Draft 4 now requires an explicit NEW verdict for every enabled
`(Profile, Device, remote-prefix)` pair in both relevant directions. The verdict is
`ACCEPT` or `DROP` according to `Profile.direction`; omission is not a valid
representation of denial.

Generated NEW verdicts are ordered longest-prefix-first. The architecture now includes the
shared-Device overlapping-prefix counterexample for both Device→host and host→Device
semantics.

A rootless `firewall_intent` projector and regression tests implement the same rule,
including both reviewer counterexamples.

## Operational multipath observation

Accepted. Draft 4 explicitly records that disappearance of any member of a materialized
fallback multipath requires full Profile-route reprojection under the protective barrier.
Traffic fails closed during the transition even if another member remains healthy.

## D1 — CHANGELOG

Accepted. A newest-first entry records both EXP-013 closure and Draft 4.

## D2 — persistent shadow example

Accepted. §12 now shows the concrete three-member case: three normal routes, one common
shadow ECMP fallback at 65535, and terminal blackhole at 65536.

## Baseline

After these changes, **NG1 Architecture Draft 4** is the production implementation
baseline. EXP-013 is closed PASS and no longer gates unavailable-path projection.
