# VPN-GATE NG3 — managed L3 endpoint selection review

**Date:** 2026-11-19
**Cycle:** `ng3-design-cycle-20261119-managed-l3-endpoint-35m`

## Scope

Select the Release-1 Linux realization strategy for the primary HOST <-> STACK boundary after
EXP-070/071, while preserving a clean lower-backend seam and without changing Device/Profile
product semantics.

This review also closes the active EXP-060 workflow blocker encountered while validating the
existing selected paired-RPDB host bootstrap.

## Selected architecture

The product-level lower contract is now a **managed L3 endpoint**:

```text
HOST                         STACK
vpng0  <--- lower backend ---> stack endpoint
```

Profile/Device/runtime policy sees the endpoint contract, not a Linux link type.

Release-1 lower selection:

```text
default:    routed veth + Proxy ARP
alternate:  netkit L3
```

The default is deliberately the older implementation because:

- EXP-070 proves the routed-veth/device-only shape on Debian 12 / Linux 6.1;
- it preserves the project's Debian-12 deployment floor;
- EXP-071 found no material steady-state dataplane advantage for netkit;
- veth/Proxy-ARP uses long-established kernel primitives.

Netkit L3 remains a compatible lower backend rather than a different product architecture.
`managed_l3_boundary.py` makes this choice explicit and keeps any override below ordinary
Device/Profile configuration.

## EXP-072 — production bootstrap equivalence

EXP-072 uses the production `build_linux_host_bootstrap_desired` and
`LinuxHostBootstrapBackend` with `inner_gateway=None`.

Both routed-veth/Proxy-ARP and netkit-L3 passed:

- managed `0.0.0.0/0` capture using a device-only boundary route;
- preservation of a strictly-more-specific ordinary `main` route;
- a nested managed prefix overriding a broader ordinary `main` route;
- immediate preservation of a runtime-added more-specific ordinary `/32`;
- stack-ingress bypass preventing recapture;
- actual payload reachability;
- exact cleanup leaving ordinary `main` identical.

Therefore the paired-RPDB bootstrap no longer needs a peer gateway address as part of its
selected lower route representation.

## EXP-060 blocker resolution

Instrumented fresh-postcondition evidence showed that the kernel state was correct. Linux
`ip -j rule` represented a non-/32 prefix as:

```text
dst = bare address
dstlen = prefix length
```

The observer ignored `dstlen`, reconstructed the `/25` as `/32`, and therefore reported its
own correct preserve/dispatch rules as both stale and missing.

The fix changes only authoritative JSON normalization and adds a regression test. No
host-bootstrap policy, RPDB ordering or routing behavior changed. Final EXP-060 privileged
evidence is PASS.

## Deliberate non-changes

### Ordinary-side Profile gateway NAT

EXP-070's stack-side SNAT control does **not** supersede EXP-064 behavior lanes. Its reply path
used an explicit ordinary-side route to the stack NAT source address, so it did not prove the
accepted `+snat` purpose of avoiding route distribution to ordinary hosts.

Therefore:

- EXP-064 remains selected;
- gateway NAT is not moved into STACK by this cycle;
- the four host behavior classes remain authoritative until equivalent replacement evidence
  exists.

### Current alpha physical lifecycle

`managed_network_domain.py` still creates the existing addressed veth (`/30 + peer gateway`)
shape. It is now explicitly transitional. This cycle establishes the replacement contract and
proves the host-bootstrap consumer, but does not claim that alpha lifecycle migration is
complete.

The remaining migration should be staged rather than conflated with this selection:

1. materialize/observe the selected routed-veth + Proxy-ARP primary endpoint in the managed
   domain lifecycle;
2. make the selected stateful-return route consume the same backend-neutral endpoint target;
3. preserve or explicitly separate any stack-local service address needed by local integration
   and publication from the boundary transport representation;
4. only then switch alpha lifecycle end-to-end and retire the transitional `/30 + gateway`
   dependency.

## Final validation

NG3 Python run `44598912456`, final attempt 2:

- `unit`: **PASS**;
- `linux-selected-host-bootstrap-backend` (EXP-060): **PASS**;
- `linux-managed-l3-host-bootstrap` (EXP-072): **PASS**;
- `linux-routed-stack-endpoint` (EXP-070): **PASS**;
- `linux-boundary-dataplane-race` (EXP-071): **PASS**;
- `linux-debian12-routed-veth`: **PASS** on Debian 12 / `6.1.0-56-cloud-amd64`;
- `linux-alpha-smoke`: **PASS**;
- payload/return/behavior-lane integrations touched by the same workflow: **PASS**.

The first Debian-12 job attempt exited from guest setup before evidence markers. An unchanged
rerun completed with `EXP070_D12_RESULT=PASS` and `EXP070_D12_CLOUD_INIT_RC=0`; it is treated
as QEMU/cloud-guest infrastructure flake rather than network evidence.

The workflow conclusion remains red only because it intentionally still executes two historical
negative mechanisms:

- `linux-nft-marked-host-bootstrap` — rejected EXP-057;
- `linux-profile-gateway-nat-association` — rejected EXP-063.

Neither is selected Release-1 machinery and neither regressed in this cycle.
## Requirement impact

No accepted product requirement changes.

The cycle changes Linux architecture/realization only. Existing requirements already describe
explicit owned host-boundary routing contributions and observable gateway-NAT behavior without
requiring a peer gateway IP or a particular virtual-device primitive.

## Requirement-state inventory

### decomp

All accumulated links remain resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT.**

Release 1 selects routed veth + Proxy ARP as the simplest compatible managed-L3-endpoint
backend while retaining netkit L3 as an equivalent alternate lower realization. EXP-072 proves
the common production host-bootstrap semantics, and the previously active EXP-060 blocker is
resolved as an observer normalization defect.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
