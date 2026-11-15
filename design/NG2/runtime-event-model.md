# VPN-GATE NG2 — событийная модель runtime

> **2026-11-15 availability-path update:** the active-probe collector -> route-materializer
> path is intentionally synchronous and aggregate-based as specified by
> `design/NG2/availability-collector-materializer.md`. It does not require EventEnvelope
> revision/epoch ordering. The general Event Delivery model below remains applicable to
> genuinely asynchronous latest-value streams elsewhere in runtime.

**Статус:** нормативный проект NG2  
**Дата:** 2026-11-13  
**Область:** steady-state runtime после успешного startup и до начала shutdown  
**Общая компонентная модель:** `design/component-model.md`

Документ описывает события и Engines верхнего уровня VPN-GATE NG2. Внутренняя
декомпозиция Managers и их Machinery рассматривается отдельными документами.

Bootstrap/startup/shutdown находятся вне steady-state scope этого документа. Минимальная
protective startup boundary для Linux network policy зафиксирована отдельно в
`design/NG2/runtime-bootstrap.md`.

## 1. Основная петля

Runtime сопоставляет:

- нормализованную конфигурацию;
- текущие наблюдения внешней среды;
- текущие состояния Managers;
- встроенную policy VPN-GATE.

Общий поток:

```text
InfoEvents
    |
    v
RuntimeStateManager
    |
    v
CurrentRuntimeSnapshot
    |
    v
Calculators(config, policy, snapshot)
    |
    +--> RequestEvents --> Managers
    |
    +--> InfoEvents ----> status/diagnostics
                            |
                            v
                  environment changes
                            |
                            +--> InfoEvents
```

Runtime не требует единого процедурного global reconcile call.

## 2. Engines верхнего уровня

### 2.1. RuntimeStateManager

`RuntimeStateManager` — Manager общей runtime-проекции VPN-GATE.

Он:

1. подписывается на системно значимые InfoEvents;
2. хранит latest known projections текущего runtime epoch;
3. собирает `CurrentRuntimeSnapshot`;
4. применяет Calculators к snapshot + config + policy;
5. публикует изменившиеся RequestEvents;
6. публикует вычисленные системные InfoEvents;
7. не управляет Linux networking или probe machinery непосредственно.

Latest-value storage является cache текущего мира, а не историческим журналом.

RuntimeStateManager остается владельцем общей structural/configuration
проекции, но больше не является посредником availability hysteresis для route priority.

Runtime-derived association logical probes with Profiles может по-прежнему вычисляться и
валидироваться из configuration/interface state, однако текущие availability-problems counters/latches
не проходят цепочку `AvailabilityProbeStateInfo -> RuntimeStateManager ->
PayloadTrafficStateRequest`.

Raw current good-news/tick observations поступают в bounded input port
`PayloadTrafficManager`, который сам владеет availability collector state для route
priority. Поэтому EventEnvelope ordering не требуется для этой availability path.

### 2.2. InterfaceObservationAgent

`InterfaceObservationAgent` наблюдает runtime network interfaces.

Он публикует актуальную проекцию релевантных интерфейсов, включая как минимум:

- ifname;
- ifindex;
- kernel flags/properties, необходимые policy;
- адресные данные, если они реально нужны runtime policy.

Concrete interface identity:

```text
(ifname, ifindex)
```

Same-name/new-ifindex означает новую concrete interface identity.

Agent не выполняет Device admission и не определяет Profile binding.

### 2.3. AvailabilityProbeManager

`AvailabilityProbeManager` управляет physical active-probe domain:

- desired logical probe set;
- probe-specific NetworkRules;
- rules/readiness lifecycle;
- current concrete physical generation;
- execution demand for `ProbeExecutionAgent`.

Он не владеет routing hysteresis, availability-problems channel counters или payload route priority.

### 2.4. ProbeExecutionAgent

`ProbeExecutionAgent` исполняет current physical probe demand.

Он владеет physical send cadence, bounded workers, stale physical-generation rejection и
local execution diagnostics. Для availability collector он производит только:

```text
good_news(current channel)
tick(current logical channel)
```

