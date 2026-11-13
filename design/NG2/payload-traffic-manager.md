# VPN-GATE NG2 — PayloadTrafficManager decomposition

**Статус:** нормативный проект NG2  
**Дата:** 2026-11-14  
**Область:** steady-state payload traffic management  
**Общие модели:** `design/component-model.md`, `design/NG2/runtime-event-model.md`

Документ фиксирует границы и контракты компонентов `PayloadTrafficManager`.

Цель декомпозиции — отделить:

1. payload semantics VPN-GATE;
2. преобразование payload intent в абстрактные network rules;
3. безопасную материализацию network rules в конкретный сетевой стек.

Linux route/RPDB/nft/sysctl mechanics не являются частью payload domain.

## 1. Архитектурная схема

```text
                    asynchronous event space

                 PayloadTrafficStateRequest
                            |
                            v
                 +-----------------------+
                 | PayloadTrafficManager |
                 +-----+------------+----+
                       |            |
                 sync  |            | sync
                       v            v
          +------------------+   +-----------------------+
          | PayloadRules     |   | NetworkRulesAdapter   |
          | Calculator       |   +-----------------------+
          +------------------+       ^              |
                                     |              |
                               sync  |              | hidden lower domain
                                     |              v
          +------------------+       |        network stack / drivers
          | PayloadState     |<------+
          | Calculator       |
          +------------------+
                       |
                       v
                 PayloadTrafficStateInfo

                    asynchronous event space
```

Все Machinery в текущем VPN-GATE NG2 ожидаются Direct. Никаких Indirect-компонентов в
этой декомпозиции нет.

Синхронный dependency graph:

```text
PayloadTrafficManager
    -> PayloadRulesCalculator
    -> PayloadStateCalculator
    -> NetworkRulesAdapter
```

ацикличен. Внутреннее устройство `NetworkRulesAdapter` находится за Adapter boundary и
не входит в граф payload domain.

## 2. Предмет управления PayloadTrafficManager

`PayloadTrafficManager` управляет **семантически наблюдаемой политикой прохождения
payload traffic**.

В его область входят:

- какие Profiles должны иметь payload forwarding;
- через какие concrete interface identities каждый Profile сейчас может передавать
  payload;
- приоритет путей;
- Profile destinations;
- разрешенные направления новых соединений;
- Device traffic envelopes;
- payload NAT intent;
- требование terminal fail-close для недоставленного трафика;
- итоговая семантически значимая проекция фактически материализованной payload policy.

В его область **не** входят:

- VPN process lifecycle;
- interface discovery;
- availability probe execution;
- publication relay workers;
- numeric Linux routing-table IDs;
- numeric RPDB priorities;
- numeric route metrics;
- nft table/chain names;
- nft syntax;
- route/nft/sysctl command ordering;
- transition/barrier phases;
- конкретные network-stack verification commands.

## 3. PayloadTrafficManager

### 3.1. Тип

`PayloadTrafficManager` — **Manager**, следовательно Engine.

Он подписывается на RequestEvents, самостоятельно поддерживает свою managed domain,
использует Machinery синхронно и публикует InfoEvents.

### 3.2. Input

Основной вход:

```text
PayloadTrafficStateRequest
```

Request является полной актуальной desired projection и supersede'ит предыдущую revision.

Семантически request содержит:

```text
Profiles participating in payload traffic
Profile destinations
Profile direction policy
current usable/bound concrete interfaces per Profile
ordering/preference of usable paths
Device traffic envelopes
Device NAT policy
other payload-semantic requirements
```

Request не содержит технической materialization information.

### 3.3. Internal current state

Manager хранит только явно значимое текущее состояние:

```text
latest_request
latest_desired_network_rules
latest_published_payload_state
local retry/audit scheduling state
```

Допустим технологический cache, если он полностью восстанавливается из текущего request и
свежего состояния Adapter.

Manager не хранит как собственную semantic history:

- committed numeric metrics;
- previous Linux table allocations;
- previous nft generations;
- previous transition kind;
- persisted interface admission history.

### 3.4. Output

Manager публикует:

```text
PayloadTrafficStateInfo
```

Только при семантически значимом изменении.

InfoEvent отражает фактически установленную payload policy, а не историю внутренних
операций.

Минимально проекция должна позволять верхнему runtime установить:

- соответствует ли фактическая payload policy текущему request;
- какие Profile capabilities фактически доступны;
- находится ли payload domain в защитно ограниченном состоянии;
- известно ли вообще текущее состояние с достаточной уверенностью.

Рабочие категории состояния:

```text
READY
DEGRADED
ISOLATED
UNKNOWN
```

Точный serialization enum может быть уточнен отдельно, но семантика различий нормативна:

- **READY** — запрошенная payload policy полностью материализована и подтверждена;
- **DEGRADED** — подтверждена безопасная, но неполная относительно request payload policy;
- **ISOLATED** — payload forwarding фактически защитно закрыт;
- **UNKNOWN** — Manager не может доказать текущее состояние с достаточной полнотой.

Operation failure сам по себе не является state category.

### 3.5. Request handling

При новой request revision Manager:

```text
1. stores latest request
2. PayloadRulesCalculator.calculate(request)
3. NetworkRulesAdapter.apply(self, desired_rules)
4. inspects action result
5. obtains authoritative last Adapter state for self
6. PayloadStateCalculator.calculate(request, desired_rules, network_state)
7. publishes changed PayloadTrafficStateInfo
8. schedules retry/audit if current state does not satisfy request
```

Если `apply()` возвращает FAILURE, решение о дальнейшей реакции принадлежит Manager.

Обычная реакция:

```text
apply(self, ...) -> FAILURE
renewState(self)
getLastState(self)
PayloadStateCalculator(...)
publish actual state
retry according to local policy
```

Adapter failure не является implicit command для RuntimeStateManager.

### 3.6. Drift/audit loop

Пока текущий request не superseded, он остается управляющим intent.

Manager периодически или по локальному trigger проверяет managed domain:

```text
renewState(self)
    |
getLastState(self)
    |
compare/interpret against current desired rules
    |
if drift:
    apply(current desired rules)
    |
publish changed semantic state
```

Для repair не требуется новый RequestEvent.

## 4. PayloadRulesCalculator

### 4.1. Тип

`PayloadRulesCalculator` — Direct Calculator.

Он не выполняет I/O, не публикует Events и не имеет скрытой исторической зависимости.

### 4.2. Contract

```text
calculate(PayloadTrafficStateRequest) -> NetworkRulesSpec
```

Одинаковый explicit input обязан давать эквивалентный semantic output.

### 4.3. Responsibility

Calculator переводит payload domain в network-rules domain.

Он определяет:

- logical routing domains для Profiles;
- destinations каждого routing domain;
- ordered usable paths;
- logical dispatch/selection rules;
- terminal action для недоставленного трафика;
- new-flow admission policy;
- Device traffic-envelope effects;
- NAT intent;
- необходимость payload packet forwarding как capability.

### 4.4. What it must not calculate

Calculator не назначает:

- Linux table IDs;
- RPDB numeric priorities;
- route metrics;
- route protocol numbers;
- nft names/priorities;
- nft textual rules;
- sysctl paths;
- mutation ordering;
- transition classifications.

### 4.5. Path ordering

Payload domain выражает только semantic preference:

```text
path A
path B
path C
```

или эквивалентное partial/total ordering.

Конкретное numeric representation приоритета принадлежит NetworkRulesAdapter.

Следовательно, старые NG1 `TrafficRuntimeState.normal_metrics` и
`MetricAssignment.metric` не являются частью этого Calculator contract.

## 5. NetworkRulesSpec

`NetworkRulesSpec` — контракт на границе payload domain -> network-rules domain.

Это **не** Linux desired state.

Концептуально он содержит:

```text
NetworkRulesSpec
    routing_domains
        logical_domain_id
        destinations
        ordered_paths
        terminal_disposition

    dispatch_policy

    traffic_allows
        source/destination semantic endpoints
        effective packet predicates

    flow_initiation_allows
        source/destination semantic endpoints
        effective packet predicates

    nat_policy
        none / masquerade intent
        applicable paths/destinations

    forwarding_requirement
```

Filtering contract является allow-only: отсутствие разрешения означает deny. Явные deny
rules из payload domain в Adapter не передаются.

Два набора разрешений имеют разный смысл:

- `traffic_allows` описывает, какие байты вообще допустимы между semantic endpoints;
- `flow_initiation_allows` дополнительно описывает, какой допустимый трафик может
  инициировать новый stateful flow.

Routing fail-close также выражается семантически: `DROP` / `REJECT`, а не Linux route
types. В частности, payload zero-path использует `DROP`; конкретный `blackhole` route,
его metric и прочая materialization принадлежат Adapter.

