# NG2 — PayloadTrafficManager request-path review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** first executable PayloadTrafficManager RequestEvent handling path

## Review criteria

Проверялись:

- соответствие Manager/Engine роли;
- отсутствие synchronous domain reply на RequestEvent;
- owner=self semantics для Adapter;
- separation action result vs observed state;
- request/desired state consistency;
- InfoEvent deduplication;
- lifecycle cleanup;
- отсутствие premature audit/retry complexity;
- чистота domain boundaries.

## Findings

### M1 — request and desired rules had to be accepted atomically

**Severity:** correctness/architecture  
**Disposition:** accepted and fixed.

Первоначальная реализация записывала latest_request до PayloadRulesCalculator.calculate().

Если pure Calculator отвергал input, Manager мог остаться в противоречивом состоянии:

    latest_request = new request
    latest_desired = previous desired rules

Исправление:

1. сначала рассчитывается candidate desired rules;
2. только после успешного pure calculation вместе принимаются latest_request и
   latest_desired;
3. до этого Adapter не вызывается.

Invalid/unrepresentable RequestEvent не становится частично принятым managed intent.

### M2 — RequestEvent handler must not become synchronous RPC

**Severity:** architecture  
**Disposition:** accepted and implemented.

handle_request() возвращает None.

Внешний domain result появляется только через PayloadTrafficStatePublisher, который
представляет порт Event Delivery Environment.

Manager не возвращает PayloadTrafficStateInfo caller'у и не требует synchronous response от
RuntimeStateManager.

### M3 — Adapter owner is the Manager instance identity

**Severity:** architecture  
**Disposition:** accepted and covered.

Все calls используют один и тот же owner object:

    adapter.apply(self, desired)
    adapter.renew_state(self)
    adapter.get_last_state(self)
    adapter.cleanup(self)

Test проверяет identity через is, а не equality.

Manager не знает scope name и не передает lower-domain semantic label.

### M4 — operation FAILURE must not become payload state

**Severity:** correctness  
**Disposition:** accepted and covered.

При apply FAILURE:

1. Manager вызывает renew_state(self);
2. независимо от ActionResult читает get_last_state(self);
3. PayloadRulesStateCalculator интерпретирует observation;
4. публикуется доказуемый state.

Tests покрывают:

- apply FAILURE + authoritative isolated observation -> SAFE/ISOLATED;
- apply FAILURE при observation, уже совпадающем с desired -> никакого synthetic FAILED;
- apply FAILURE + renew FAILURE + stale observation -> UNKNOWN axes.

### M5 — repeated identical InfoEvent must be suppressed

**Severity:** runtime behavior  
**Disposition:** accepted and implemented.

Manager сравнивает новый PayloadTrafficStateInfo с последним успешно опубликованным payload.

Повторный одинаковый RequestEvent может повторно вызвать Adapter, но не создает event storm.

Избежание лишнего Adapter apply является будущей оптимизацией, не semantic requirement.

### M6 — publisher failure must not poison dedup state

**Severity:** implementation review  
**Disposition:** accepted by current ordering.

latest_published обновляется только после publisher.publish(info).

Если Event Delivery Environment raises/fails, следующий reconcile не считает
неопубликованный state уже доставленным.

Отдельная delivery retry policy находится вне текущего unit.

### M7 — cleanup remains lifecycle operation

**Severity:** architecture  
**Disposition:** accepted and implemented.

shutdown() делегирует adapter.cleanup(self) и возвращает ActionResult lifecycle caller'у.

Это не RequestEvent response и не нарушает asynchronous domain-event semantics.

### M8 — audit/retry loop intentionally excluded

**Severity:** scope  
**Disposition:** accepted.

Этот unit реализует только:

    RequestEvent -> desired rules -> Adapter -> observation -> rules state -> InfoEvent

Periodic drift audit, retry scheduling and event-triggered reconcile остаются отдельным
review unit.

Это предотвращает возвращение NG1 central Planner complexity одним большим переносом.

## Component/domain review

Current synchronous dependencies:

    PayloadTrafficManager
        -> PayloadRulesCalculator
        -> PayloadRulesStateCalculator
        -> NetworkRulesAdapter
        -> Event Delivery Environment publisher port

Graph is acyclic.

Manager owns:

- latest accepted request;
- latest desired rules;
- last successfully published payload state.

Manager does not own:

- Linux allocations;
- mutation/barrier phases;
- nft/routes/sysctl mechanics;
- Adapter internal owner registry;
- Profile system-level verdicts.

PayloadRulesCalculator and PayloadRulesStateCalculator remain Direct Calculators.
NetworkRulesAdapter remains Direct Adapter.

## Evidence

NG2 Python CI passed on commit
4880649b867781bf21a24d9454122168a58ef90f.

Tests cover:

- owner identity;
- valid request success path;
- invalid request rejected before Adapter mutation;
- apply failure -> refresh -> actual observation;
- apply failure not mapped to FAILED state;
- apply + refresh failure -> UNKNOWN from stale observation;
- semantic InfoEvent deduplication;
- changed observation publication;
- lifecycle cleanup using same owner identity.

No kernel experiment is required for this unit; all behavior is orchestration over existing
semantic contracts.

## Final verdict

**PASS.**

No unresolved finding blocks the request-path implementation.

Next coherent unit: drift/audit reconcile for PayloadTrafficManager, reusing current desired
rules and preserving the same action-result/state separation.