Good news increment bounded counters; tick sets a boolean pending fact. Neither input is a
journal item requiring replay ordering. `NO_REPLY` remains absence of good news; local
execution ERROR remains diagnostic only.

Logical observation windows, `evidence_epoch`, `elapsed_intervals` and boundary
catch-up are not part of the target runtime model. Exact aggregation and transition rules
are normative in `design/NG2/availability-collector-materializer.md`.

### 2.5. PayloadTrafficManager

`PayloadTrafficManager` управляет payload network policy VPN-GATE. Его внутренняя
декомпозиция и Machinery contracts зафиксированы в
`design/NG2/payload-traffic-manager.md`.

Его предметная область включает только правила, определяющие payload forwarding:

- Profile routing/RPDB;
- payload filtering;
- payload NAT;
- payload forwarding safety;
- необходимые payload-related network prerequisites.

Он не управляет:

- VPN-процессами;
- availability probe subsystem;
- transport publication workers;
- Profile satisfaction.

Внутренняя безопасная материализация rules, verification, barriers и работа с Linux
networking скрыты внутри Manager/Machinery и не входят в event contract верхнего уровня.

### 2.6. PublicationManager

`PublicationManager` управляет transport publication subsystem:

- published TCP/UDP endpoints;
- relay/listener workers;
- соответствующий lifecycle;
- фактическое состояние publication.

Он не владеет payload routing и не определяет Profile policy.

Если публикации требуется kernel network admission, это отдельная network-rules
ответственность, а не причина считать relay machinery частью PayloadTrafficManager.

## 3. Отсутствие DeviceManager в текущем runtime

Текущий NG2 runtime **не управляет VPN Device processes/adapters**.

VPN machinery запускается и поддерживается внешними механизмами/администратором. Runtime
наблюдает результат через InterfaceObservationAgent.

Поэтому в текущем scope отсутствуют:

```text
DeviceManager
DeviceStateRequest
DeviceStateInfo
DeviceCapacityCalculator
```

`Device` остается конфигурационным понятием, связывающим ожидаемые interfaces и
traffic/publication policy.

Future Device lifecycle management может ввести отдельный Manager, когда daemon реально
получит actuator mechanisms для создания/остановки/масштабирования VPN machinery.

## 4. Event Delivery Environment

Все Engines связаны через Event Delivery Environment.

Она:

- доставляет Events согласно subscriptions;
- не интерпретирует domain semantics;
- не выполняет policy;
- не является source of truth;
- не превращает RequestEvent в RPC.

Повторная доставка одинаковой текущей проекции должна быть безопасна.

## 5. Event envelope

Концептуально:

```text
EventEnvelope
    kind            INFO | REQUEST
    type
    publisher
    subject
    runtime_epoch
    revision
    event_id
    caused_by       optional
    published_at    diagnostic only
    payload
```

Правила:

1. новый daemon run получает новый `runtime_epoch`;
2. `revision` монотонна в пределах publisher + type + subject + epoch;
3. более старая revision одной state projection игнорируется;
4. `caused_by` используется для диагностики/correlation, но не заменяет observation;
5. timestamp не является единственным ordering mechanism.

## 6. RequestEvent semantics

RequestEvent выражает актуальное управляющее намерение.

Для одного subject:

```text
revision 10 -> desired A
revision 11 -> desired B
```

означает, что B заменяет A.

Manager:

- принимает latest request как текущий управляющий input;
- сам отвечает за локальную convergence policy;
- не требует повторного request для каждого retry;
- публикует текущую managed-domain projection как InfoEvent.

Superseding RequestEvent обновляет desired state, но не обязан прерывать уже начатую
нижнеуровневую transaction. Для transaction-scoped Machinery действует правило:

```text
running transaction
    -> immutable current -> target plan
newer request
    -> latest/pending desired only
transaction verified complete
    -> converge from verified result to latest desired
```

В частности, availability-driven route-priority materialization сериализуется в scope
Profile/routing-domain: два route move plans одного Profile не выполняются одновременно и
не interleave commands.

RequestEvent не требует непосредственного response.

