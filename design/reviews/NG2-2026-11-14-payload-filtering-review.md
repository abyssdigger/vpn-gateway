# NG2 — Payload/network-rules filtering review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** первый NG2 routing/filtering contract slice между `PayloadRulesCalculator` и
`NetworkRulesAdapter`

## Review criteria

Проверялись:

- соответствие согласованной payload semantics;
- fail-closed behavior;
- overlap Profiles и first-match traffic envelope;
- generation-aware interface identity;
- Direct Machinery contract и owner lifecycle;
- чистота следования компонентной модели;
- изоляция payload domain от network-stack domain;
- отсутствие Linux/nft implementation details выше Adapter boundary;
- пригодность структуры для последующего Python -> Rust переноса.

## Findings

### F1 — infrastructure `host0` leaked into the upper contract

**Severity:** architecture  
**Disposition:** accepted and fixed.

Первый routing slice передавал `InterfaceRef.stable("host0")` из
`PayloadRulesCalculator`.

Это заставляло payload domain знать конкретное имя инфраструктурного Linux interface.

Исправление:

- введен semantic endpoint `LOCAL_NETWORK`;
- конкретная materialization локальной стороны оставлена будущему
  `NetworkRulesAdapter`;
- regression test проверяет отсутствие interface identity у `LOCAL_NETWORK`.

### F2 — payload envelope reused lower-domain selector types

**Severity:** architecture  
**Disposition:** accepted and fixed.

`TrafficEnvelopeRule` первоначально принимал `TrafficSelector` из
`network_rules.py`. Это делало payload input model зависимой от vocabulary нижней
network-rules domain и нарушало обязательную semantic conversion boundary.

Исправление:

- введены payload-domain `PayloadProtocol`, `PayloadPortRange`,
  `PayloadTrafficSelector`;
- `PayloadRulesCalculator` явно преобразует их в network-rules selector;
- canonical `InterfaceIdentity` вынесена в отдельный neutral contract
  `interface_identity.py`, потому что она является междоменным наблюдаемым фактом, а не
  собственностью network-rules domain.

### F3 — Linux route type leaked through terminal routing policy

**Severity:** architecture  
**Disposition:** accepted and fixed.

Payload calculator выбирал `BLACKHOLE`, а generic network-rules contract также содержал
`UNREACHABLE/PROHIBIT`.

Это преждевременно фиксировало Linux routing mechanism выше Adapter boundary.

Исправление:

- terminal contract теперь семантический: `DROP | REJECT`;
- payload zero-path выбирает `DROP`;
- конкретный Linux blackhole/unreachable route и metric относятся к Adapter.

### F4 — named scope encoded caller semantics

**Severity:** architecture  
**Disposition:** accepted and fixed.

Ранее Adapter contract использовал именованный `NetworkRulesScope("payload")`.

Исправление:

- caller передает собственную opaque instance identity как `owner`;
- Adapter обязан различать owners по identity, не по имени/equality/domain type;
- добавлен `cleanup(owner)`;
- cleanup идемпотентен и означает удаление/нейтрализацию всего effective state/resources
  owner, а не только внутренней ссылки;
- physical composition нескольких owners остается скрытой backend mechanics.

### F5 — allow-only filtering could widen a broader overlapping Profile

**Severity:** correctness/safety  
**Disposition:** accepted and fixed during implementation.

При default-deny и только ALLOW rules широкий Profile `10.0.0.0/8` не должен разрешить
трафик в более специфичный `10.1.0.0/16`, если narrow Profile имеет другую direction или
другие paths.

Исправление:

- predicate каждого destination исключает все более специфичные configured destinations;
- отдельный test проверяет, что broad OUTBOUND не разрешает outbound initiation в narrow
  INBOUND prefix.

### F6 — traffic envelope must preserve first-match semantics without passing denies down

**Severity:** correctness  
**Disposition:** accepted and fixed during implementation.

NG1 traffic envelope допускает `default=allow` с точечными DROP и ordered first-match
rules. Передача исходного allow/drop policy в Adapter нарушила бы domain boundary.

Исправление:

- calculator преобразует ordered policy в boolean effective allow predicate;
- `traffic_allows` описывает допустимые байты;
- `flow_initiation_allows` отдельно описывает, какие допустимые байты могут создать новый
  stateful flow;
- Adapter не получает Profile direction или Device envelope;
- added tests cover default-allow/drop, default-drop/allow and first-match ordering.

## Model review

### Engines / Machinery

`PayloadRulesCalculator` остается Direct Calculator:

- explicit request in;
- deterministic semantic projection out;
- no I/O;
- no hidden history.

`NetworkRulesAdapter` остается Direct Adapter:

```text
apply(owner, spec)       -> SUCCESS | FAILURE
renew_state(owner)       -> SUCCESS | FAILURE
get_last_state(owner)    -> NetworkRulesState
cleanup(owner)           -> SUCCESS | FAILURE
```

Action result и observed state не смешиваются.

### Domain isolation

После fixes:

```text
payload concepts
    Profile direction
    Device traffic envelope
    payload selector/protocol/ports
            |
            v
PayloadRulesCalculator
            |
            v
network-rules concepts
    LOCAL_NETWORK
    concrete interface identity
    routing domains
    effective traffic predicates
    effective flow-initiation predicates
    DROP / REJECT
            |
            v
NetworkRulesAdapter
            |
            v
Linux details
    RPDB / routes / nft / conntrack / sysctl
    blackhole route
    established/related realization
    physical owner composition
```

No reviewed upper-level contract currently requires nft syntax, Linux rule/route numbers,
`host0`, conntrack states or concrete terminal route types.

## Evidence

Repository tests added/updated for:

- generation identity;
- no `host0` leak;
- zero-path fail-close;
- predicate complement;
- OUTBOUND return traffic without remote initiation;
- default-allow envelope with DROP exception;
- default-drop envelope with ALLOW exception;
- first-match envelope ordering;
- longest-prefix dispatch;
- broad/narrow Profile non-widening;
- explicit Adapter cleanup contract.

A local reconstructed Python contract smoke was compiled and executed successfully after the
final semantic changes:

```text
CURRENT_FILTERING_SMOKE=PASS
```

No kernel experiment is required for this review unit: it defines pure semantic projection.
Linux materialization remains a later Adapter review unit and must use the existing
EXP-012/017 evidence plus new integration evidence where needed.

## Final verdict

**PASS after accepted fixes.**

No unresolved filtering-contract finding remains at minor severity or higher.

The next coherent review unit may proceed to payload NAT semantics. NAT must be translated
to a network-rules intent without leaking nft `postrouting`, `masquerade` syntax or
mutation ordering into payload domain.
