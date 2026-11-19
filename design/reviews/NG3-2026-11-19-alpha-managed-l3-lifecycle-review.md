# VPN-GATE NG3 — alpha managed-L3 lifecycle migration review

**Date:** 2026-11-19
**Cycle:** `ng3-design-cycle-20261119-alpha-managed-l3-lifecycle-35m`

## Scope

Migrate the real Release-1 alpha primary HOST <-> STACK lifecycle from the historical
addressed `/30 + peer gateway` veth to the selected managed-L3 endpoint contract, while
keeping the lower backend seam compatible with the already-selected future netkit-L3
alternative.

Ordinary-side Profile gateway NAT / EXP-064 behavior lanes are explicitly outside this cycle.

## Runtime shape after migration

Alpha now constructs:

```text
HOST
    vnga-host0                 unnumbered routed veth
    198.19.255.2/32 dev vnga-host0
          ||
          || Proxy ARP / routed L3 boundary
          ||
STACK (vpn-gate-alpha)
    vnga-inner0 198.19.255.2/32
    default dev vnga-inner0
```

`198.19.255.2/32` is the stack-local service address used by managed local integration and
publication. It is no longer a next-hop/gateway identity.

The host endpoint has no IPv4 address. The selected routed-veth backend owns exact
`proxy_arp=1` and `rp_filter=0` state on both boundary endpoints. The managed-domain lifecycle
observes and verifies these facts together with reciprocal veth identity, the stack-local
`/32`, the host service route and the stack device-only default.

## Host routing consumers

### Paired-RPDB bootstrap

`HostBootstrapRouteSpec.via` already became optional in the preceding CD. The selected alpha
boundary now passes the backend-neutral `host_boundary_gateway`, which is `None` for the
routed primary endpoint.

Therefore selected bootstrap routes are physically:

```text
<managed-prefix> dev vnga-host0 table <bootstrap-table>
```

with no peer gateway. EXP-072 already proved the routing semantics; the migrated EXP-051 alpha
smoke proves that the installed systemd runtime actually uses this representation.

### Stateful return

`HostBoundaryRouteSpec` and `HostBoundaryReturnRouteSpec` now also admit `via=None`; the Linux
route Driver and authoritative observers render/compare that device-only form.

The selected stateful return table is therefore:

```text
default dev vnga-host0 table <return-table>
```

EXP-073 proves the production desired-state compiler, route-dependency convergence and nft
return owner with this shape for both forwarded and host-local replies while host `main` has
no remote-prefix route.

## Service-address / transport-address separation

The old alpha topology accidentally used the primary `/30` for two independent jobs:

1. HOST <-> STACK transport next-hop;
2. addressable stack-local endpoint for client transport/publication.

The migration removes that coupling. The transport is now unnumbered/device-directed while the
stack service address remains an independent `/32` on the managed endpoint.

EXP-051 also previously used the former host-side boundary address as its host-local return
test endpoint. The harness now assigns an explicit test-only `/32` on host `lo`, proving that
host-local identity is likewise independent of boundary addressing.

## Compatibility / backend duality

`ManagedNetworkDomainSpec` retains the older addressed-primary representation as an internal
compatibility path for historical experiments/tests. The real alpha selects
`ROUTED_VETH_PROXY_ARP` and rejects an addressed host endpoint for that mode.

`netkit-l3` remains the compatible alternate backend of the managed-L3 contract. This cycle
does not add the netkit lifecycle Driver: the current alpha intentionally materializes the
Debian-12-compatible routed-veth backend. Crucially, bootstrap, stateful return, service
addressing and Device/Profile semantics no longer contain a veth peer-gateway dependency, so
adding the alternate Driver is now a lower implementation substitution rather than another
architecture migration.

## Evidence

Workflow run `44604743687`:

- `unit`: PASS;
- `linux-managed-l3-host-bootstrap` / EXP-072: PASS;
- `linux-routed-managed-l3-stateful-return` / EXP-073: PASS;
- `linux-alpha-smoke` / migrated EXP-051: PASS;
- `linux-payload-forward`, including managed-domain and bounded controller-startup privileged
  integrations: PASS;
- selected host bootstrap and host-boundary behavior owner/lane regressions: PASS.

Distinguishing alpha markers:

```text
EXP051_ROUTED_MANAGED_L3_BOUNDARY=PASS
EXP051_SERVER_PUBLICATION_E2E=PASS
EXP051_SELECTED_HOST_BOOTSTRAP_DEVICE_ONLY=PASS
EXP051_FIRST_PAYLOAD=PASS
EXP051_ROUTE_RETURN_HOST_LOCAL_REPLY=PASS
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

EXP-073:

```text
EXP073_DEVICE_ONLY_DESIRED=PASS
EXP073_ROUTE_SPLIT=PASS
EXP073_NO_REMOTE_MAIN_ROUTE=PASS
EXP073_FORWARDED_REPLY=PASS
EXP073_HOST_LOCAL_REPLY=PASS
EXP073_RESULT=PASS
```

## Requirement impact

No accepted product requirement changes.

The migration only changes Linux realization of the already-explicit managed-domain and
host-boundary routing responsibilities. Existing requirements do not require a peer gateway
IP or an addressed HOST <-> STACK transit subnet.

## Deliberate non-changes / remaining work

- EXP-064 four behavior lanes remain selected for ordinary-side Profile `+snat`; this cycle
  neither moves gateway NAT into STACK nor removes those semantics.
- additional behavior-lane boundaries remain their existing lower realization until their
  alpha materialization cycle;
- netkit-L3 lifecycle materialization remains optional/future lower implementation work, not
  an alpha functional blocker;
- IPv6 remains outside Release-1 payload scope.

## Requirement-state inventory

### decomp

Resolved historical links unchanged:

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

The real alpha primary boundary now implements the managed-L3 endpoint architecture. The
historical primary `/30 + gateway` dependency is removed from alpha lifecycle, selected host
bootstrap and selected stateful return.
