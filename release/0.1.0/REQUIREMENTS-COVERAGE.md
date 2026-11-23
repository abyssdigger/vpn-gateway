# VPN-GATE 0.1.0 requirements coverage

**Release:** `0.1.0`  
**Scope label:** Release-1  
**Normative source:** `design/NG3/requirements.md`  
**Architecture source:** `design/NG3/architecture-ng.md`  
**Normative nodes:** **220**

## Result

The release coverage inventory contains every normative Requirement/Constraint in the current
NG3 tree:

- **209** `closed` -> `covered`;
- **8** `postponed` -> `excluded-postponed`;
- **3** `permanent` -> `conformance-applicable`;
- **0** `open`;
- **0** `pending_closure`;
- **0** `rejected_closure`.

No normative node is omitted from this file.

## Evidence interpretation

For a `closed` row, `covered` means that the normative tree carries accepted closure and
the listed exact architecture occurrence is the release-specific architecture basis. The
project-wide traceability evidence is
`design/reviews/NG3-2026-11-23-requirements-architecture-code-traceability-review.md`.
Executable release conformance is additionally exercised by `release/0.1.0/QA-REPORT.md`
where the requirement has runtime/deployment behavior.

For a `postponed` row, the listed deferral record plus
`design/reviews/NG3-2026-11-22-postponed-status-constraint-review.md` is the basis for
excluding the node from the current release frontier. Existing coincidental implementation does
not change that disposition.

For a `permanent` row, finite closure evidence is not applicable by
`design/requirements-model.md`. Release treatment is conformance-only; integrity of these
statuses was accepted in
`design/reviews/NG3-2026-11-22-requirement-status-permanent-integrity-review.md`, and the
release fulfillment review must report any known violation.

## Coverage matrix

