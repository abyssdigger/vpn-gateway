# NG3 configuration-format review — Release-1 user-facing policy grammar

**Status:** RESOLVED  
**Created:** 2026-11-16  
**Ordinary grammar resolved:** 2026-11-17  
**Per-path firewall re-entered:** 2026-11-23  
**Canonical contract:** `design/NG3/config-model.md`

## Resolution

The configuration-format re-entry condition was met and the ordinary Release-1 grammar has
been accepted.

Canonical Device fields are now:

```text
use_outbound_nat
allow_vpn_client
publish_vpn_server
firewall
```

Canonical Profile extensions are now:

```text
direction = outbound | inbound | inbound+snat | bidirectional | bidirectional+snat
availability_check = icmp | icmp/<IPv4>
```

There is no public top-level `[integration.*]` object in Release 1.

Historical prototype spellings such as `nat`, `traffic_envelope`, `publications` and
`interface_balancing` remain design evidence only and are not parser aliases.

The resolved Release-1 grammar includes compact non-overlapping `N,A-B,...` port bundles for
Device firewall and server publication. Explicit publication translation requires equal
expanded bundle cardinality and positional 1:1 mapping. `allow_vpn_client` remains exact-port.

The exact accepted forms, validation rules and complete example are normative in
`design/NG3/config-model.md`.

## Subsequent per-path firewall resolution

The original 2026-11-17 decision deliberately postponed per-path Device firewall syntax while
the project still treated durable logical-path identity as an unresolved prerequisite.

The 2026-11-23 re-entry recovered EXP-004.3/EXP-009 evidence and clarified the actual product
scope. A generic durable VPN-path identity is not required. The canonical Device firewall now
has one optional, mutually exclusive rule-local path selector:

```text
no via
    -> every current path of the Device

via if <exact-ifname>
    -> current path of this Device on that exact interface

via peer <IPv4>
    -> current point-to-point path of this Device with that observed
       private/inner peer IPv4
```

`via peer` does not mean an external VPN transport/server endpoint or payload address.
Exact-if selection uses the already verified current binding; private-peer selection is
resolved only among current Device paths and uses demand-scoped fresh peer observation.

The re-entry and later scope clarification are recorded in:

- `design/reviews/NG3-2026-11-23-private-peer-path-restriction-reentry-review.md`;
- `design/reviews/NG3-2026-11-23-device-firewall-path-scope-clarification-review.md`;
- `design/reviews/NG3-2026-11-23-device-firewall-path-selector-design-review.md`.

Current requirement status is owned by `design/NG3/requirements.md`; this historical
deferral record no longer asserts a live postponement.

## Requirement trace

Resolved ordinary grammar:

- `VPNG-U001-R4.R4.R4.R4.C1`;
- `VPNG-U001-R4.R4.R6.R1`;
- `VPNG-U001-R4.R4.R6.R2.R1`;
- `VPNG-U001-R4.R4.R6.R3`;
- `VPNG-U001-R4.R4.R6.C1`;
- `VPNG-U001-R4.R4.R6.R4`;
- `VPNG-U003-R3.R6.R3.R1.R1`.

Re-entered per-path capability and scope constraints:

- `VPNG-U001-R1.R4.R2.R1`;
- `VPNG-U001-R1.R4.R2.R1.R1`;
- `VPNG-U001-R4.R4.R6.R2.R1`;
- `VPNG-U001-R4.R4.R6.R2.R5`;
- `VPNG-U001-R1.R4.R2.R1.C1`;
- `VPNG-U001-R4.R4.R6.R2.R5.C1`.

Their live status is intentionally not duplicated here.

## Requirement-state inventory

- active `decomp`: none in this grammar decision;
- active `unreal`: none;
- active `broken`: none;
- `[rejected_closure]`: none.
