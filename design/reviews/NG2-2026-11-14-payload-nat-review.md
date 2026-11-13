# NG2 — Payload NAT contract review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** payload NAT projection into `NetworkRulesSpec`

## Review criteria

Проверялись:

- сохранение NG1 payload NAT semantics;
- отсутствие nft/Linux materialization details выше Adapter boundary;
- независимость NAT policy от filtering policy;
- корректность overlap Profiles;
- generation-aware egress identity;
- чистота компонентной модели и предметных границ;
- Python -> Rust friendliness.

## Findings

### N1 — raw `MASQUERADE` must not become Adapter vocabulary

**Severity:** architecture  
**Disposition:** accepted and fixed during implementation.

`MASQUERADE` остается payload/config-domain понятием. Network-rules contract получает
семантическое требование:

```text
SourceNatSpec
    source = LOCAL_NETWORK
    egress = concrete interface identity
    target = EGRESS_ADDRESS
    predicate = effective destination set
```

Конкретный nft `postrouting ... masquerade` или иной backend mechanism находится ниже
Adapter boundary.

### N2 — broad Profile NAT must not capture a more-specific Profile

**Severity:** correctness  
**Disposition:** accepted and fixed during implementation.

Source-NAT predicate использует ту же longest-prefix ownership semantics, что и dispatch /
filtering: более широкий destination исключает все более специфичные configured
destinations.

Regression test проверяет `10.0.0.0/8` MASQUERADE + `10.1.0.0/16` separate Profile:
broad NAT predicate не матчится на narrow destination.

### N3 — NAT must not depend on Device envelope realization

**Severity:** architecture/correctness  
**Disposition:** accepted; implementation already correct.

NAT projection строится из routing/profile destination semantics и path NAT mode, но не из
effective filtering predicate.

Это сохраняет разделение предметных понятий: firewall может запретить пакет, но наличие
NAT intent для соответствующего routed path не должно зависеть от того, каким способом
filtering backend его отсекает.

### N4 — source translation requires concrete egress identity

**Severity:** correctness  
**Disposition:** accepted and enforced.

`SourceNatSpec` отвергает `LOCAL_NETWORK` как egress. Egress обязан быть concrete
generation-aware interface endpoint.

## Model review

`PayloadRulesCalculator` выполняет явное преобразование:

```text
PayloadNatMode.NONE
    -> no SourceNatSpec

PayloadNatMode.MASQUERADE
    -> SourceNatTarget.EGRESS_ADDRESS
```

Adapter не знает `PayloadNatMode`.

В обратную сторону payload domain не получает nft chain/hook, route table, address lookup
или mutation-order concepts.

## Evidence

Repository tests added for:

- `NONE` -> no translation;
- `MASQUERADE` -> `EGRESS_ADDRESS`;
- source NAT requires concrete egress path;
- broad Profile NAT cannot capture a more-specific Profile.

Local reconstructed contract smoke after the semantic changes:

```text
CURRENT_FILTERING_SMOKE=PASS
CURRENT_NAT_SMOKE=PASS
```

No kernel experiment is required for this review unit. This unit defines semantic
projection only. Concrete Linux NAT materialization remains part of the future
`NetworkRulesAdapter` implementation and will require integration evidence.

## Final verdict

**PASS.**

No unresolved NAT-contract finding remains at minor severity or higher.