## 7. InfoEvent semantics

InfoEvent сообщает актуальную системно значимую проекцию publisher.

Для current-state streams обычно действует:

```text
newer publication supersedes older publication
for same publisher/type/subject/epoch
```

Низкоуровневый operation failure не обязан становиться системным event, если Manager может
выразить его через более содержательное текущее состояние своей области.

## 8. Каталог событий

### 8.1. InterfaceInventoryInfo

**Kind:** InfoEvent  
**Publisher:** InterfaceObservationAgent  
**Subscribers:** RuntimeStateManager  
**Subject:** runtime interface inventory  
**Publication mode:** full snapshot

Содержит актуальный набор релевантных concrete interfaces и свойства, необходимые
Calculators.

Не содержит:

- admission;
- Profile binding;
- availability verdict.

### 8.2. AvailabilityProbeSetRequest

**Kind:** RequestEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** AvailabilityProbeManager  
**Subject:** availability probe set  
**Publication mode:** full desired snapshot

Определяет полный набор logical probes, которые runtime сейчас требует поддерживать.

Текущий normalized contract:

```text
probe_id
ICMP mechanism
concrete InterfaceIdentity
IPv4 target
enabled
AvailabilityChannelPolicy
    interval_seconds
    failure_ticks
    recovery_good_news
```

`enabled=false` сохраняет настроенный logical probe, но запрещает автономное probing.
Physical ProbeRules вычисляются только из enabled probes. Поэтому disable последнего
logical consumer закрывает соответствующий physical plane, а disable одного из нескольких
consumers общего plane не меняет его. Logical probe config при этом сохраняется. Policy обязателен для каждого normalized logical probe; policy-less manual mode удален.

`ProbeRulesCalculator` дедуплицирует physical plane по
`(mechanism, InterfaceIdentity, target)`. Timing/enable policy не является physical
NetworkRules semantics.

Production availability policy не коррелирует reply с semantic attempt id. Valid replies
являются colorless good-news units; logical timer firing является только pending tick
fact. availability-problems hysteresis принадлежит PayloadTrafficManager collector и задается
`design/NG2/availability-collector-materializer.md`.

Новая revision заменяет предыдущий desired set.

### 8.3. Availability diagnostic projection

`AvailabilityProbeStateInfo` больше не является routing-control Event contract.

Во время миграции implementation может продолжать публиковать probe diagnostics/status,
но RuntimeStateManager не использует их для вычисления route priority. Routing-relevant
availability-problems state находится внутри PayloadTrafficManager collector.

### 8.4. PayloadTrafficStateRequest

**Kind:** RequestEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** PayloadTrafficManager  
**Subject:** complete payload traffic domain  
**Publication mode:** full desired snapshot

Содержит семантическое желаемое payload traffic state:

```text
Profiles participating in payload
selected/bound concrete interfaces per Profile
configured/base path order per Profile
availability channel assignment/policy per Profile
Profile directions
Profile destinations
Device traffic-policy references
required payload forwarding intent
```

Не содержит технических command sequences:

```text
ip route add/del
ip rule add/del
nft command sequence
sysctl command sequence
transaction phases
verification phases
```

Все это принадлежит внутренней реализации PayloadTrafficManager и его Machinery.

Effective availability order и transient live-prefix boundary являются внутренним current
state PayloadTrafficManager. Они не являются полями normalized user configuration и не
передаются как готовая availability projection через PayloadTrafficStateRequest. Никакой
EMPTY route/metric object в RequestEvent не существует.

### 8.5. PayloadTrafficStateInfo

**Kind:** InfoEvent  
**Publisher:** PayloadTrafficManager  
**Subscribers:** RuntimeStateManager; diagnostics/status  
**Subject:** payload traffic domain  
**Publication mode:** current state snapshot

Публикует системно значимое состояние payload traffic domain.

Текущий payload event contract:

```text
PayloadTrafficStateInfo
    rules_state: PayloadRulesState
        knowledge
        convergence
        safety
        service

    profiles[]
        profile_name
        observed_paths: tuple[InterfaceIdentity, ...] | UNKNOWN
```