Новый flow должен удовлетворять обоим наборам. Обратный трафик уже разрешенного flow не
моделируется верхней предметной областью отдельно: conntrack/stateful realization,
`ESTABLISHED/RELATED`, invalid-state handling и порядок firewall rules принадлежат
network-stack domain за Adapter.

Device traffic envelope полностью разрешается в `PayloadRulesCalculator` до Adapter.
В том числе first-match `allow/drop + default` политика преобразуется в effective
allow-predicate; Adapter не знает понятий Profile direction и Device envelope.

Верхний контракт также не называет инфраструктурный Linux-интерфейс вроде `host0`.
Host-facing сторона представляется semantic endpoint `LOCAL_NETWORK`, а ее конкретная
Linux materialization принадлежит Adapter.

Concrete VPN-path interface identity остается generation-aware:

```text
(ifname, ifindex)
```

потому что различение same-name/new-ifindex является частью системной семантики,
подтвержденной EXP-017.

### 5.1. Что намеренно отсутствует

В `NetworkRulesSpec` отсутствуют:

```text
table_id
rpdb_priority
route_metric
route_protocol_number
nft_table_name
nft_chain_name
nft_rule_text
sysctl_command
transition_kind
barrier_phase
```

## 6. NetworkRulesAdapter

### 6.1. Тип

`NetworkRulesAdapter` — Direct Adapter.

Он является границей между:

```text
payload/network-rules semantic model
        |
        v
concrete networking subsystem
```

Все, что находится за этой границей, для PayloadTrafficManager считается внутренней
реализацией Adapter.

### 6.2. Trusted contract

Компоненты разрабатываются совместно и по умолчанию доверяют друг другу.

Caller не диктует Adapter:

- безопасный mutation order;
- когда закрывать forwarding barrier;
- как проверять nft generation;
- как аллоцировать Linux identifiers;
- как проводить rollback/rebuild;
- какие Drivers использовать.

Adapter обязан сам корректно реализовать собственную domain semantics.

### 6.3. Public methods

Минимальный контракт:

```text
apply(owner, spec: NetworkRulesSpec) -> ActionResult

renewState(owner) -> ActionResult

getLastState(owner) -> NetworkRulesState

cleanup(owner) -> ActionResult
```

`owner` — opaque identity экземпляра caller. Обычный caller передает собственную identity
(`self` / `&self` в терминах реализации). Adapter использует ее только для разделения
ownership и не интерпретирует имя, тип или предметный смысл caller.

Нормативно:

- тот же instance identity означает тот же owned scope;
- другой instance identity означает другой owned scope;
- identity действует только в пределах lifetime caller instance;
- `NetworkRulesSpec` не содержит owner/scope и описывает только требуемые правила;
- один owner не может удалить или перезаписать effective state другого owner.

`cleanup(owner)` является lifecycle-operation, а не удалением ссылки из cache. Она
идемпотентна. SUCCESS означает, что Adapter больше не имеет effective state или ресурсов
данного owner, способных влиять на внешнюю среду; при необходимости Adapter пересобирает
общую physical policy без удаленного owner.

Дополнительные методы допустимы только при отдельной смысловой необходимости.

### 6.4. ActionResult

`ActionResult` отвечает только на вопрос об операции, вызванной caller:

```text
SUCCESS
FAILURE + diagnostic
```

Он не заменяет `NetworkRulesState`.

#### apply()

```text
apply(owner, spec) -> SUCCESS
```

означает:

> Adapter завершил операцию materialization по своему контракту и свежо подтвердил, что
> управляемая им network-rules projection соответствует переданному spec.

На SUCCESS:

- desired rules materialized;
- required post-apply verification completed;
- `getLastState()` отражает свежую подтвержденную projection.

```text
apply(spec) -> FAILURE
```

означает:

> Adapter не смог гарантировать успешное завершение requested materialization.

FAILURE не сообщает caller, какое итоговое semantic состояние payload domain следует
вывести. Это решает Manager после observation.

Adapter не имеет права выдавать SUCCESS на основании только успешного выполнения команд без
fresh verification.

#### renewState()

```text
renewState(owner) -> SUCCESS
```

означает:

> Adapter свежо наблюдал весь принадлежащий ему network-rules scope и обновил explicit
> last-state projection.

```text
renewState() -> FAILURE
```

означает:

