# VPN-GATE NG3 — Design Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261115-40m`  
**CYCLE_INTERVAL:** 40m  
**Cycle type:** design-only / requirements-first  
**Checkpoint reason:** Git commit elapsed time exceeded `CYCLE_INTERVAL`; current review unit is complete.

## Cycle clock

```text
CYCLE_START_COMMIT:
4b3785b5c228782768afe317d4f09386fd46b440
2026-11-15T18:14:07Z
NG3: establish initial requirement tree

last content head before checkpoint:
b91ce8a754b030a12e27d9a17857578e23532548
2026-11-15T20:24:36Z
NG3: refresh review after compact requirements and VPN channel gate

elapsed to last content head:
2h 10m 29s
```

The commit that adds this checkpoint file is the final checkpoint commit for this cycle unit;
its authoritative SHA/timestamp is obtained from GitHub branch history.

## Completed

- established NG3 requirement-first baseline without automatic NG2 architecture inheritance;
- accepted seven L1 requirements;
- decomposed core payload, policy, availability, safety, lifecycle, observability and
  implementation-quality requirements;
- added explicit first-release VPN-channel ownership chain:
  - `VPNG-R1.R3` — VPN-GATE consumes supported VPN channels as paths;
  - `VPNG-R1.R3.C1` — administrator provisions/configures the VPN channel in release 1;
  - `VPNG-R1.R3.C1.R1` — VPN-GATE must provide the onboarding instructions/contract;
- converted the requirement document to compact one-line normative form:
  `**[ID]** Purpose/Reason | Statement`;
- derived the first partial NG3 architecture strictly from requirement references;
- deliberately kept active probing as architecture rather than product requirement;
- separated availability product semantics from bounded-state implementation quality;
- reconciled the mandatory NG2 handoff as historical evidence rather than inherited design;
- updated architecture to reflect the administrator-provisioned VPN-channel boundary;
- completed initial whole-scope NG3 requirements/architecture review.

## Evidence

Mechanical requirement-format check:

```text
requirement/constraint lines: 55
unique IDs:                   55
malformed normative lines:     0
```

Mechanical architecture traceability check:

```text
architecture references:       177
unique referenced IDs:          51
missing/broken IDs:              0
```

No code was implemented in this cycle, so no runtime/unit/kernel test gate was required.

## Review result

Initial review:

```text
design/reviews/NG3-2026-11-15-initial-requirements-architecture-review.md
```

Verdict: PASS for the first requirement-first NG3 architecture review unit, with explicit
remaining requirement/design gaps.

## Human decisions resolved in this unit

The first-release VPN-channel ownership gate was explicitly resolved:

- VPN-GATE must be able to consume/manage supported VPN channels as paths;
- the administrator deploys and performs basic VPN configuration in release 1;
- VPN-GATE must document/provide the contract required to make such a channel visible and
  usable.

No VPN-session provisioning Manager is therefore justified for the first release.

## Still open

The following are visible requirements/design gaps rather than silently invented architecture:

- exact administrator-facing VPN-channel onboarding identity/contract and instructions;
- authoritative user configuration vocabulary and normalization boundary;
- exact availability negative-evidence / threshold semantics;
- complete system-wide status aggregation/presentation;
- concrete lower network-policy transition algorithm;
- complete startup/cleanup ownership map;
- deployment/environment constraints not yet explicitly accepted.

## Next intended review unit

After the next user turn, start a new autonomous cycle and refine the externally provisioned
VPN-channel onboarding/configuration contract first, because it connects the newly accepted
`VPNG-R1.R3.C1.R1` boundary to configuration, observability and later concrete architecture.

Do not invent a tunnel/session Manager unless a later requirement explicitly moves VPN
provisioning into VPN-GATE.
