# VPN-GATE NG2 — событийная модель runtime

**Статус:** нормативный проект NG2  
**Дата:** 2026-11-13  
**Область:** steady-state runtime после успешного startup и до начала shutdown  
**Общая компонентная модель:** `design/component-model.md`

Документ описывает события и Engines верхнего уровня VPN-GATE NG2. Внутренняя
декомпозиция Managers и их Machinery рассматривается отдельными документами.

Bootstrap/startup/shutdown пока находятся вне scope.

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

`AvailabilityProbeManager` управляет подсистемой активных availability probes.

Он не управляет доступностью удаленного endpoint. Его managed domain — собственная probe
subsystem:

- набор активных probe tasks;
- необходимая probe-specific network environment;
- lifecycle и исполнение probes;
- получение фактических probe results.

Manager получает желаемый набор probes как RequestEvent и публикует текущие результаты как
InfoEvents.

Итоговая семантика:

```text
(Profile, concrete interface) -> ON/OFF
```

ему не принадлежит. Probe result является только одним из входов `BindingCalculator`.

### 2.4. PayloadTrafficManager

`PayloadTrafficManager` управляет payload network policy VPN-GATE.

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

### 2.5. PublicationManager

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

Определяет полный набор probes, которые runtime сейчас требует поддерживать.

Концептуальный probe:

```text
probe_id
mechanism
concrete interface identity
target
mechanism-specific parameters
semantic scope/correlation
```

Новая revision заменяет предыдущий desired set.

### 8.3. AvailabilityProbeStateInfo

**Kind:** InfoEvent  
**Publisher:** AvailabilityProbeManager  
**Subscribers:** RuntimeStateManager  
**Subject:** probe_id  
**Publication mode:** current state per probe

Содержит текущий probe result:

```text
probe_id
state
reason/details
observation generation
```

Отсутствие publication не должно автоматически означать failure. До подтвержденного
наблюдения состояние трактуется как UNKNOWN.

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

### 8.5. PayloadTrafficStateInfo

**Kind:** InfoEvent  
**Publisher:** PayloadTrafficManager  
**Subscribers:** RuntimeStateManager; diagnostics/status  
**Subject:** payload traffic domain  
**Publication mode:** current state snapshot

Публикует системно значимое состояние payload traffic domain.

Минимально требуются состояния, позволяющие понять:

- соответствует ли domain текущему request;
- доказана ли безопасная payload policy;
- находится ли domain в защитно ограниченном состоянии.

Рабочие названия:

```text
READY
CONVERGING
ISOLATED
UNKNOWN/FAILED    # точный enum будет зафиксирован в decomposition document
```

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
- current condition state.

Выход:

```text
IsBound(concrete_interface, Profile) -> bool
```

Без дополнительных `interface_balancing` conditions применимый selected interface
считается usable для Profile.

Дополнительные conditions образуют AND.

Active availability evidence поступает через `AvailabilityProbeStateInfo`.

### 10.3. AvailabilityProbeDemandCalculator

Вход:

- config;
- selected interfaces;
- Profile balancing requirements.

Выход:

- полный desired set для `AvailabilityProbeSetRequest`.

### 10.4. PayloadTrafficIntentCalculator

Вход:

- config;
- binding matrix;
- текущие системно значимые runtime facts.

Выход:

- semantic desired payload projection для `PayloadTrafficStateRequest`.

Linux/kernel materialization в Calculator не входит.

### 10.5. PublicationIntentCalculator

Вход:

- normalized configuration;
- runtime facts, реально влияющие на publication policy.

Выход:

- desired publication projection.

### 10.6. ProfileStateCalculator

Вход:

- Profile requirements;
- binding matrix;
- current payload traffic state;
- current publication state, если она влияет на конкретный Profile contract;
- другие реальные system-level facts.

Выход:

- текущее Profile state и diagnostic reasons.

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

### 12.2. Availability probe failure

```text
AvailabilityProbeManager
    |
    +-- AvailabilityProbeStateInfo(UNREACHABLE)
            |
            v
    RuntimeStateManager
            |
         BindingCalculator
            |
       binding matrix changes
            |
            +-- PayloadTrafficStateRequest
            +-- ProfileStateInfo
```

Один concrete interface может остаться usable для другого Profile.

### 12.3. PayloadTrafficManager fail-close

```text
PayloadTrafficManager
    detects unsafe/unknown local rules state
        |
        +-- locally restricts payload domain
        |
        +-- PayloadTrafficStateInfo(ISOLATED)
                    |
                    v
            RuntimeStateManager
                    |
                    +-- ProfileStateInfo
                    +-- other changed outputs
```

Recovery является тем же обычным control loop, если отдельная policy не требует другого.

## 13. Correlation

Пример causal chain:

```text
AvailabilityProbeStateInfo
    -> RuntimeStateManager
    -> PayloadTrafficStateRequest R23
    -> PayloadTrafficManager
    -> lower Machinery
    -> observed payload rules/state changes
    -> PayloadTrafficStateInfo I51
    -> RuntimeStateManager
    -> ProfileStateInfo I52
```

Не требуется переносить транзитивный correlation identifier через всю цепочку.

Корректность определяется текущими projections, а не восстановлением causal history.

## 14. Что не является верхнеуровневым event contract

В верхний runtime contract не входят:

- route/RPDB command sequences;
- nft command sequences;
- sysctl invocation;
- transaction phases;
- retry counters;
- probe socket mechanics;
- relay worker internals;
- Driver APIs;
- Adapter internal topology;
- metric allocator implementation.

Если RuntimeStateManager начинает требовать эти детали, следует проверить границу
соответствующего Manager.

## 15. Event graph

```text
+---------------------------+
| InterfaceObservationAgent |
+-------------+-------------+
              |
     InterfaceInventoryInfo
              |
              v
      +---------------------+
      | RuntimeStateManager |
      +---+-------------+---+
          |             |
          |             +--------------------+
          |                                  |
AvailabilityProbeSetRequest       PayloadTrafficStateRequest
          |                                  |
          v                                  v
+-------------------------+       +------------------------+
| AvailabilityProbeManager|       | PayloadTrafficManager  |
+------------+------------+       +-----------+------------+
             |                                |
AvailabilityProbeStateInfo         PayloadTrafficStateInfo
             |                                |
             +--------------->+<---------------+
                              |
                    RuntimeStateManager

RuntimeStateManager
        |
        +-- PublicationStateRequest --> PublicationManager
        |                               |
        |                        PublicationStateInfo
        |                               |
        +<------------------------------+
        |
        +-- ProfileStateInfo --> status/log/UI
```

Все feedback cycles верхнего уровня замыкаются Events.

## 16. Следующая декомпозиция

Отдельно проектируются:

1. PayloadTrafficManager и его Machinery;
2. AvailabilityProbeManager и его Machinery;
3. PublicationManager и его Machinery;
4. точные state enums/reason codes;
5. Event Delivery Environment implementation;
6. serialization/schema versioning;
7. restart/resubscription/state-refresh protocol;
8. Profile status model.

Future Device lifecycle management остается отдельным будущим расширением и не является
частью текущего NG2 runtime.
