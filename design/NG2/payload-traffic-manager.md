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
          | PayloadRulesState     |<------+
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
    -> PayloadRulesStateCalculator
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
latest_desired_network_rules
latest_published_payload_state
local retry/audit scheduling state   # when scheduler is implemented
```

Исходный `PayloadTrafficStateRequest` после успешного Direct Calculator projection не
хранится: его текущая управляющая семантика полностью представлена
`latest_desired_network_rules`. Это исключает дублирование двух форм одного current
intent.

Допустим технологический cache, если он полностью восстанавливается из текущего desired
ruleset и свежего состояния Adapter.

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

InfoEvent отражает фактически наблюдаемую payload policy, а не историю внутренних
операций.

Точный текущий payload:

```text
PayloadTrafficStateInfo
    rules_state: PayloadRulesState

    profiles[]
        profile_name
        observed_paths: tuple[InterfaceIdentity, ...] | UNKNOWN
```

`rules_state` сообщает aggregate состояние правил по независимым осям.

Per-Profile `observed_paths` сообщает только фактическую routing projection requested
Profile:

- при authoritative observation — concrete ordered paths;
- authoritative отсутствие logical domain — пустой tuple;
- неизвестное/stale observation — UNKNOWN.

Эти paths не являются самостоятельным verdict о здоровье Profile. RuntimeStateManager
комбинирует их с `rules_state`, binding/availability и другими system-level facts в
`ProfileStateCalculator`.

Foreign observed routing domains не публикуются как requested Profiles; их наличие
отражается через divergence/safety rules-state assessment.

Raw `NetworkRulesState` и Linux-specific representation через event boundary не проходят.

Payload rules не сводятся к одному enum. Их состояние оценивается по независимым осям:

```text
PayloadRulesState
    knowledge
        KNOWN | UNKNOWN

    convergence
        MATCHED | DIVERGED | UNKNOWN

    safety
        SAFE | UNSAFE | UNKNOWN

    service
        READY | DEGRADED | ISOLATED | UNKNOWN
```

Смыслы осей:

- **knowledge** — имеется ли достаточно авторитетное текущее наблюдение ruleset;
- **convergence** — совпадает ли observed ruleset с desired ruleset;
- **safety** — доказано ли, что observed ruleset не разрешает запрещенное desired policy
  поведение;
- **service** — какой уровень payload service доказан observed ruleset.

Оси намеренно независимы. В частности, `KNOWN + DIVERGED + UNSAFE` является нормальным
представимым состоянием; физическая работоспособность трафика не превращает unsafe ruleset
в `READY`.

`DEGRADED` допускается только для доказанно safe, но неполной service projection.
`ISOLATED` означает доказанно закрытый payload service. Когда требуемое свойство нельзя
доказать из observed semantic rules, соответствующая ось принимает `UNKNOWN`.

Operation failure сам по себе не является значением ни одной из этих осей.

### 3.5. Request handling

При новой request revision Manager:

```text
1. desired_rules = PayloadRulesCalculator.calculate(request)
2. accepts latest_desired_network_rules as the current managed intent
3. NetworkRulesAdapter.apply(self, desired_rules)
4. if apply failed: NetworkRulesAdapter.renewState(self)
5. network_state = NetworkRulesAdapter.getLastState(self)
6. PayloadRulesStateCalculator.calculate(desired_rules, network_state)
7. project PayloadTrafficStateInfo
8. publish only if semantic InfoEvent payload changed
9. schedule retry/audit later if current state does not satisfy request
```

Pure Calculator rejection happens before the request becomes current managed intent and
before any Adapter mutation. Manager не хранит параллельно исходный request и его compiled
form, поэтому между ними не может возникнуть внутренний drift. Valid RequestEvents
ожидаются от доверенного RuntimeStateManager; invalid/unrepresentable input
рассматривается как processing error, а не как частично принятый intent.

Если `apply()` возвращает FAILURE, решение о дальнейшей реакции принадлежит Manager.

Обычная реакция:

```text
apply(self, ...) -> FAILURE
renewState(self) -> SUCCESS | FAILURE
getLastState(self)
PayloadRulesStateCalculator(desired_rules, network_state)
project/publish actual state
retry according to local policy
```

Результат `renewState()` также не подменяет observation. Даже если обе операции вернули
FAILURE, Manager публикует то состояние, которое можно доказать из `getLastState()`
(обычно UNKNOWN/stale), а не синтетический FAILED verdict.

Adapter failure не является implicit command для RuntimeStateManager.

### 3.6. Drift/audit loop

Пока текущий request не superseded, он остается управляющим intent.

Один audit/reconcile pass:

```text
1. renewState(self)
2. getLastState(self)
3. PayloadRulesStateCalculator(current desired, observed)
4. if convergence != MATCHED:
       apply(self, current desired)
       if apply failed:
           renewState(self)
       getLastState(self)
       recalculate PayloadRulesState
