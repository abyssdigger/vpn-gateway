# NG3 EXP-069 stack -> managed-tambour metadata carrier review

**Date:** 2026-11-19  
**Base main:** snapshot 131, `27f7b9c673559d5a756d774b31621e53f71a7f57`  
**Reviewed cycle branch:** `ng3-design-cycle-20261119-boundary-metadata-35m`

## Scope

Review of the EXP-069 setup, privileged evidence and result interpretation for the question
whether an already-selected stack-side behavior class can cross the existing cross-netns veth
into the VPN-GATE-managed tambour without a separate behavior-lane veth.

The review does not reopen accepted product semantics and does not itself change the selected
EXP-064 architecture.

## Requirements

The experiment is traceable to:

- `VPNG-U001-R1.R2.R4.R4.R4`;
- `VPNG-U001-R1.R2.R4.R4.R4.R1`;
- `VPNG-U004-R4.R6.R1.R6`;
- `VPNG-U004-R4.R6.R1.R6.R1`.

No requirement wording was changed by this block.

## Evidence reviewed

Primary evidence run:

- workflow run `44557102092`;
- job `linux-boundary-metadata-carriers` (`135676135049`);
- source commit `d534e49229e0890ed187183411a63e979f47d18f`;
- job conclusion: PASS.

The result-recording head was independently rerun by workflow `44557414550`; its
`linux-boundary-metadata-carriers` job also passed.

The active NG3 workflow remains red only on the already-known unrelated jobs:

- `linux-nft-marked-host-bootstrap` — historical EXP-057 rejected mechanism;
- `linux-profile-gateway-nat-association` — historical EXP-063 rejected mechanism;
- `linux-selected-host-bootstrap-backend` — existing EXP-060 blocker.

`unit` passed on the result-recording head.

## Findings

### 1. The survival result is distinguishing

For every carrier classified as LOST, STACK observed the exact value before the tested veth
boundary while the first managed-tambour observer saw zero matches.

Observed local candidates:

| Candidate | Stack | Tambour | Result |
| --- | ---: | ---: | --- |
| `meta mark` | 8 | 0 | LOST |
| `meta priority` | 8 | 0 | LOST |
| `ct mark` | 1 | 0 | LOST |
| `ct label 69` | 1 | 0 | LOST |
| `ct zone 105` | 1 | 0 | LOST |

This is stronger than inferring carrier loss from an end-to-end connection failure: the TCP
flow itself succeeded, the source-side value was measured, and the receiving side measured
the exact value independently.

### 2. EXP-063 packet-mark evidence reproduced

The `meta mark` control reproduced the previously known EXP-063 shape: stack-side exact
mark observation was non-zero and tambour-side exact observation was zero.

Therefore EXP-069 is consistent with the historical rejected transient packet-mark mechanism.

### 3. The on-wire positive control validates the observation boundary

IPv4 DSCP `0x2e` produced 8 source-side and 8 tambour-side matches. This demonstrates that
the same TCP flow, hooks and exact-match observation can report a value that actually crosses
the boundary.

The negative unmarked flow produced no candidate-counter increase.

Together these controls make "the observer never sees anything" an implausible explanation
for the local-metadata losses.

### 4. NAT/cleanup mechanics are proven for a surviving carrier

For the DSCP positive control, the managed tambour:

1. recognized the exact carrier;
2. stored an internal NAT conntrack class;
3. removed the original carrier before ordinary host route processing;
4. applied MASQUERADE later from the internal class.

The later exact-carrier counter remained zero. LAN observed the host-side source for the
marked flow and the original remote source for the neighboring unmarked flow.

This proves the consume -> internal class -> NAT pattern independently from the choice of
carrier.

### 5. PASS must not be over-generalized

EXP-069 does **not** prove that every possible Linux side channel is impossible.

The following candidates were not available in the direct form required by this experiment:

- `meta pkttype` set: runner/kernel returned operation-not-supported;
- `meta secmark`: unavailable on the runner's security-mark path;
- `meta nftrace`: cannot be used as the required direct exact nft matcher on this target;
- `ct secmark`: cannot be assigned from a constant and its packet-secmark prerequisite was
  unavailable.

The experiment also intentionally excludes explicit encapsulation, VLAN/L2 coding, BPF
flow-map side channels and new physical topology. Those mechanisms would require separate
evidence and have materially different complexity/semantics.

Accordingly the defensible technical statement is:

> No tested direct nft-usable local-only carrier survived the current stack -> managed-tambour
> cross-netns veth boundary.

It is not:

> No possible Linux carrier exists.

### 6. Hygiene guard defect was independent and corrected

The fresh project-governance refactor added the normative
`design/experiments/README.md` runbook, but the active-lineage guard still rejected every
`design/experiments/*` path not contained in a `* NG3 *` dossier directory.

The cycle therefore added the narrow exception for exactly
`design/experiments/README.md`. The subsequent `Actual main lineage guard` run
`44557759705` passed.

This correction changes no experiment or product semantics.

## Verdict

**EXP-069 technical evidence: accepted. No blocking review finding.**

The result supports retaining physical behavior lanes as the current selected fallback for
Release 1, because the tested simpler local metadata carriers did not survive. However this
review does not assign a new project-level `Disposition` and does not rewrite the current
EXP-064 architecture.

Any decision to treat EXP-069 as sufficient reason to close further metadata-carrier search,
or to replace EXP-064 with a different mechanism, remains a separate post-result human
decision.

## Requirement-state inventory

No new requirement-state anomaly was introduced by this block.

- active `unreal`: none observed;
- active `broken`: none observed;
- active `rejected_closure`: none observed;
- historical resolved `decomp` links remain unchanged.
