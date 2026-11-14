# EXP-027 — result

Date: 2026-11-14

Result: **PASS**

Environment:

- GitHub privileged Linux runner;
- disposable network namespace;
- seven veth path interfaces;
- one table for `198.51.100.0/24`;
- one table for `default`;
- owned unicast protocol 202;
- terminal blackhole protocol 201, metric 65536.

## Proven production primitive

Steady state contains one route for every eligible path plus one unoccupied ordinary
metric slot.

For one move:

```text
X@Mold + EMPTY@Mempty
    add X@Mempty
X@Mold + X@Mempty
    delete X@Mold
EMPTY@Mold + X@Mempty
```

Fresh FIB checks after every add proved:

- the complete eligible path set remained present;
- route count was exactly `N+1`;
- exactly one path had two copies;
- terminal blackhole remained.

Fresh checks after every delete proved:

- the complete eligible path set remained present;
- route count returned to exactly `N`;
- every path had exactly one copy;
- the deleted old metric became the new EMPTY;
- terminal blackhole remained.

## Passed transitions

For both ordinary prefix and `default`:

```text
A B G D . V E J
    ->
A B V G D . E J

A B V G D . E J
    ->
A B G D . V E J

A B G D E J . V
    ->
A B V G D E J .
```

Observed completion markers:

```text
PASS P1
PASS P2
PASS P3
PASS D1
PASS D2
PASS D3
EXP027=PASS
```

## Consequence

The production route-priority fast path may model the FIB as a permutation of
`eligible paths + EMPTY` and use only `add duplicate -> delete old` elementary moves.

No eligible route is intentionally absent at any intermediate point.

The earlier EXP-027 `ip route replace` result remains valid evidence that the same
interface can coexist at multiple metrics, but top-down replacement is superseded as the
production transition strategy.

Structural fail-closed rebuild remains the fallback for any non-pure priority change or
failed verification.
