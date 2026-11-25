# VPN-GATE 0.1.0 release scope

**Version:** `0.1.0`  
**Scope label:** Release-1  
**Status:** `approved`  
**Compatibility role:** `non-binding`  
**Projectholder approval:** 2026-11-24

## Role of this document

This is the release-specific projectholder contract for VPN-GATE 0.1.0.

It does not replace or weaken the normative NG3 Requirement/Constraint tree. Where a Constraint
allows a weaker first release, this document may choose a stronger scope and make that stronger
choice mandatory for 0.1.0.

The release candidate is acceptable only if requirements **and** the commitments below are
satisfied.

## Baseline

The 0.1.0 release frontier includes the current NG3 requirements applicable to Release-1,
except requirements formally outside the active frontier through accepted `postponed` status.

Permanent requirements remain conformance obligations.

## Projectholder scope decisions

### Protective mode is mandatory in 0.1.0

The complete Protective mode family defined by `VPNG-U004-R5*` is included in Release-1 /
0.1.0.

The omission permitted by `VPNG-U004-R5.C1` is **not exercised** for this release.

Therefore 0.1.0 requires, end-to-end:

- explicit authorized enter and exit operations;
- successful enter only after the required protective block is confirmed;
- blocking of ordinary-network -> VPN-GATE, VPN-GATE -> ordinary-network, and VPN-path ->
  VPN-path IP forwarding while the mode is confirmed active;
- preservation of configuration intent, diagnostic/current-state surfaces, and managed runtime
  objects needed for diagnosis and recovery;
- separately identifiable VPN-GATE-owned protective blocking state;
- finite-cadence re-confirmation while Protective mode is requested active;
- repair/re-application of violated protective blocking when exact safe restoration is possible;
- exit only after applicable ordinary desired state is freshly confirmed and protective blocking
  is successfully removed;
- failed/unconfirmed exit must retain the traffic block and expose an explicit problem result.

Any `partial` or `none` materialization of these A.011 commitments is a release blocker for
0.1.0.

## Mandatory published integration walkthrough

Documentation-driven deployment acceptance for 0.1.0 must execute the published
`DEPLOYMENT.md` paths for all three release-supported client integrations:

- WireGuard / wg-quick;
- OpenConnect;
- L2TP / PPP.

For each integration, the walkthrough must install/configure/start it by the published
administrator path, confirm the resulting VPN path through the supported built-in current-state
or diagnostic surface, and prove real Profile payload transfer. Documented lifecycle
stop/restart behavior is part of the walkthrough where the published procedure claims it.

This list is release-specific. It preserves the approved 0.1.0 integration boundary without
making these technology names part of the general release methodology.

## Accepted omissions / deferred scope

The release does not require the aggressive host-routing helper family
`VPNG-U001-R5.R2*`; the omission permitted by `VPNG-U001-R5.R2.C1` **is exercised** for
0.1.0. Existing aggressive-helper implementation/evidence remains outside the Release-1 runtime
scope and does not make its automatic Protective-mode escalation path a 0.1.0 commitment.

The release does not require the runtime-service privilege-minimization family
`VPNG-M001-R5*`; the first-release omission permitted by `VPNG-M001-R5.C1` **is exercised**
for 0.1.0. This omission concerns only the long-running service privilege boundary and does not
change the scope of one-shot installation/upgrade/administrative operations.

The release does not require the formally postponed developer execution trace family
`VPNG-D001-R2*`.

The release does not require the formally postponed Raspberry-Pi-2 resource-envelope acceptance
family `VPNG-M001-R3`, `VPNG-M001-R3.R2`, and `VPNG-M001-R3.R2.R1`.

These exclusions follow current requirement status; they are not newly created omissions.

## Release evidence boundary

Release preparation must provide:

- a complete requirements-coverage matrix evaluated against this scope;
- end-to-end Protective mode evidence covering enter, active blocking, periodic re-confirmation,
  repair after drift, safe exit, and failed-exit retention;
- deployment QA of the actual release bundle for the release-supported integration boundary;
- exact-candidate fulfillment review showing no unresolved scope blocker.

## Approval consequence

This scope was approved before the next release-preparation attempt.

No subsequent release candidate may use `VPNG-U004-R5.C1` to waive Protective mode for
0.1.0 unless the projectholder explicitly revises this document before a new candidate is
prepared.
