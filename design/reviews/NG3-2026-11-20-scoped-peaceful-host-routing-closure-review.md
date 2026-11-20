# NG3 review — scoped peaceful host-routing requirement/design closure

**Date:** 2026-11-20  
**Review unit:** revised Release-1 peaceful helper traffic scope  
**Branch:** `ng3-design-cycle-20261120-helper-routing-selectors-35m`  
**Requirement:** `VPNG0001-R2.R2`  
**Verdict:** **ACCEPTED — architecture closure restored**

## Trigger

The previous Release-1 lowering used one unconditional peaceful-helper dispatch after
`main suppress_prefixlength 0`. With helper destination `0.0.0.0/0`, that changed
otherwise-default host-local traffic even when the administrator intended VPN-GATE only as a
gateway for selected LAN transit.

That behavior was too broad for `VPNG0001-R2`: helper destination scope and the ordinary-host
traffic handed to that helper must be separate administrative decisions.

## Accepted product contract

Release 1 now uses independent top-level controls:

```toml
helper_routing_interfaces = ":none"   # default
helper_routing_policy = "peaceful"    # default
```

Selectors are canonical and strict:

- `:none` — no helper contribution;
- `:local` — host-originated traffic;
- `:external` — all non-local ordinary-host ingress;
- `:any` — local plus external;
- exact interface names — only that ingress;
- `:local` may be unioned with exact names; exact names may be unioned with each other.

The managed boundary is excluded from capture by a higher-priority bypass. Peaceful helper
does not own `net.ipv4.ip_forward`; external transit prerequisites remain administrator
responsibility.

The default is now deliberately non-invasive.

## Linux closure

Selected lowering:

```text
iif <managed-boundary> lookup main
lookup main suppress_prefixlength 0
<selector dispatch(es)> lookup <peaceful-helper-table>
ordinary main/default
```

Selector dispatch:

```text
:local       iif lo
:external    not iif lo
:any         unconditional
<ifname>     iif <ifname>
```

EXP-078 run `44758764201`, job `136365426254`, passed every selector/non-interference
criterion. EXP-077 remains complementary evidence for the main-first/global subcase and
non-destructive lifecycle cleanup. EXP-074 remains separate aggressive-helper evidence.

## Requirements review

The revised `VPNG0001-R2.R2` Purpose remains directly causal to `VPNG0001-R2`: the helper
reduces administrative routing work without taking unrelated ordinary-host routing into its
scope. The Statement does not require Linux RPDB vocabulary and explicitly separates selected
host traffic from helper ownership semantics.

No new primary promise is introduced. The user-visible schema change is the accepted
refinement required to express the already-agreed host-side automation boundary.

## Simplification review

No generic source-policy language, marks, nft packet classification, per-flow state or helper
routing daemon is required. Linux already exposes the needed distinction in RPDB ingress
selectors. One helper table, one preserve-main rule, one managed-boundary bypass and a bounded
set of selector-specific dispatch rules are sufficient.

## Disposition

- `VPNG0001-R2.R2`: [`closed`].
- EXP-078: selected.
- EXP-077: remains selected complementary evidence.
- Implementation must now replace the obsolete `host_routing = auto|manual` surface and
  global single-dispatch representation with this accepted contract before the development
  block is complete.
