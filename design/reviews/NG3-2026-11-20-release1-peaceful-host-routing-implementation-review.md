# NG3 Release-1 peaceful host-routing implementation review — 2026-11-20

## Scope

This review closes the development block that followed the host-network ownership requirement
correction and replaces the alpha's previously wired authoritative host-routing owner with the
selected Release-1 peaceful lifecycle helper.

Branch:

`ng3-design-cycle-20261120-host-routing-helper-35m`

Base main snapshot:

`f551da17b8364d7adc4c1c11da5b159e58887736` — Main snapshot 140.

## Product boundary implemented

Core managed forwarding no longer depends on authoritative ordinary-host routing ownership.

Release 1 now exposes:

```toml
host_routing = "auto"   # default
# or
host_routing = "manual"
```

- `auto` enables peaceful lifecycle-scoped route assistance;
- `manual` creates no peaceful host-routing contribution and leaves ordinary-host integration
  to the administrator;
- later administrator route changes are not periodically reconciled and do not gate the
  internal managed-domain ForwardingGate.

This closes `VPNG0001-R2.R2`.

The manual host-integration contract is published in `design/NG3/host-integration.md` and
covers remote-prefix reachability, Profile-SNAT identity return routing, full-tunnel underlay
requirements and the host-local versus host-forwarding distinction. This closes
`VPNG0001-R2.R1.R1`.

## Selected Linux lowering

The peaceful helper uses a dedicated helper table and protocol marker, with lookup order:

```text
kernel local
iif managed-boundary -> main
main suppress_prefixlength 0
peaceful-helper table
ordinary main/default
```

Consequences:

- explicit non-default administrator `main` routes win before helper dispatch;
- helper `0.0.0.0/0` replaces only otherwise-default routing for ordinary-origin traffic;
- packets already arriving from STACK use ordinary `main` and are not recaptured;
- the helper does not rewrite ordinary `main`;
- Profile-SNAT identity /32 routes use the proven
  `via <stack-service-address> dev <boundary> onlink` form.

The selected Release-1 allocation is independent from the retained aggressive prototype:

- table `0x7FFF0004`;
- bypass priority `0x6002`;
- preserve-main priority `0x6003`;
- dispatch priority `0x6004`;
- route/rule protocol `204`.

The EXP-074 aggressive allocation/behavior remains unchanged and detached from alpha runtime
composition.

## Lifecycle behavior

Startup still treats failure to establish an explicitly enabled `auto` helper as failure of
that requested lifecycle operation.

After successful startup, however, ordinary-host routing returns to administrator control:

- alpha periodic reconciliation no longer observes or repairs peaceful host-routing state;
- later administrator changes do not close core managed forwarding;
- stop removes only still-identifiable helper-owned state;
- a foreign/admin replacement at an owned slot is preserved rather than deleted or treated as
  a core cleanup failure.

`manual` mode returns no host-routing contribution at all.

## Observability and deployment surface

Configured-intent status now exposes the normalized `host_routing` mode.

The alpha deployment README and example configuration describe the selected peaceful helper
rather than the former authoritative prototype.

Current implementation descriptions in the Python reference README/module docstrings and
NG3 changelog were aligned with the actual runtime composition.

## Acceptance evidence

### EXP-077

EXP-077 provides the differentiating privileged evidence for the Release-1 peaceful helper:

- otherwise-default traffic is assisted through the managed boundary;
- pre-existing administrator non-default route wins;
- an administrator /32 added after activation wins immediately without reconciliation;
- STACK-origin traffic bypasses helper capture;
- ordinary `main` is not mutated by helper activation;
- a foreign replacement at the helper preserve-main priority survives peaceful cleanup;
- final ordinary `main` returns to its pre-helper state.

The experiment emitted `EXP077_RESULT=PASS`.

EXP-074 executed in the same host-routing job and remained PASS, proving that retaining the
aggressive evidence path did not silently change its authoritative semantics.

### Full branch workflow

GitHub Actions `NG3 Python` run `44742418333` completed **SUCCESS** on the final code tree.

All jobs passed, including:

- unit tests;
- alpha smoke;
- EXP-074 / EXP-077 host-routing job;
- Debian-12 routed-veth;
- EXP-049 external OpenVPN integration;
- payload forwarding/NAT/nft;
- probing;
- stack return affinity;
- Profile SNAT reverse and combined dataplane;
- host publication.

Actual-main lineage guards also remained green throughout the block.

## Evidence lifecycle

EXP-077 is selected acceptance evidence for `VPNG0001-R2.R2`.

It does not supersede EXP-074, which remains selected for the postponed aggressive
authoritative child `VPNG0001-R2.R3.R1`.

EXP-059/060/072 remain valid lower Linux facts/history; EXP-077 reuses the relevant
specificity-preservation, stack-ingress-bypass and managed-L3 route facts without restoring
their former complete bootstrap architecture.

## Remaining requirement state

No unresolved Release-1 obligation remains in this host-routing block.

The remaining `pending_closure` nodes are explicitly outside the Release-1 obligation:

- `VPNG0001-R2.R3` aggressive host-routing helper;
- `VPNG0001-R2.R3.R2` continuous aggressive ownership/recovery;
- `VPNG0001-R2.R3.R3` unrecoverable-alarm containment composition;
- `VPNG0004-R4.R7` administrative payload-containment mode;
- `VPNG0005-R5.R6.R4` reload semantics when a deployment interface chooses to support reload.

Current causal-link inventory contains four `decomp` links and no active `-> pending`
target; all four resolve to concrete live requirement nodes. There are no active `unreal`,
`broken` or `rejected_closure` links.

## Verdict

**ACCEPTED — DEVELOPMENT BLOCK COMPLETE.**

The previous alpha mismatch is removed: the default runtime now implements the peaceful
Release-1 helper semantics rather than the postponed aggressive semantics.

The next development block must start only after normal snapshot publication of this completed
tree. It should be selected from the remaining Release-1 implementation/readiness work rather
than by reopening the now-closed host-routing ownership question.
