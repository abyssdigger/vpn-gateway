# EXP-066 — NG3 probe local nft owner shape

## Purpose

Pin current nftables JSON representation for the already selected EXP-024 Release-1 probe
local-admission mechanism:

```text
OUTPUT:
    dedicated probe uid + exact oif + exact target + ICMP
        -> set dedicated conntrack mark
        -> accept

INPUT:
    exact iif + exact source + ICMP + dedicated conntrack mark
        -> accept
```

This experiment does not re-decide probe semantics. It supplies current lower representation
evidence needed by an authoritative observer/mutator in the shared `ip vpn_gate` table.

## Scenario

Inside one disposable network namespace:

1. create a dummy current path;
2. create `ip vpn_gate` with DROP-policy `stack_output` and `stack_input` chains;
3. install one marked probe OUTPUT rule and one reverse INPUT rule;
4. record numeric JSON for both chains;
5. delete both rules by handle and verify the chains contain no probe rules.

## Acceptance

The result must expose the exact JSON expression shape for:

- `meta skuid`;
- exact `meta oif` / `meta iif`;
- IPv4 target/source;
- ICMP protocol;
- conntrack mark assignment;
- conntrack mark match;
- terminal ACCEPT;
- owner comment and handle.

No host state is modified.