| ID | Decomposition | Status | Release disposition | Architecture / status basis |
| --- | --- | --- | --- | --- |
| `VPNG-U001` | `complete` | `closed` | `covered` | `architecture-ng.md:568` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1` | `complete` | `closed` | `covered` | `architecture-ng.md:568` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1675` — [A.004] PayloadTrafficManager |
| `VPNG-U001-R1.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:568` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:2271` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:2058` — [B.001] ManagedL3BoundaryLifecycle |
| `VPNG-U001-R1.R3.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:2275` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.R4` | `incomplete` | `closed` | `covered` | `architecture-ng.md:2276` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.R4.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:2277` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.R4.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:2278` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.R4.R3` | `incomplete` | `closed` | `covered` | `architecture-ng.md:2279` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.R4.R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:2280` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.R4.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:2281` — [C.004] VPNPathAdapter |
| `VPNG-U001-R1.R3.C1` | `incomplete` | `closed` | `covered` | `architecture-ng.md:569` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.C1.R1` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1589` — [A.002] ConfigurationAdapter |
| `VPNG-U001-R1.R3.C1.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:569` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.C1.R1.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:570` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.C3` | `incomplete` | `closed` | `covered` | `architecture-ng.md:570` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.C3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:571` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.R6` | `complete` | `closed` | `covered` | `architecture-ng.md:571` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.R6.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:572` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R3.R6.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:572` — Managed VPN routing and supported VPN integration |
| `VPNG-U001-R1.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:617` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R1.R4.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:617` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R1.R4.R2` | `incomplete` | `closed` | `covered` | `architecture-ng.md:617` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R1.R4.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1735` — [A.005] PayloadPolicyCalculator |
| `VPNG-U001-R1.R4.R2.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1736` — [A.005] PayloadPolicyCalculator |
| `VPNG-U001-R1.R4.R2.R1.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:618` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R2` | `incomplete` | `closed` | `covered` | `architecture-ng.md:2629` — [E.002] HostRoutingContribution |
| `VPNG-U001-R2.R1` | `incomplete` | `closed` | `covered` | `architecture-ng.md:585` — Ordinary-host integration and helper scope |
| `VPNG-U001-R2.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:585` — Ordinary-host integration and helper scope |
| `VPNG-U001-R3` | `complete` | `closed` | `covered` | `architecture-ng.md:643` — Inbound source identity, packet matching and return affinity |
| `VPNG-U001-R4` | `complete` | `closed` | `covered` | `architecture-ng.md:616` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1580` — [A.002] ConfigurationAdapter |
| `VPNG-U001-R4.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1581` — [A.002] ConfigurationAdapter |
| `VPNG-U001-R4.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1582` — [A.002] ConfigurationAdapter |
| `VPNG-U001-R4.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1584` — [A.002] ConfigurationAdapter |
| `VPNG-U001-R4.R5.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:619` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R5.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:619` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R5.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:620` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R5.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:620` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1583` — [A.002] ConfigurationAdapter |
| `VPNG-U001-R4.R4.R1` | `incomplete` | `closed` | `covered` | `architecture-ng.md:621` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R1.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:621` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R2` | `incomplete` | `closed` | `covered` | `architecture-ng.md:622` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:622` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:623` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R4` | `incomplete` | `closed` | `covered` | `architecture-ng.md:623` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R4.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:624` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R4.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:624` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R4.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:625` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R4.R4.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:625` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:626` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6` | `complete` | `closed` | `covered` | `architecture-ng.md:626` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:627` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:627` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:628` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R2.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:628` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R2.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:629` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R2.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:629` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R2.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1586` — [A.002] ConfigurationAdapter |
| `VPNG-U001-R4.R4.R6.R2.R5.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:630` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:631` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:631` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R4.R4.R6.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:632` — Human configuration and Device/Profile policy model |
| `VPNG-U001-R5` | `complete` | `closed` | `covered` | `architecture-ng.md:586` — Ordinary-host integration and helper scope |
| `VPNG-U001-R5.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:586` — Ordinary-host integration and helper scope |
| `VPNG-U001-R5.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:586` — Ordinary-host integration and helper scope |
| `VPNG-U001-R5.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:599` — Aggressive host routing and administrative protective mode |
| `VPNG-U001-R5.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:599` — Aggressive host routing and administrative protective mode |
| `VPNG-U001-R5.R2.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:600` — Aggressive host routing and administrative protective mode |
| `VPNG-U001-R5.R2.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:600` — Aggressive host routing and administrative protective mode |
| `VPNG-U001-R5.R2.R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:601` — Aggressive host routing and administrative protective mode |
| `VPNG-U001-R5.R2.R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:601` — Aggressive host routing and administrative protective mode |
| `VPNG-U001-R5.R2.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:587` — Ordinary-host integration and helper scope |
| `VPNG-U002` | `complete` | `closed` | `covered` | `architecture-ng.md:654` — Explicit VPN traffic policy and inbound first-release bound |
| `VPNG-U002-R2` | `complete` | `closed` | `covered` | `architecture-ng.md:654` — Explicit VPN traffic policy and inbound first-release bound |
| `VPNG-U002-R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1590` — [A.002] ConfigurationAdapter |
| `VPNG-U002-R2.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1738` — [A.005] PayloadPolicyCalculator |
| `VPNG-U002-R2.R1.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1739` — [A.005] PayloadPolicyCalculator |
| `VPNG-U002-R2.R1.R3` | `incomplete` | `closed` | `covered` | `architecture-ng.md:643` — Inbound source identity, packet matching and return affinity |
| `VPNG-U002-R2.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1591` — [A.002] ConfigurationAdapter |
| `VPNG-U002-R2.R2.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:654` — Explicit VPN traffic policy and inbound first-release bound |
| `VPNG-U002-R2.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1741` — [A.005] PayloadPolicyCalculator |
| `VPNG-U002-R2.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1592` — [A.002] ConfigurationAdapter |
| `VPNG-U002-R2.R3.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1743` — [A.005] PayloadPolicyCalculator |
| `VPNG-U002-R2.R3.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:655` — Explicit VPN traffic policy and inbound first-release bound |
| `VPNG-U002-R2.R3.C1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:655` — Explicit VPN traffic policy and inbound first-release bound |
| `VPNG-U002-R2.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1593` — [A.002] ConfigurationAdapter |
| `VPNG-U002-R2.R5` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1594` — [A.002] ConfigurationAdapter |
| `VPNG-U002-R2.R5.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1746` — [A.005] PayloadPolicyCalculator |
| `VPNG-U003` | `complete` | `closed` | `covered` | `architecture-ng.md:665` — Multi-path preference and availability adaptation |
| `VPNG-U003-R3` | `complete` | `closed` | `covered` | `architecture-ng.md:665` — Multi-path preference and availability adaptation |
| `VPNG-U003-R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1681` — [A.004] PayloadTrafficManager |
| `VPNG-U003-R3.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:665` — Multi-path preference and availability adaptation |
| `VPNG-U003-R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1682` — [A.004] PayloadTrafficManager |
| `VPNG-U003-R3.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:666` — Multi-path preference and availability adaptation |
| `VPNG-U003-R3.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1683` — [A.004] PayloadTrafficManager |
| `VPNG-U003-R3.R4` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1684` — [A.004] PayloadTrafficManager |
| `VPNG-U003-R3.R4.R1` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1785` — [A.006] AvailabilityPriorityCalculator |
| `VPNG-U003-R3.R4.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1786` — [A.006] AvailabilityPriorityCalculator |
| `VPNG-U003-R3.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1685` — [A.004] PayloadTrafficManager |
| `VPNG-U003-R3.R5.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:666` — Multi-path preference and availability adaptation |
| `VPNG-U003-R3.R5.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:666` — Multi-path preference and availability adaptation |
| `VPNG-U003-R3.R6` | `complete` | `closed` | `covered` | `architecture-ng.md:1819` — [A.007] AvailabilityProbeAgent |
| `VPNG-U003-R3.R6.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1634` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1821` — [A.007] AvailabilityProbeAgent |
| `VPNG-U003-R3.R6.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1822` — [A.007] AvailabilityProbeAgent |
| `VPNG-U003-R3.R6.R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1635` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R3.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1636` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R3.R1.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1637` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R3.R1.R1.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1638` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R3.R1.R1.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1639` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R3.R1.R1.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1640` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R3.R1.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:667` — Multi-path preference and availability adaptation |
| `VPNG-U003-R3.R6.R3.R1.C2` | `complete` | `closed` | `covered` | `architecture-ng.md:1647` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R6.R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1641` — [A.003] AvailabilityDescriptionResolver |
| `VPNG-U003-R3.R7` | `complete` | `closed` | `covered` | `architecture-ng.md:1686` — [A.004] PayloadTrafficManager |
| `VPNG-U003-R3.R8` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1788` — [A.006] AvailabilityPriorityCalculator |
| `VPNG-U003-R3.R8.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1789` — [A.006] AvailabilityPriorityCalculator |
| `VPNG-U003-R3.R8.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:1790` — [A.006] AvailabilityPriorityCalculator |
| `VPNG-U003-R3.R9` | `complete` | `closed` | `covered` | `architecture-ng.md:2224` — [C.003] NetworkPolicyEnforcer |
| `VPNG-U003-R4` | `complete` | `closed` | `covered` | `architecture-ng.md:644` — Inbound source identity, packet matching and return affinity |
| `VPNG-U004` | `complete` | `closed` | `covered` | `architecture-ng.md:677` — Safety, recovery and operator truth |
| `VPNG-U004-R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1687` — [A.004] PayloadTrafficManager |
| `VPNG-U004-R4.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1595` — [A.002] ConfigurationAdapter |
| `VPNG-U004-R4.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1689` — [A.004] PayloadTrafficManager |
| `VPNG-U004-R4.R3` | `incomplete` | `closed` | `covered` | `architecture-ng.md:2115` — [C.001] NetworkPolicyAdapter |
| `VPNG-U004-R4.R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:2225` — [C.003] NetworkPolicyEnforcer |
| `VPNG-U004-R4.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1511` — [A.001] ProductLifecycleControl |
| `VPNG-U004-R4.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1512` — [A.001] ProductLifecycleControl |
| `VPNG-U004-R4.R6` | `complete` | `closed` | `covered` | `architecture-ng.md:677` — Safety, recovery and operator truth |
| `VPNG-U004-R5` | `complete` | `closed` | `covered` | `architecture-ng.md:602` — Aggressive host routing and administrative protective mode |
| `VPNG-U004-R5.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:602` — Aggressive host routing and administrative protective mode |
| `VPNG-U004-R5.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:602` — Aggressive host routing and administrative protective mode |
| `VPNG-U004-R5.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:603` — Aggressive host routing and administrative protective mode |
| `VPNG-U004-R5.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:603` — Aggressive host routing and administrative protective mode |
| `VPNG-U004-R5.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:678` — Safety, recovery and operator truth |
| `VPNG-D001` | `incomplete` | `permanent` | `conformance-applicable` | finite closure N/A; permanent-status integrity review + release conformance check |
| `VPNG-D001-R1` | `complete` | `closed` | `covered` | `architecture-ng.md:692` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:692` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R1` | `incomplete` | `closed` | `covered` | `architecture-ng.md:541` — 2.9.4. Deliberately omitted machinery |
| `VPNG-D001-R1.R1.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1865` — [A.008] RuntimeStatusAgent |
| `VPNG-D001-R1.R1.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:692` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1695` — [A.004] PayloadTrafficManager |
| `VPNG-D001-R1.R1.R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1596` — [A.002] ConfigurationAdapter |
| `VPNG-D001-R1.R1.R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1597` — [A.002] ConfigurationAdapter |
| `VPNG-D001-R1.R1.R3.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:2065` — [B.001] ManagedL3BoundaryLifecycle |
| `VPNG-D001-R1.R1.R3.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:693` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R3.R4` | `incomplete` | `closed` | `covered` | `architecture-ng.md:693` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R3.R4.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:694` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:694` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1598` — [A.002] ConfigurationAdapter |
| `VPNG-D001-R1.R1.R6` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1697` — [A.004] PayloadTrafficManager |
| `VPNG-D001-R1.R1.R6.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:695` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R6.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:695` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R7` | `incomplete` | `closed` | `covered` | `architecture-ng.md:2066` — [B.001] ManagedL3BoundaryLifecycle |
| `VPNG-D001-R1.R1.R7.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:696` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R1.R1.R8` | `incomplete` | `closed` | `covered` | `architecture-ng.md:2634` — [E.002] HostRoutingContribution |
| `VPNG-D001-R1.R1.R8.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:533` — 2.9.3. Target production-runtime language boundary |
| `VPNG-D001-R1.R1.R8.C2` | `complete` | `closed` | `covered` | `architecture-ng.md:533` — 2.9.3. Target production-runtime language boundary |
| `VPNG-D001-R1.R1.R8.C3` | `complete` | `closed` | `covered` | `architecture-ng.md:533` — 2.9.3. Target production-runtime language boundary |
| `VPNG-D001-R1.R1.R8.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:514` — 2.9.3. Target production-runtime language boundary |
| `VPNG-D001-R1.R1.R8.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:514` — 2.9.3. Target production-runtime language boundary |
| `VPNG-D001-R1.R1.R8.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:2638` — [E.002] HostRoutingContribution |
| `VPNG-D001-R2` | `complete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-developer-execution-trace.md`; postponed-status review |
| `VPNG-D001-R2.R1` | `incomplete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-developer-execution-trace.md`; postponed-status review |
| `VPNG-D001-R2.R2` | `incomplete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-developer-execution-trace.md`; postponed-status review |
| `VPNG-D001-R2.R3` | `incomplete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-developer-execution-trace.md`; postponed-status review |
| `VPNG-D001-R2.R4` | `incomplete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-developer-execution-trace.md`; postponed-status review |
| `VPNG-D001-R3` | `complete` | `closed` | `covered` | `architecture-ng.md:697` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:697` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R3.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:698` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:698` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R3.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:698` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-D001-R3.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:699` — Maintainability, continuity, evidence and development boundaries |
| `VPNG-M001` | `incomplete` | `permanent` | `conformance-applicable` | finite closure N/A; permanent-status integrity review + release conformance check |
| `VPNG-M001-R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1513` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1514` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1515` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.R2` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1690` — [A.004] PayloadTrafficManager |
| `VPNG-M001-R1.R1.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:678` — Safety, recovery and operator truth |
| `VPNG-M001-R1.R1.R3` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1516` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:679` — Safety, recovery and operator truth |
| `VPNG-M001-R1.R1.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1517` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1518` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.C1` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1529` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.C1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:679` — Safety, recovery and operator truth |
| `VPNG-M001-R1.R1.R6` | `incomplete` | `closed` | `covered` | `architecture-ng.md:1519` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.R6.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1520` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.R6.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1521` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R1.R1.R6.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1522` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R2` | `complete` | `closed` | `covered` | `architecture-ng.md:679` — Safety, recovery and operator truth |
| `VPNG-M001-R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1859` — [A.008] RuntimeStatusAgent |
| `VPNG-M001-R2.R1.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1860` — [A.008] RuntimeStatusAgent |
| `VPNG-M001-R2.R1.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1692` — [A.004] PayloadTrafficManager |
| `VPNG-M001-R2.R1.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1523` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R2.R1.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1524` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R2.R1.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1525` — [A.001] ProductLifecycleControl |
| `VPNG-M001-R2.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1904` — [A.009] RuntimeStatusTextRenderer |
| `VPNG-M001-R2.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1905` — [A.009] RuntimeStatusTextRenderer |
| `VPNG-M001-R2.R2.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1906` — [A.009] RuntimeStatusTextRenderer |
| `VPNG-M001-R2.R2.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1907` — [A.009] RuntimeStatusTextRenderer |
| `VPNG-M001-R2.R2.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1908` — [A.009] RuntimeStatusTextRenderer |
| `VPNG-M001-R2.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1939` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1940` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1941` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R2.R1` | `complete` | `closed` | `covered` | `architecture-ng.md:1942` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R2.R2` | `complete` | `closed` | `covered` | `architecture-ng.md:1943` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R2.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1944` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R2.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1945` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R3` | `complete` | `closed` | `covered` | `architecture-ng.md:1946` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R4` | `complete` | `closed` | `covered` | `architecture-ng.md:1947` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R5` | `complete` | `closed` | `covered` | `architecture-ng.md:1948` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R6` | `complete` | `closed` | `covered` | `architecture-ng.md:1949` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R2.R3.R6.C1` | `complete` | `closed` | `covered` | `architecture-ng.md:1950` — [A.010] OperationalLogAdapter |
| `VPNG-M001-R3` | `incomplete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-raspberry-pi2-resource-envelope.md`; postponed-status review |
| `VPNG-M001-R3.R1` | `complete` | `permanent` | `conformance-applicable` | finite closure N/A; permanent-status integrity review + release conformance check |
| `VPNG-M001-R3.R2` | `incomplete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-raspberry-pi2-resource-envelope.md`; postponed-status review |
| `VPNG-M001-R3.R2.R1` | `incomplete` | `postponed` | `excluded-postponed` | `design/deferrals/NG3-raspberry-pi2-resource-envelope.md`; postponed-status review |