> Adapter не смог получить достаточно полное/надежное текущее наблюдение.

После FAILURE `getLastState()` обязан явно отражать, что current state не является
authoritative fresh observation.

#### getLastState()

`getLastState(owner)`:

- не выполняет внешнего I/O;
- возвращает последнюю явно поддерживаемую Adapter projection;
- не скрывает от caller факт UNKNOWN/stale observation;
- не требует знания неявной истории Adapter calls.

Это explicit state contract и не противоречит externally-stateless Machinery.

## 7. NetworkRulesState

`NetworkRulesState` — нормализованная наблюдаемая проекция network-rules domain.

Он не должен протекать Linux implementation details наверх.

Концептуально:

```text
NetworkRulesState
    knowledge
        KNOWN | UNKNOWN

    observed_rules
        same semantic vocabulary as NetworkRulesSpec where representable

    diagnostics
        optional opaque/detail information
```

Если техническое состояние нельзя надежно преобразовать обратно в semantic network-rules
model, Adapter возвращает `knowledge = UNKNOWN`, а технические подробности оставляет
диагностике.

PayloadTrafficManager не обязан разбирать raw nft/iproute output.

## 8. Внутренняя ответственность NetworkRulesAdapter

Эта секция фиксирует обязательные свойства Adapter, но не раскрывает их как caller API.

Adapter самостоятельно отвечает за:

### 8.1. Technical allocation

Преобразование logical identifiers в concrete Linux representation:

- Profile/logical routing domain -> routing table ID;
- semantic dispatch order -> RPDB priorities;
- ordered paths -> safe numeric route metrics/other kernel representation;
- logical filter/NAT policies -> nft objects.

Стабильность технических назначений может поддерживаться на основании наблюдаемой внешней
среды и внутреннего explicit cache Adapter.

PayloadTrafficManager не хранит такую историю.

### 8.2. Safe transition

Adapter знает свойства конкретного сетевого стека и сам выбирает безопасную mutation
sequence.

Внутри допустимы:

```text
incremental transition
structural rebuild
barrier close
route/rule mutation
NAT-before-admission ordering
fresh verification
barrier reopen
best-effort protective close on failure
```

Эти понятия не являются payload-domain contract.

### 8.3. Fresh verification

Любой SUCCESS materialization должен подтверждаться новым observation после mutation.

Это напрямую следует из EXP-012.

### 8.4. Generation-aware interface materialization

Concrete dynamic interface references должны учитывать `(ifname, ifindex)`.

EXP-017 запрещает считать same-name/new-ifindex той же самой interface generation.

### 8.5. Drift representation

Чужое/неожиданное состояние внутри owned scope не должно молча canonicalize'иться как
desired.

Если Adapter не может надежно представить или классифицировать observed state, он сообщает
UNKNOWN через `NetworkRulesState`.

### 8.6. Owner isolation и physical composition

Semantic state разных owners хранится и наблюдается раздельно.

Если Linux backend требует общий enforcement point, Adapter самостоятельно композитит
актуальные allow rules всех owners в physical policy. Типовая materialization может иметь
отдельные owner chains, возвращающие управление для чужого трафика, и общий terminal deny.

Это backend mechanics. PayloadTrafficManager, AvailabilityProbeManager и другие callers
не знают друг о друге и не передают в `NetworkRulesSpec` сведения о соседних owners.

`apply(owner, ...)`, `renewState(owner)` и `cleanup(owner)` обязаны сохранять state
остальных owners.

## 9. PayloadStateCalculator

### 9.1. Тип

`PayloadStateCalculator` — Direct Calculator.

### 9.2. Contract

```text
calculate(
    request: PayloadTrafficStateRequest,
    desired: NetworkRulesSpec,
    observed: NetworkRulesState
) -> PayloadTrafficState
```

### 9.3. Responsibility

Calculator переводит фактическую network-rules projection обратно в payload semantics.

Он определяет:

- полностью ли request materialized;
- какие Profile paths/capabilities подтверждены;
- является ли наблюдаемая policy безопасной, но неполной;
- закрыт ли payload forwarding;
- достаточно ли данных для authoritative state.

### 9.4. Rules

Если `NetworkRulesState.knowledge == UNKNOWN`, Calculator не имеет права вывести READY.

READY требует semantic equivalence observed rules и desired spec.

DEGRADED допустим только если Calculator способен доказать безопасную неполную payload
projection.

