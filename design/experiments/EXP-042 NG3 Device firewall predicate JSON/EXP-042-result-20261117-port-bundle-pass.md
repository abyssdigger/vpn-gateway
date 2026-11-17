# EXP-042 result — Device firewall port-bundle nft JSON PASS

**Date:** 2026-11-17  
**Workflow:** NG3 Python run `44136005710`  
**Source commit:** `7616d1c7624cc1928325d0649f1ae86aa32d1b94`

## Scope

This extension verifies the lower Linux/nftables representation required by the accepted
Release-1 Device-firewall port-bundle grammar.

Test rule:

```text
tcp sport 1000-1003
tcp dport { 80, 443, 8000-8007 }
return
```

## Observed canonical nft JSON

The inclusive source range is represented as:

```json
{"match":{"left":{"payload":{"field":"sport","protocol":"tcp"}},"op":"==","right":{"range":[1000,1003]}}}
```

The mixed exact/range destination bundle is represented as:

```json
{"match":{"left":{"payload":{"field":"dport","protocol":"tcp"}},"op":"==","right":{"set":[80,443,{"range":[8000,8007]}]}}}
```

Evidence markers:

```text
EXP042_PORT_BUNDLE=1
EXP-042 Device firewall predicate JSON: PASS
```

The same workflow also exercised the production guarded Device-firewall lower path using a
mixed port bundle and reported:

```text
NG3 live bounded guarded Device firewall mutation: PASS
```

This proves the complete current firewall path:

```text
canonical config
  -> normalized PortBundle
  -> DeviceFirewallRuleIntent
  -> nft scalar/range/set desired JSON
  -> strict Linux renderer
  -> nft materialization
  -> authoritative observation/comparison
```

No expansion into one rule per individual port is required.

## Verdict

**PASS.**

Release-1 Device firewall may use compact exact/range port bundles while preserving one
ordered user rule and one terminal verdict. The accepted lower representation is exact-port
scalar, inclusive `range`, or mixed `set` containing scalar/range operands.
