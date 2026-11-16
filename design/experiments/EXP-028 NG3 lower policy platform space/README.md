# EXP-028 — NG3 lower policy platform space

## Purpose

Validate one concrete Linux numeric/resource candidate for the NG3 lower
`NetworkPolicyPlatformSpace`.

This experiment is intentionally narrower than a full structural NetworkPolicyExecutor. It
tests whether the candidate namespaces are representable and actually selected by current
Linux/iproute2/nftables behavior in a disposable network namespace.

## Candidate

```text
payload table pool:
    [0x80000000, 0xC0000000)

probe table pool:
    [0xC0000000, 0x100000000)

probe RPDB priority pool:
    [0x2000, 0x4000)     # 8192..16383

payload RPDB priority pool:
    [0x4000, 0x6000)     # 16384..24575

ambient/main lookup:
    priority 32766

managed guard route protocol:
    201

managed path/unicast route protocol:
    202

first preference metric:
    1

terminal guard metric:
    0xffffffff

nft namespace:
    family ip
    table vpn_gate
```

The RPDB split deliberately leaves:

- priorities 1..8191 outside VPN-GATE for higher-precedence external/admin rules;
- priorities 24576..32765 outside VPN-GATE before the default main rule.

The high table pools use the two top-bit role prefixes `10` and `11`, providing large,
directly classifiable internal namespaces without consuming common low table IDs.

## Hypotheses

- **H1:** Linux/iproute2 accepts and reports the high 32-bit table IDs.
- **H2:** probe priority 8192 and payload priority 16384 coexist before main priority 32766
  and route lookup follows the intended table.
- **H3:** route protocols 201/202 remain observable role markers in the selected tables.
- **H4:** metric 1 normal route and `u32::MAX` terminal blackhole are both representable.
- **H5:** dedicated `ip vpn_gate` nftables namespace can be created, observed and removed
  independently.

## Safety

The experiment creates only a disposable network namespace and deletes it on exit.

It does not modify host routes, rules or nftables state.

## Acceptance

All five hypotheses must pass in privileged GitHub CI before these numeric values become the
NG3 Linux platform constants.

Historical RC/NG evidence for 201/202 and ordinary metrics is supporting evidence only; this
experiment is the NG3 acceptance gate for the complete combined layout.
