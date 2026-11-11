# EXP-013 — NG1 unavailable-path common-metric fallback

Status: **IN PROGRESS — Phase A PASS; A3 artifact interpretation and Phase B remain**

Architecture baseline: **NG1 Draft 3**

## Цель

Проверить Linux/FIB-семантику принятого NG1 правила:

```text
normal metric < UNAVAILABLE_METRIC < BLACKHOLE_METRIC
```

и конкретно материализацию нескольких `UNAVAILABLE` paths на одном общем
`UNAVAILABLE_METRIC`.

Эксперимент обязателен до реализации unavailable-path projector в TrafficEngine.

Первый live-прогон Phase A подтвердил A1 и дошёл до terminal части A2, где старый
harness ошибочно ожидал текст `blackhole` от обычного `ip route get`. Для blackhole
локальный lookup возвращает ошибку; assertion исправлен через `fibmatch` + table
inventory. Подробности: `EXP-013-phase-A-attempt-1.md`.

Исправленный rerun завершился `PHASE_A=PASS`; результат сохранён в
`EXP-013-phase-A-result.md`. Перед финализацией Phase B требуется разобрать A3 artifacts,
поскольку A3 намеренно фиксирует фактическое kernel behavior после удаления одного
multipath nexthop.

## Почему нужен отдельный live gate

Архитектура уже определяет policy:

- `UNKNOWN` и `AVAILABLE` остаются в normal tier;
- только положительный `UNAVAILABLE` опускает path вниз;
- все `UNAVAILABLE` paths одного destination делят один final fallback metric;
- terminal `blackhole default` должен проигрывать fallback даже для Profile с
  `0.0.0.0/0`.

Но еще не доказаны kernel details:

1. допускает ли целевая Debian/iproute2 связка direct-`dev` multipath без gateway;
2. как такой route представлен в `ip -j route`;
3. что происходит с multipath route при исчезновении одного interface;
4. корректно ли normal -> common fallback -> normal меняется без survivor priority churn;
5. как common fallback конкурирует с `blackhole default` для `/0`;
6. что реально происходит с payload, когда один из equal-cost fallback paths фактически
   мертв, но interface остается существовать.

Последний пункт особенно важен: common metric не должен молча трактоваться как
последовательный failover, если Linux фактически дает ECMP/hash selection.

## Phase A — disposable kernel/FIB probe

Phase A не использует VPN и не меняет host routing.

Harness создает отдельный netns с двумя dummy interfaces и отдельной routing table.

Проверки:

### A1 — direct-dev multipath accepted

Создать route вида:

```text
<target> metric UNAVAILABLE_METRIC
    nexthop dev path-a weight 1
    nexthop dev path-b weight 1
```

PASS: команда принимается kernel, JSON inventory содержит один multipath route с двумя
direct-device nexthops.

### A2 — terminal blackhole ordering

В той же table установить normal route, unavailable multipath route и blackhole route с
ordering:

```text
normal < unavailable < blackhole
```

PASS: lookup выбирает normal path; после удаления normal path — unavailable multipath;
после удаления fallback — blackhole.

Отдельно повторить для `default`, потому что это реальная форма Profile с destination
`0.0.0.0/0`.

### A3 — one nexthop interface disappears

Удалить один dummy interface, не меняя route вручную.

Зафиксировать JSON route state, lookup result, судьбу surviving nexthop и отсутствие stale
reference. Это наблюдение определит точную reconciliation expectation TrafficEngine.

### A4 — same-name/new-ifindex return

Создать интерфейс с тем же именем снова.

Зафиксировать новый ifindex и убедиться, что kernel сам не восстанавливает прежний
multipath membership. Восстановление должно оставаться обязанностью reconciliation.

## Phase B — real VPN interfaces and payload

Harness: `vpn-gateway-exp-013-phase-b.sh`.

Phase B выполняется на той же dedicated Debian 13 gateway с двумя реальными OpenConnect
interfaces (`vpnsXX`).