ISOLATED означает доказанное отсутствие payload forwarding capability, а не просто
operation failure.

## 10. Error semantics

### 10.1. Machinery failure

Calculator failure означает invalid/unrepresentable explicit input и рассматривается как
Manager-local processing failure.

Adapter action FAILURE означает только неуспех конкретной synchronous operation.

### 10.2. Manager reaction

Только PayloadTrafficManager решает:

- retry immediately;
- retry later;
- request fresh state;
- publish DEGRADED/ISOLATED/UNKNOWN;
- логировать/escalate diagnostic failure.

Нижняя Machinery не публикует PayloadTrafficStateInfo самостоятельно.

## 11. Evidence constraints

### EXP-012

Подтверждает для Adapter:

- drift must be observed;
- structural/unknown repair requires protective barrier;
- verification after apply is mandatory;
- forwarding may reopen only after complete fresh verification;
- failure path must remain fail-closed.

### EXP-013 / EXP-016

Подтверждают Linux route/FIB mechanics.

Они не возвращают отмененные NG1 concepts:

- shadow unavailable routes;
- UNAVAILABLE_METRIC;
- userspace sequential fallback semantics.

### EXP-017

Подтверждает numeric-ifindex generation-aware filtering и необходимость отличать
same-name/new-ifindex.

### EXP-014

Multi-path inbound flow pinning не считается production-proven capability.

Текущая декомпозиция не вводит новый flow-pinning mechanism.

### EXP-015

MSS/MTU clamping не добавляется без отдельного доказательства необходимости.

### EXP-023

Подтверждает, что Profile-local availability может изменяться при неизменной interface
identity. Это влияет на `PayloadTrafficStateRequest`, но probe execution остается за
`AvailabilityProbeManager`.

## 12. Mapping старого NG1 к NG2

Предварительная карта ответственности:

```text
NG1 device_engine.py
    -> НЕ PayloadTrafficManager
       selection/binding moved to RuntimeStateManager calculators

NG1 traffic_state.py
    -> metric-history architecture removed from PayloadTrafficManager
       technical allocation belongs behind NetworkRulesAdapter

NG1 route_intent.py
NG1 firewall_intent.py
    -> semantic material for PayloadRulesCalculator

NG1 kernel_allocation.py
NG1 kernel_state.py
NG1 kernel_mutation.py
NG1 transition.py
    -> NetworkRulesAdapter hidden lower domain

NG1 nft_policy.py
    -> split:
       semantic policy compilation -> PayloadRulesCalculator where genuinely payload-specific
       nft materialization/observe/verify -> behind NetworkRulesAdapter

NG1 planner.py
    -> central orchestration disappears
       payload-domain orchestration -> PayloadTrafficManager
       network transaction/materialization -> NetworkRulesAdapter
```

## 13. Инварианты

1. PayloadTrafficManager не знает concrete Linux allocation identifiers.
2. PayloadTrafficManager не командует transaction phases Adapter.
3. NetworkRulesAdapter не знает Profile satisfaction policy.
4. Adapter action result не подменяет observation state.
5. `apply() == SUCCESS` требует fresh verified materialization.
6. `renewState()` и `getLastState()` являются явным state contract.
7. Caller не зависит от скрытой истории Adapter.
8. Technical allocation history не является PayloadTrafficManager state.
9. Same-name/new-ifindex считается новой concrete interface identity.
10. Operation failure интерпретирует Manager, не Adapter.
11. Current request действует до superseding revision.
12. Drift repair не требует нового RequestEvent.
13. Синхронный dependency graph payload domain ацикличен.
14. Нижняя domain за NetworkRulesAdapter не имеет independent synchronous back-edge в
    payload domain.

## 14. Пока открыто

Следующий проход должен определить точный data contract:

1. `NetworkRulesSpec`:
   - representation routing domains;
   - path ordering;
   - dispatch semantics;
   - flow policy;
   - NAT policy;
   - terminal actions;
2. `NetworkRulesState`:
   - степень normalization observed state;
   - representation unrepresentable/foreign state;
3. `PayloadTrafficStateInfo`:
   - точный per-Profile payload;
   - окончательные enum/reason codes;
4. audit/retry timing policy PayloadTrafficManager;
5. внутреннюю декомпозицию `NetworkRulesAdapter` в его собственной предметной области.

До этого момента Adapter boundary считается фиксированной: Linux transaction machinery не
должна снова протекать в PayloadTrafficManager.