5. project PayloadTrafficStateInfo
6. publish only if semantic state changed
```

Repair определяется **convergence**, а не service severity.

Поэтому:

- `MATCHED + READY` — repair не нужен;
- `MATCHED + DEGRADED` — repair не нужен;
- `MATCHED + ISOLATED` — repair не нужен;
- `DIVERGED` или `convergence=UNKNOWN` — выполняется попытка materialize current desired.

Это критично для zero-path request: защитная изоляция может быть полностью корректной
materialization текущего intent и не должна сама по себе запускать бесконечный repair loop.

Для repair не требуется новый RequestEvent.

Scheduler/cadence audit loop находится вне этого review unit: `audit()` реализует только
один deterministic reconcile pass.

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

    source_nat
        source semantic endpoint
        egress semantic endpoint
        effective packet predicate
        translation target = EGRESS_ADDRESS

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

Payload NAT policy также разрешается до Adapter. Текущее payload-понятие
`MASQUERADE` преобразуется в semantic source translation:

```text
source = LOCAL_NETWORK
egress = concrete path
target = EGRESS_ADDRESS
predicate = effective Profile destination
```

Adapter не получает nft `postrouting`/ `masquerade` vocabulary. Он обязан реализовать
семантику source translation выбранным backend mechanism. `NONE` представлен отсутствием
source-NAT intent.

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

## 9. PayloadRulesStateCalculator

### 9.1. Тип

`PayloadRulesStateCalculator` — Direct Calculator.

Он оценивает **состояние правил обработки payload**, а не состояние payload data plane
вообще.

### 9.2. Contract

```text
calculate(
    desired: NetworkRulesSpec,
    observed: NetworkRulesState
) -> PayloadRulesState
```

Исходный `PayloadTrafficStateRequest` не является входом этого Calculator. Все
payload-domain требования, нужные для оценки ruleset, уже выражены
`PayloadRulesCalculator` в desired `NetworkRulesSpec`.

### 9.3. Responsibility

Calculator переводит normalized network-rules observation обратно в payload-rules
semantics и независимо оценивает:

```text
knowledge
convergence
safety
service
```

Он не выполняет I/O, не вызывает Adapter и не исправляет drift.

### 9.4. Conservative proof rule

Calculator не имеет права выводить `SAFE`, `DEGRADED` или `ISOLATED` по
недоказанному предположению.

Минимальные правила:

- неавторитетное observation -> `knowledge = UNKNOWN`;
- authoritative semantic equality -> `MATCHED + SAFE + READY`;
- authoritative semantic inequality -> `DIVERGED`;
- `UNSAFE` требует доказанного расширения разрешений относительно desired;
- `SAFE` при divergence требует доказательства, что observed policy является только
  ограничением desired policy;
- `DEGRADED` требует доказанного safe partial service;
- `ISOLATED` требует доказанного отсутствия payload service;
- если отношение rulesets нельзя доказать, соответствующие `safety/service` остаются
  `UNKNOWN`.

Такой conservative contract позволяет начать с узкого доказуемого классификатора и
расширять его только вместе с тестами/evidence, не превращая syntactic difference в
необоснованную semantic оценку.

Текущий реализованный proof set дополнительно фиксирует:

- semantic equality не зависит от порядка routing domains, destinations внутри domain и
  allow-only filtering rules; ordered paths и dispatch order остаются значимыми;
- удаление paths с сохранением их relative order и/или удаление существующих allow rules
  может доказать `SAFE`, если dispatch и NAT semantics не изменены;
- такое доказательство restriction **не** доказывает `DEGRADED` service: service остается
  `UNKNOWN`, пока отдельный service proof не покажет реальную потерю capability;
- byte-level allow для endpoint pair, которого desired policy вообще не разрешает, является
  доказанным permission widening и дает `UNSAFE`;
- более тонкие predicate widening/narrowing внутри уже существующего endpoint pair пока не
  классифицируются без отдельного implication proof.

`Safety` относится к permissions ruleset, а не к случайной текущей достижимости пакета.
Поэтому новое разрешение может быть `UNSAFE`, даже если другой defect одновременно мешает
пакету реально пройти.

### 9.5. Future common state-type review

Для `AvailabilityProbeManager` ожидается симметричная пара:

```text
ProbeRulesCalculator
ProbeRulesStateCalculator
```

и собственный `ProbeRulesState`.

ProbeRules semantic lower boundary теперь определена отдельно, но реальная
`ProbeRulesState` всё ещё отсутствует: Linux local-process materialization ожидает
target-confirmation EXP-024.

После появления обеих **исполняемых и наблюдаемых** state-моделей обязателен отдельный
review: если их оси и семантика окажутся принципиально одинаковыми, следует вынести общий
тип состояния rules. До этого момента общий `RulesState` не вводится, чтобы не обобщать
совпадение формы раньше доказанного совпадения предметной семантики.

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

Текущий `NetworkRulesSpec / NetworkRulesState` contract и concrete Linux lower domain
зафиксированы отдельно в `design/NG2/network-rules-adapter.md`.

Для payload/runtime слоя остаются открыты:

1. mapping `PayloadTrafficStateInfo` в окончательный `ProfileStateInfo` внутри
   RuntimeStateManager;
2. audit/retry scheduling policy вокруг уже реализованного deterministic `audit()` pass;
3. richer divergent predicate implication только там, где появится реальная необходимость;
4. после реализации `ProbeRulesState` — review на предмет общего rules-state type;
5. remaining runtime assembly above the implemented protective startup gate; forwarding
   closure до первого owner reconcile зафиксирован в `runtime-bootstrap.md`.

Adapter boundary остается фиксированной: Linux transaction machinery не должна снова
протекать в PayloadTrafficManager.
