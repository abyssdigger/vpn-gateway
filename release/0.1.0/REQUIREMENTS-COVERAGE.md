# VPN-GATE 0.1.0 requirements coverage — release attempt 2

**Release:** `0.1.0`  
**Scope label:** Release-1  
**Approved scope:** `release/0.1.0/RELEASE-SCOPE.md`  
**Normative source:** `design/NG3/requirements.md` (`9bb6cb44ac43f16e78da6f4157a42a15f8ed2753`)  
**Architecture source:** `design/NG3/architecture-ng.md` (`dea03313c96279e158a391dcf74b664a3774ddc8`)  
**Normative nodes:** **220**

## Result

This attempt-2 inventory contains every normative Requirement/Constraint in the current NG3 tree:

- **209** `closed`;
- **8** `postponed` -> `excluded-postponed`;
- **3** `permanent` -> `conformance-applicable`;
- **6** closed aggressive-helper capability nodes -> `excluded-by-approved-scope`;
- **0** `open`;
- **0** `pending_closure`;
- **0** `rejected_closure`.

The approved 0.1.0 scope explicitly **does not exercise** `VPNG-U004-R5.C1`; the complete
Protective-mode family is therefore release-mandatory and is covered by current A.011
materialization/evidence.

The approved scope **does exercise** `VPNG-U001-R5.R2.C1`; the aggressive host-routing helper
capability is therefore excluded from the 0.1.0 runtime frontier even though its accepted
semantics and implementation evidence remain in the project.

No normative node is omitted from this file.

## Interpretation

`covered` means the current accepted requirement closure applies to this release and the
listed current architecture occurrence is its release-specific architecture basis.

`excluded-by-approved-scope` is used only where the normative tree explicitly permits that
release omission and the approved `RELEASE-SCOPE.md` selects it. It is not a requirement-status
change.

`excluded-postponed` preserves the normative postponement and accepted deferral record.

`conformance-applicable` preserves permanent obligations for which finite closure is
inapplicable; the fulfillment review must report any known violation.

## Coverage matrix