`PayloadRulesState` является многомерным state, а не единым READY/FAILED enum.

`observed_paths` — факт текущей materialized routing projection для requested Profile,
не verdict о корректности Profile. При неизвестном authoritative rules observation paths
тоже UNKNOWN; при авторитетном отсутствии requested logical routing domain публикуется
пустой список paths.

Raw `NetworkRulesState`, Linux route/RPDB/nft details и foreign logical domains в этот
InfoEvent не входят.

Manager вправе локально fail-close при недоказанной безопасности и затем опубликовать
фактическое состояние.

### 8.6. PublicationStateRequest

**Kind:** RequestEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** PublicationManager  
**Subject:** publication domain  
**Publication mode:** full desired snapshot

Определяет желаемые publication endpoints в предметных терминах.

### 8.7. PublicationStateInfo

**Kind:** InfoEvent  
**Publisher:** PublicationManager  
**Subscribers:** RuntimeStateManager; diagnostics/status  
**Subject:** publication domain  
**Publication mode:** current state snapshot

Публикует фактическое системно значимое состояние transport publication.

### 8.8. ProfileStateInfo

**Kind:** InfoEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** status/log/UI/diagnostics  
**Subject:** Profile  
**Publication mode:** current state per Profile

Публикует вычисленное текущее состояние Profile.

Полный status/severity model фиксируется отдельно.

## 9. CurrentRuntimeSnapshot

Концептуально:

```text
CurrentRuntimeSnapshot
    normalized_config

    interface_inventory
    availability_probe_states

    payload_traffic_state
    publication_state

    derived/current policy projections
```

Каждая projection до первой корректной публикации имеет состояние UNKNOWN.

UNKNOWN нельзя молча трактовать как:

- пустой interface set;
- probe failure;
- успешный empty payload state;
- успешную publication absence.

Неопределенность, способная расширить payload exposure, обрабатывается fail-closed.

## 10. Calculators RuntimeStateManager

Calculators являются Machinery, а не Engines.

### 10.1. InterfaceSelectionCalculator

Вход:

- Device expected-interface configuration;
- current interface inventory;
- current selection, если она нужна для survivor preservation внутри одного daemon run;
- selector quotas.

Выход:

- selected/admitted concrete interfaces.

Независимые daemon runs не наследуют persisted candidate history.

### 10.2. BindingCalculator

Вход:

- selected interfaces;
- Profiles;
- обязательные non-probe eligibility conditions.

Выход:

```text
IsBound(concrete_interface, Profile) -> bool
```

Availability probe evidence **не** является условием binding membership.

Binding исчезает по структурной/административной причине, а не потому, что active probe
не подтвердил достижимость. Это гарантирует, что probing не может самостоятельно удалить
последний настроенный путь.

### 10.3. AvailabilityProbeDemandCalculator

Вход:

- config;
- selected interfaces;
- Profile balancing requirements.

Выход:

- полный desired set для `AvailabilityProbeSetRequest`.

### 10.4. PayloadTrafficIntentCalculator

Вход:

- config и configured/base path priority;
- binding matrix;
- availability channel assignment/policy;
- другие structural runtime facts.

Выход:

- semantic structural payload projection для `PayloadTrafficStateRequest`.

Calculator больше не принимает current availability probe states и не вычисляет готовый
effective `ordered_paths`. current availability-problems state, effective order и live-prefix boundary
принадлежат PayloadTrafficManager collector/materializer flow.

## 11. Recalculation RuntimeStateManager

При новом InfoEvent:

```text
1. validate epoch/revision/subject
2. replace latest projection
3. rebuild affected CurrentRuntimeSnapshot view
4. run affected Calculators
5. compare with last published outputs
6. publish only semantically changed Events
7. update diagnostic cache
```

Полный пересчет допустим; partial dependency recalculation — оптимизация.

Повторный одинаковый input не должен создавать event storm.

## 12. Основные feedback loops

### 12.1. Появление интерфейса

