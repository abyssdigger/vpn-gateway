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

The resolved Release-1 grammar includes compact non-overlapping `N,A-B,...` port bundles for
Device firewall and server publication. Explicit publication translation requires equal
expanded bundle cardinality and positional 1:1 mapping. `allow_vpn_client` remains exact-port.

The exact accepted forms, validation rules and complete example are normative in
`design/NG3/config-model.md`.

## Remaining independent deferral

Per-path Device firewall rules remain outside Release 1 under
`VPNG-U001-R1.R4.R2.R1.C1` and the corresponding configuration constraint
`VPNG-U001-R4.R4.R6.R2.R5.C1`.

That future capability requires an accepted durable logical-VPN-path selector grammar that
uses the product's distinguishable logical path identity and does not expose runtime ifname,
transport endpoint or peer as the long-lived user-facing identity.

This remaining item does not reopen the ordinary Release-1 grammar above.

## Requirement trace

Resolved ordinary grammar:

- `VPNG-U001-R4.R4.R4.R4.C1`;
- `VPNG-U001-R4.R4.R6.R1`;
- `VPNG-U001-R4.R4.R6.R2.R1`;
- `VPNG-U001-R4.R4.R6.R3`;
- `VPNG-U001-R4.R4.R6.C1`;
- `VPNG-U001-R4.R4.R6.R4`;
- `VPNG-U003-R3.R6.R3.R1.R1`.

Still independently constrained:

- `VPNG-U001-R4.R4.R6.R2.R5.C1`.

## Requirement-state inventory

- active `decomp`: none in this grammar decision;
- active `unreal`: none;
- active `broken`: none;
- `[rejected_closure]`: none.