| ID | Decomposition | Status | Approved-scope decision | Release disposition | Architecture / status basis | Acceptance / evidence basis |
| --- | --- | --- | --- | --- | --- | --- |
| `VPNG-U001` | `complete` | `closed` | — | `covered` | architecture-ng.md:568 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:568 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1675 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:568 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:2278 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:2065 — [B.001] ManagedL3BoundaryLifecycle | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:2282 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R4` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:2283 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R4.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:2284 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R4.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:2285 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R4.R3` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:2286 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R4.R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:2287 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R4.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:2288 — [C.004] VPNPathAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.C1` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:569 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.C1.R1` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1589 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.C1.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:569 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.C1.R1.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:570 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.C3` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:570 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.C3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:571 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R6` | `complete` | `closed` | — | `covered` | architecture-ng.md:571 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R6.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:572 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R3.R6.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:572 — Managed VPN routing and supported VPN integration | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:617 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R4.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:617 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R4.R2` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:617 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R4.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1735 — [A.005] PayloadPolicyCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R4.R2.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1736 — [A.005] PayloadPolicyCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R1.R4.R2.R1.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:618 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R2` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:2636 — [E.002] HostRoutingContribution | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R2.R1` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:585 — Ordinary-host integration and helper scope | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R2.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:585 — Ordinary-host integration and helper scope | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:643 — Inbound source identity, packet matching and return affinity | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:616 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1580 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1581 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1582 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1584 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R5.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:619 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R5.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:619 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R5.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:620 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R5.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:620 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1583 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R1` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:621 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R1.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:621 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R2` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:622 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:622 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:623 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R4` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:623 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R4.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:624 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R4.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:624 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R4.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:625 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R4.R4.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:625 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:626 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6` | `complete` | `closed` | — | `covered` | architecture-ng.md:626 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:627 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:627 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:628 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R2.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:628 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R2.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:629 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R2.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:629 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R2.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1586 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R2.R5.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:630 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:631 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:631 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R4.R4.R6.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:632 — Human configuration and Device/Profile policy model | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:586 — Ordinary-host integration and helper scope | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R5.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:586 — Ordinary-host integration and helper scope | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R5.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:586 — Ordinary-host integration and helper scope | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U001-R5.R2` | `complete` | `closed` | aggressive host-routing helper omitted; VPNG-U001-R5.R2.C1 exercised for 0.1.0 | `excluded-by-approved-scope` | architecture-ng.md:599 — Aggressive host routing and administrative protective mode | accepted closed semantics retained; release runtime evidence not required by approved 0.1.0 scope |
| `VPNG-U001-R5.R2.R1` | `complete` | `closed` | aggressive host-routing helper omitted; VPNG-U001-R5.R2.C1 exercised for 0.1.0 | `excluded-by-approved-scope` | architecture-ng.md:599 — Aggressive host routing and administrative protective mode | accepted closed semantics retained; release runtime evidence not required by approved 0.1.0 scope |
| `VPNG-U001-R5.R2.R2` | `complete` | `closed` | aggressive host-routing helper omitted; VPNG-U001-R5.R2.C1 exercised for 0.1.0 | `excluded-by-approved-scope` | architecture-ng.md:600 — Aggressive host routing and administrative protective mode | accepted closed semantics retained; release runtime evidence not required by approved 0.1.0 scope |
| `VPNG-U001-R5.R2.R3` | `complete` | `closed` | aggressive host-routing helper omitted; VPNG-U001-R5.R2.C1 exercised for 0.1.0 | `excluded-by-approved-scope` | architecture-ng.md:600 — Aggressive host routing and administrative protective mode | accepted closed semantics retained; release runtime evidence not required by approved 0.1.0 scope |
| `VPNG-U001-R5.R2.R3.R1` | `complete` | `closed` | aggressive host-routing helper omitted; VPNG-U001-R5.R2.C1 exercised for 0.1.0 | `excluded-by-approved-scope` | architecture-ng.md:601 — Aggressive host routing and administrative protective mode | accepted closed semantics retained; release runtime evidence not required by approved 0.1.0 scope |
| `VPNG-U001-R5.R2.R3.R2` | `complete` | `closed` | aggressive host-routing helper omitted; VPNG-U001-R5.R2.C1 exercised for 0.1.0 | `excluded-by-approved-scope` | architecture-ng.md:601 — Aggressive host routing and administrative protective mode | accepted closed semantics retained; release runtime evidence not required by approved 0.1.0 scope |
| `VPNG-U001-R5.R2.C1` | `complete` | `closed` | omission exercised for aggressive helper family in 0.1.0 | `covered` | architecture-ng.md:587 — Ordinary-host integration and helper scope | accepted Constraint + approved RELEASE-SCOPE |
| `VPNG-U002` | `complete` | `closed` | — | `covered` | architecture-ng.md:654 — Explicit VPN traffic policy and inbound first-release bound | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:654 — Explicit VPN traffic policy and inbound first-release bound | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1590 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1738 — [A.005] PayloadPolicyCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R1.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1739 — [A.005] PayloadPolicyCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R1.R3` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:643 — Inbound source identity, packet matching and return affinity | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1591 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R2.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:654 — Explicit VPN traffic policy and inbound first-release bound | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1741 — [A.005] PayloadPolicyCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1592 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R3.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1743 — [A.005] PayloadPolicyCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R3.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:655 — Explicit VPN traffic policy and inbound first-release bound | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R3.C1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:655 — Explicit VPN traffic policy and inbound first-release bound | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1593 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R5` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1594 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U002-R2.R5.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1746 — [A.005] PayloadPolicyCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003` | `complete` | `closed` | — | `covered` | architecture-ng.md:665 — Multi-path preference and availability adaptation | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:665 — Multi-path preference and availability adaptation | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1681 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:665 — Multi-path preference and availability adaptation | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1682 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:666 — Multi-path preference and availability adaptation | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1683 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R4` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1684 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R4.R1` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1785 — [A.006] AvailabilityPriorityCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R4.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1786 — [A.006] AvailabilityPriorityCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1685 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R5.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:666 — Multi-path preference and availability adaptation | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R5.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:666 — Multi-path preference and availability adaptation | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6` | `complete` | `closed` | — | `covered` | architecture-ng.md:1819 — [A.007] AvailabilityProbeAgent | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1634 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1821 — [A.007] AvailabilityProbeAgent | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1822 — [A.007] AvailabilityProbeAgent | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1635 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1636 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1637 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1.R1.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1638 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1.R1.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1639 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1.R1.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1640 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:667 — Multi-path preference and availability adaptation | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R1.C2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1647 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R6.R3.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1641 — [A.003] AvailabilityDescriptionResolver | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R7` | `complete` | `closed` | — | `covered` | architecture-ng.md:1686 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R8` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1788 — [A.006] AvailabilityPriorityCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R8.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1789 — [A.006] AvailabilityPriorityCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R8.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1790 — [A.006] AvailabilityPriorityCalculator | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R3.R9` | `complete` | `closed` | — | `covered` | architecture-ng.md:2231 — [C.003] NetworkPolicyEnforcer | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U003-R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:644 — Inbound source identity, packet matching and return affinity | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004` | `complete` | `closed` | — | `covered` | architecture-ng.md:677 — Safety, recovery and operator truth | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1687 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1595 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1689 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4.R3` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:2122 — [C.001] NetworkPolicyAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4.R3.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:2232 — [C.003] NetworkPolicyEnforcer | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1511 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1512 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R4.R6` | `complete` | `closed` | — | `covered` | architecture-ng.md:677 — Safety, recovery and operator truth | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-U004-R5` | `complete` | `closed` | Protective mode mandatory; VPNG-U004-R5.C1 omission not exercised | `covered` | architecture-ng.md:602 — Aggressive host routing and administrative protective mode | accepted closure + current full A.011 materialization + Protective Linux/release-bundle QA |
| `VPNG-U004-R5.R1` | `complete` | `closed` | Protective mode mandatory; VPNG-U004-R5.C1 omission not exercised | `covered` | architecture-ng.md:602 — Aggressive host routing and administrative protective mode | accepted closure + current full A.011 materialization + Protective Linux/release-bundle QA |
| `VPNG-U004-R5.R2` | `complete` | `closed` | Protective mode mandatory; VPNG-U004-R5.C1 omission not exercised | `covered` | architecture-ng.md:602 — Aggressive host routing and administrative protective mode | accepted closure + current full A.011 materialization + Protective Linux/release-bundle QA |
| `VPNG-U004-R5.R3` | `complete` | `closed` | Protective mode mandatory; VPNG-U004-R5.C1 omission not exercised | `covered` | architecture-ng.md:603 — Aggressive host routing and administrative protective mode | accepted closure + current full A.011 materialization + Protective Linux/release-bundle QA |
| `VPNG-U004-R5.R4` | `complete` | `closed` | Protective mode mandatory; VPNG-U004-R5.C1 omission not exercised | `covered` | architecture-ng.md:603 — Aggressive host routing and administrative protective mode | accepted closure + current full A.011 materialization + Protective Linux/release-bundle QA |
| `VPNG-U004-R5.C1` | `complete` | `closed` | Protective mode mandatory; VPNG-U004-R5.C1 omission not exercised | `covered` | architecture-ng.md:678 — Safety, recovery and operator truth | accepted closure + current full A.011 materialization + Protective Linux/release-bundle QA |
| `VPNG-D001` | `incomplete` | `permanent` | — | `conformance-applicable` | permanent-status integrity + current architecture/implementation conformance | finite closure N/A; fulfillment review checks for known violation |
| `VPNG-D001-R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:692 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:692 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R1` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:541 — 2.9.4. Deliberately omitted machinery | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1865 — [A.008] RuntimeStatusAgent | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:692 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1695 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1596 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R3.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1597 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R3.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:2072 — [B.001] ManagedL3BoundaryLifecycle | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R3.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:693 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R3.R4` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:693 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R3.R4.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:694 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:694 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1598 — [A.002] ConfigurationAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R6` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1697 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R6.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:695 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R6.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:695 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R7` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:2073 — [B.001] ManagedL3BoundaryLifecycle | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R7.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:696 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R8` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:2641 — [E.002] HostRoutingContribution | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R8.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:533 — 2.9.3. Target production-runtime language boundary | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R8.C2` | `complete` | `closed` | — | `covered` | architecture-ng.md:533 — 2.9.3. Target production-runtime language boundary | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R8.C3` | `complete` | `closed` | — | `covered` | architecture-ng.md:533 — 2.9.3. Target production-runtime language boundary | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R8.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:514 — 2.9.3. Target production-runtime language boundary | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R8.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:514 — 2.9.3. Target production-runtime language boundary | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R1.R1.R8.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:2645 — [E.002] HostRoutingContribution | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R2` | `complete` | `postponed` | approved scope confirms developer execution trace remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-developer-execution-trace.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
| `VPNG-D001-R2.R1` | `incomplete` | `postponed` | approved scope confirms developer execution trace remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-developer-execution-trace.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
| `VPNG-D001-R2.R2` | `incomplete` | `postponed` | approved scope confirms developer execution trace remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-developer-execution-trace.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
| `VPNG-D001-R2.R3` | `incomplete` | `postponed` | approved scope confirms developer execution trace remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-developer-execution-trace.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
| `VPNG-D001-R2.R4` | `incomplete` | `postponed` | approved scope confirms developer execution trace remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-developer-execution-trace.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
| `VPNG-D001-R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:697 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:697 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R3.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:698 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R3.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:698 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R3.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:698 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-D001-R3.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:699 — Maintainability, continuity, evidence and development boundaries | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001` | `incomplete` | `permanent` | — | `conformance-applicable` | permanent-status integrity + current architecture/implementation conformance | finite closure N/A; fulfillment review checks for known violation |
| `VPNG-M001-R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1513 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1514 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1515 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R2` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1690 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:678 — Safety, recovery and operator truth | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R3` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1516 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:679 — Safety, recovery and operator truth | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1517 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1518 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.C1` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1529 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.C1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:679 — Safety, recovery and operator truth | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R6` | `incomplete` | `closed` | — | `covered` | architecture-ng.md:1519 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R6.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1520 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R6.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1521 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R1.R1.R6.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1522 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:679 — Safety, recovery and operator truth | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1859 — [A.008] RuntimeStatusAgent | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R1.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1860 — [A.008] RuntimeStatusAgent | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R1.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1692 — [A.004] PayloadTrafficManager | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R1.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1523 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R1.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1524 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R1.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1525 — [A.001] ProductLifecycleControl | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1904 — [A.009] RuntimeStatusTextRenderer | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1905 — [A.009] RuntimeStatusTextRenderer | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R2.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1906 — [A.009] RuntimeStatusTextRenderer | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R2.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1907 — [A.009] RuntimeStatusTextRenderer | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R2.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1908 — [A.009] RuntimeStatusTextRenderer | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1939 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1940 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1941 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R2.R1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1942 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R2.R2` | `complete` | `closed` | — | `covered` | architecture-ng.md:1943 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R2.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1944 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R2.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1945 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R3` | `complete` | `closed` | — | `covered` | architecture-ng.md:1946 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R4` | `complete` | `closed` | — | `covered` | architecture-ng.md:1947 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R5` | `complete` | `closed` | — | `covered` | architecture-ng.md:1948 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R6` | `complete` | `closed` | — | `covered` | architecture-ng.md:1949 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R2.R3.R6.C1` | `complete` | `closed` | — | `covered` | architecture-ng.md:1950 — [A.010] OperationalLogAdapter | accepted closure + current architecture/traceability; release QA where runtime-applicable |
| `VPNG-M001-R3` | `incomplete` | `postponed` | approved scope confirms Raspberry-Pi-2 resource-evidence family remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-raspberry-pi2-resource-envelope.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
| `VPNG-M001-R3.R1` | `complete` | `permanent` | — | `conformance-applicable` | permanent-status integrity + current architecture/implementation conformance | finite closure N/A; fulfillment review checks for known violation |
| `VPNG-M001-R3.R2` | `incomplete` | `postponed` | approved scope confirms Raspberry-Pi-2 resource-evidence family remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-raspberry-pi2-resource-envelope.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
| `VPNG-M001-R3.R2.R1` | `incomplete` | `postponed` | approved scope confirms Raspberry-Pi-2 resource-evidence family remains outside 0.1.0 | `excluded-postponed` | design/deferrals/NG3-raspberry-pi2-resource-envelope.md + approved RELEASE-SCOPE | accepted postponement; finite closure evidence not applicable while postponed |