```text
external interface change
        |
        v
InterfaceObservationAgent
        |
        +-- InterfaceInventoryInfo
                |
                v
        RuntimeStateManager
                |
                +-- selection
                +-- binding
                +-- availability probe demand
                +-- payload traffic intent
                |
                +-- AvailabilityProbeSetRequest
                |       -> AvailabilityProbeManager
                |
                +-- PayloadTrafficStateRequest
                        -> PayloadTrafficManager
```

### 12.2. Availability evidence changes

`AvailabilityProbeManager` derives generation-bound execution demand from current READY
ProbeRules. `ProbeExecutionAgent` executes physical sends and logical tick cadence.

Producer-facing observations are aggregated directly into bounded
PayloadTrafficManager-owned channel input:

```text
valid current reply -> pending_good_news += 1 (saturating)
logical timer fire  -> tick_pending = true
```

The producer call only updates bounded state under a short lock and returns. It never
waits for route materialization.

The PayloadTrafficManager collector later processes the accumulated facts as one
simultaneous observation, updates current availability-problems channel state, and if the
routing-relevant snapshot changed invokes the sole route-priority materializer
synchronously.

```text
ProbeExecutionAgent
        |
        +-- good news / tick
        v
PayloadTrafficManager bounded input
        |
        v
availability collector state
        |
        v
effective route priority
        |
        v
sole transactional route materializer
```

No `NO_REPLY`, logical window boundary, elapsed-window replay or EventEnvelope ordering
is required on this path. Binding matrix remains unchanged by availability.

### 12.3. PayloadTrafficManager fail-close

```text
PayloadTrafficManager
    detects unsafe/unknown local rules state
        |
        +-- locally restricts payload domain
        |
        +-- PayloadTrafficStateInfo
                rules_state.service = ISOLATED
                    |
                    v
            RuntimeStateManager
                    |
                    +-- ProfileStateInfo
                    +-- other changed outputs
```

Recovery является тем же обычным control loop, если отдельная policy не требует другого.

## 13. Correlation

Availability collector correctness does not depend on causal reconstruction. Good-news
multiplicity and a pending tick are bounded aggregate facts, and collector ->
route-materializer execution is synchronous inside PayloadTrafficManager.

General Event correlation remains diagnostic-only for the asynchronous runtime streams
that still use Events.

## 14. Что не является верхнеуровневым event contract

В верхний runtime contract не входят:

- route/RPDB command sequences;
- nft command sequences;
- sysctl invocation;
- transaction phases;
- retry counters;
- probe socket mechanics;
- relay worker internals;
- Executor/Driver/Runner APIs;
- Adapter internal topology;
- metric allocator implementation.

Если RuntimeStateManager начинает требовать эти детали, следует проверить границу
соответствующего Manager.

## 15. Runtime graph

```text
InterfaceObservationAgent
        |
        v
RuntimeStateManager
        |
        +-- AvailabilityProbeSetRequest --> AvailabilityProbeManager
        |                                      |
        |                               ProbeExecutionPlan
        |                                      |
        |                                      v
        |                              ProbeExecutionAgent
        |                                      |
        |                              good news / tick
        |                                      |
        +-- PayloadTrafficStateRequest          v
                |                     PayloadTrafficManager
                |                     bounded collector input
                +--------------------------->   |
                                                v
                                      synchronous route
                                        materializer
                                                |
                                      PayloadTrafficStateInfo
                                                |
                                                v
                                      RuntimeStateManager
```

The good-news/tick edge is an aggregate producer input, not a replayable Event journal.
The collector/materializer edge is synchronous Machinery flow inside PayloadTrafficManager.

## 16. Следующая декомпозиция

Архитектурно зафиксированы:

- physical ProbeRules/readiness ownership в AvailabilityProbeManager;
- bounded physical sends and stale-generation rejection in ProbeExecutionAgent;
- bounded colorless good-news counter + boolean tick input;
- availability-problems collector policy inside PayloadTrafficManager;
- synchronous use of the sole route-priority materializer;
- no EventEnvelope requirement on the availability collector/materializer path.

Current code still implements the superseded logical-window/evidence-epoch model. The next
coherent implementation unit is its replacement by this bounded aggregate collector.
