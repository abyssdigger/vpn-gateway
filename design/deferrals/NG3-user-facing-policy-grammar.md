# NG3 configuration-format review — Release-1 user-facing policy grammar

**Status:** RESOLVED FOR ORDINARY RELEASE-1 GRAMMAR  
**Created:** 2026-11-16  
**Resolved:** 2026-11-17  
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

The exact accepted forms, validation rules and complete example are normative in
`design/NG3/config-model.md`.

## Remaining independent deferral

Endpoint-scoped Device firewall rules remain outside Release 1 under
`VPNG0001-R1.R2.R4.R6.R2.R5.C1`.

That future capability requires both:

- supported transport-endpoint provenance for the applicable integration; and
- a separate accepted durable endpoint-selector grammar that does not use runtime ifname as
  long-lived endpoint identity.

This remaining item does not reopen the ordinary Release-1 grammar above.

## Requirement trace

Resolved ordinary grammar:

- `VPNG0001-R1.R2.R4.R4.R4.C1`;
- `VPNG0001-R1.R2.R4.R6.R1`;
- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0001-R1.R2.R4.R6.R3`;
- `VPNG0001-R1.R2.R4.R6.C1`;
- `VPNG0001-R1.R3.C1.C1.R3`;
- `VPNG0003-R3.R6.R3.R1.C1.R1`.

Still independently constrained:

- `VPNG0001-R1.R2.R4.R6.R2.R5.C1`.

## Requirement-state inventory

- active `decomp`: none in this grammar decision;
- active `unreal`: none;
- active `broken`: none;
- `[rejected_closure]`: none.