Для transport/appliance scaffolding используется уже live-verified ROU v0. После появления
двух DTLS bindings замораживается **только controller process** через SIGSTOP; ocserv и
publication relay продолжают работать. Это исключает v0 drift repair из измерений.

Экспериментальные routing objects изолированы:

- отдельная table 313;
- RPDB priority 50 только для test target;
- production/v0 table 100 не меняется;
- существующие v0 FORWARD/NAT rules используются как уже проверенная payload plumbing;
- B4 добавляет только одну временную узкую DROP rule.

### Phase B candidate: persistent shadow fallback

Phase A показала, что normal route, common-metric multipath и blackhole route могут
одновременно существовать для одного prefix с разными metrics.

Поэтому Phase B проверяет более простую production-кандидатуру:

- для всех **bound** interfaces постоянно существует shadow fallback на
  `UNAVAILABLE_METRIC`;
- UNKNOWN/AVAILABLE interface дополнительно имеет свой normal route;
- AVAILABLE/UNKNOWN -> UNAVAILABLE удаляет только normal route;
- UNAVAILABLE -> AVAILABLE/UNKNOWN возвращает normal route на прежний stable metric;
- availability change не меняет membership shadow fallback;
- binding ADD/REMOVE перестраивает shadow fallback membership;
- один bound interface может быть представлен обычным direct-dev fallback route;
- два и более — одним direct-dev multipath fallback route.

A3 отдельно показала: при исчезновении одного member-interface kernel удаляет весь
direct-dev multipath route, а не автоматически сокращает его до survivors. Это безопасное
fail-closed transient state; reconcile обязан собрать fallback заново из fresh binding set.

### B1 — normal priorities

Два direct-dev routes:

```text
path A metric 1
path B metric 2
```

PASS: lookup выбирает A и test payload проходит.

### B2 — preferred path demoted

Удалить normal route A и добавить A в fallback tier на `UNAVAILABLE_METRIC`, оставив B
normal.

PASS: lookup выбирает B, payload продолжает проходить, B route/metric не меняется.

Это ключевая проверка собственно «сброса вниз».

### B3 — all paths unavailable

Удалить normal B и материализовать один common-metric multipath route с A+B.

PASS: route materializes как один multipath fallback, terminal blackhole остается ниже
него, lookup получает unicast/multipath path, а не blackhole. Payload behavior записывается.

### B4 — one fallback path dead while interface remains

Не удаляя interface, временно блокировать только experiment payload через один fallback
interface.

Зафиксировать выбор nexthop и наличие/отсутствие автоматической повторной попытки через
другой path.

**Важно:** эксперимент не предполагает, что equal-cost fallback дает sequential failover.
Если Linux дает ECMP/hash selection, это должно стать явной архитектурной семантикой.

### B5 — promotion/failback

Снять test block, вернуть A в normal tier, оставив B в unavailable fallback.

PASS: A снова выигрывает на своем normal metric, B fallback не мешает, surviving normal
slots не renumber/reorder.

### B6 — /0 profile competition

Повторить routing table в форме:

```text
default normal
default unavailable
blackhole default
```

PASS: ordering `normal < unavailable < blackhole` дает ожидаемый lookup во всех трех
состояниях.

## Safety

Phase A полностью изолирована в disposable netns.

Phase B не заменяет host main/default routes, использует отдельную table и experiment-only
RPDB rule, отдельный source netns и узкие filter/NAT rules. Cleanup обязан удалять все
experiment resources. Штатные VPN interfaces не удаляются и не перенастраиваются.

Эксперимент должен завершиться до mutation, если нет двух заданных interfaces,
`ip_forward != 1` или experiment resources уже существуют.

## Architecture decision gate

После live run возможны только два результата:

1. **PASS:** common `UNAVAILABLE_METRIC` materialization подтверждена и TrafficEngine
   может реализовать ее по наблюденной kernel форме.
2. **ARCHITECTURE FOLLOW-UP:** kernel/FIB semantics требуют изменить projector или саму
   unavailable-tier модель.

До этого gate runtime unavailable-path projector считается **не разрешенным к реализации**.
