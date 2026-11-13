# VPN-GATE NG2 — событийная модель runtime

**Статус:** нормативный проект NG2  
**Дата:** 2026-11-13  
**Область:** steady-state runtime после успешного startup и до начала shutdown  
**Общая компонентная модель:** `design/component-model.md`

Документ описывает событийные контракты верхнего уровня VPN-GATE NG2 до границ
Managers. Внутренняя декомпозиция Managers, конкретные Adapters и способы реализации их
локальных control loops намеренно не рассматриваются: это следующий архитектурный шаг.

Bootstrap, startup и shutdown также находятся вне текущего scope. Предполагается, что
runtime уже получил готовую нормализованную конфигурацию и все участники, необходимые для
steady-state работы, запущены.

## 1. Цель runtime

Runtime должен непрерывно поддерживать соответствие между:

- нормализованной внешней конфигурацией;
- текущими наблюдениями внешней среды;
- текущими состояниями управляемых Managers;
- встроенными policy/invariants VPN-GATE;
- желаемым состоянием управляемых предметных областей.

Runtime не строится вокруг процедурного общего reconciliation pass. Его основной механизм
— обмен Events через Event Delivery Environment.

Общая петля:

```text
InfoEvents from observed/managed domains
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
        +--> RequestEvents --> Managers / Agents
        |
        +--> InfoEvents ----> status/diagnostic subscribers
                                |
                                v
                  environment changes / observations
                                |
                                +---- InfoEvents ----+
                                                   |
                                                   v
                                         RuntimeStateManager
```

## 2. Участники верхнего уровня

### 2.1. RuntimeStateManager

`RuntimeStateManager` — верхнеуровневый Manager состояния runtime-стакана.

Его управляемая предметная среда — совокупность остальных runtime domains, представленная
через их опубликованные состояния.

Он:

1. подписывается на системно значимые InfoEvents Agents и Managers;
2. хранит latest known projection каждого необходимого источника;
3. собирает из них `CurrentRuntimeSnapshot`;
4. прогоняет snapshot через Calculators;
5. публикует RequestEvents только при изменении соответствующего desired projection;
6. публикует системные InfoEvents, например вычисленное состояние Profiles;
7. не управляет низкоуровневыми ресурсами непосредственно;
8. не знает внутренние retry/state-machine/Adapter механизмы нижних Managers.

Накопление latest known projections является технологическим способом построения текущего
snapshot и не является историческим журналом.

### 2.2. InterfaceObservationAgent

`InterfaceObservationAgent` представляет runtime текущую сетевую interface environment.

Он наблюдает интерфейсы и публикует актуальную проекцию их состояния. Источником wakeup
может быть netlink, audit timer или другой механизм, но содержание event должно описывать
актуальное наблюдение, а не доверять сырому wakeup как состоянию.

В исходную проекцию могут входить, как минимум:

- concrete interface identity;
- имя и ifindex;
- kernel flags;
- адресные данные, если они требуются policy;
- иные проверенные текущие свойства интерфейса.

Точная техника чтения kernel state относится к внутренней реализации Agent/Adapters.

### 2.3. ProbeAgent

`ProbeAgent` — логическая роль одного или нескольких Agents активного наблюдения
доступности.

RuntimeStateManager публикует, какие probes сейчас требуются. ProbeAgent не изменяет
проверяемую внешнюю среду, выполняет заданные наблюдения и публикует текущие результаты.

Конкретные реализации могут быть разделены по механизмам, например ICMP и TCP, но
верхнеуровневая event model от этого не меняется.

### 2.4. DeviceManager

`DeviceManager` представляет runtime управляемую область Device lifecycle/capacity.

Он принимает желаемое состояние Device domain, самостоятельно наблюдает фактическое
состояние своей среды, воздействует на нее и публикует актуальную системно значимую
проекцию.

RuntimeStateManager не должен знать, какие процессы, unit'ы, конфигурационные файлы,
retries или transport-specific операции используются DeviceManager.

### 2.5. TrafficManager

`TrafficManager` представляет runtime всю управляемую traffic domain.

Он получает семантическое желаемое traffic state, а внутри своей границы сам отвечает за
необходимые network resources, безопасные переходы, verification, fail-closed behavior и
локальную convergence policy.

RuntimeStateManager не должен оперировать route/rule/firewall/NAT operations как
управляющими действиями. В event contract передается требуемая семантика traffic domain,
а не последовательность низкоуровневых команд.

### 2.6. PublicationManager

`PublicationManager` представляет runtime управляемую область transport publication.

Он получает желаемую publication projection и публикует фактическое состояние этой
области. Socket workers, relay implementation и прочая механика скрыты внутри Manager.

## 3. Event Delivery Environment

Все перечисленные участники связаны через общую абстрактную Event Delivery Environment.

Она обеспечивает:

```text
publish(Event)

subscribe(EventType, optional scope, Subscriber)

publication
    -> delivery to every matching active subscriber
```

Среда доставки:

- не интерпретирует domain semantics;
- не вычисляет desired state;
- не выполняет policy;
- не является source of truth;
- не обязана хранить event history между запусками daemon.

Runtime correctness не должен зависеть от exactly-once semantics. Subscribers должны
переносить повторную доставку одной и той же актуальной проекции.

Для защиты от stale/out-of-order state publications каждый stateful event stream имеет
логическую revision.

## 4. Общий event envelope

Каждый Event верхнего уровня должен иметь метаданные, достаточные для маршрутизации,
дедупликации и диагностики.

Концептуально:

```text
EventEnvelope
    kind            INFO | REQUEST
    type            stable event type
    publisher       stable participant identity
    subject         domain-specific scope/key
    runtime_epoch   identity of this daemon/runtime generation
    revision        monotonic revision within publisher+type+subject+epoch
    event_id        unique diagnostic identifier
    caused_by       optional event_id/request identifier
    published_at    diagnostic timestamp
    payload         event-specific data
```

Нормативные свойства:

1. `runtime_epoch` не связывает независимые daemon runs; новый запуск является новой
   runtime generation.
2. `revision` используется для определения последней публикации одной проекции, а не как
   исторический номер domain state.
3. Subscriber игнорирует publication с revision старше уже принятой для того же stream.
4. `caused_by` является optional diagnostic/correlation metadata и не заменяет наблюдение
   фактической среды.
5. `published_at` не используется как единственный механизм ordering.

Конкретная serialized representation будет определена при проектировании реализации.

## 5. Семантика RequestEvent

RequestEvent в NG2 означает актуальное управляющее намерение, а не одноразовую procedure
call.

Для одного request subject:

```text
revision 10: desired = A
revision 11: desired = B
```

означает, что B заменяет A.

Manager, принявший актуальный RequestEvent:

- сохраняет его как текущий управляющий input своей области;
- пытается поддерживать/достигать соответствующее состояние согласно локальной policy;
- не требует повторного request для каждого retry;
- прекращает следовать старому request после принятия более новой revision;
- публикует актуальное состояние области как InfoEvent.

RequestEvent не требует непосредственного response event.

InfoEvent Manager может содержать `caused_by` или accepted request revision для
диагностики, но системная корректность должна определяться текущей наблюдаемой проекцией
Manager, а не фактом получения "успешного ответа" на request.

## 6. Семантика InfoEvent

InfoEvent верхнего уровня сообщает текущую системно значимую проекцию publisher'а.

Для state projections предпочтительна семантика:

```text
newer publication supersedes older publication of same subject
```

RuntimeStateManager хранит только актуальную публикацию, необходимую для текущего snapshot.

Failure конкретной низкоуровневой операции не обязан становиться отдельным системным event,
если наружу можно опубликовать более содержательное текущее состояние предметной области.

Например, предпочтительно:

```text
DeviceStateInfo:
    requested capacity = 5
    actual capacity    = 4
    effective limit    = 4
    state              = LIMITED
    reason             = ...
```

вместо того, чтобы верхний уровень строил policy вокруг последовательности
`StartFailed`, `RetryFailed`, `RetrySucceeded`.

## 7. Нормативный каталог событий

Имена являются NG2 architectural names. Поля payload могут уточняться при проектировании
Managers, но семантика event types фиксируется этим документом.

### 7.1. InterfaceInventoryInfo

**Kind:** InfoEvent  
**Publisher:** InterfaceObservationAgent  
**Subscribers:** RuntimeStateManager  
**Subject:** runtime interface inventory  
**Publication mode:** full snapshot

Содержит актуальный набор релевантных runtime interfaces и свойства, необходимые
Calculators.

Нормативная identity concrete interface:

```text
(ifname, ifindex)
```

Same-name/new-ifindex является новой concrete interface identity.

`InterfaceInventoryInfo` не содержит понятия Profile binding или admission: это
наблюдение внешней среды.

### 7.2. ProbeSetRequest

**Kind:** RequestEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** ProbeAgent implementations  
**Subject:** runtime probe set  
**Publication mode:** full desired snapshot

Определяет полный набор probes, которые runtime сейчас требует поддерживать.

Каждый probe имеет stable `probe_id` в пределах runtime epoch и содержит достаточное
описание observation task, например:

```text
probe_id
mechanism
concrete interface identity
target
mechanism-specific parameters
semantic owner/scope
```

ProbeAgent не обязан понимать Profile policy; `semantic owner/scope` может оставаться
opaque correlation data.

Новая revision полного ProbeSetRequest заменяет предыдущий desired probe set.

### 7.3. ProbeStateInfo

**Kind:** InfoEvent  
**Publisher:** ProbeAgent  
**Subscribers:** RuntimeStateManager  
**Subject:** `probe_id`  
**Publication mode:** current state per probe

Публикует актуальный результат probe:

```text
probe_id
state
reason/details where useful
observation generation
```

Полный enum probe state определяется контрактом probe mechanism. Runtime policy не должна
делать вывод из отсутствия publication там, где требуется явное UNKNOWN/UNAVAILABLE
состояние.

### 7.4. DeviceStateRequest

**Kind:** RequestEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** DeviceManager  
**Subject:** managed Device domain  
**Publication mode:** desired state snapshot

Описывает требуемое состояние Device domain в предметных терминах.

В первоначальной NG2 модели ключевая часть — desired capacity по configured Device /
ExpectedInterface scope. Концептуально:

```text
device
expected-interface scope
desired capacity
relevant normalized Device configuration generation
```

Request не должен содержать команды вида `start process X` или `restart unit Y`.

### 7.5. DeviceStateInfo

**Kind:** InfoEvent  
**Publisher:** DeviceManager  
**Subscribers:** RuntimeStateManager  
**Subject:** managed Device domain or Device scope  
**Publication mode:** current state snapshot

Содержит системно значимую текущую проекцию Device domain, достаточную верхнему уровню для
следующего policy calculation.

Она может включать:

```text
current managed capacity
effective current limit if known
current availability/readiness of managed capacity
reason/constraint information
accepted request revision for diagnostics
```

Точный contract будет уточнен при декомпозиции DeviceManager.

Критическое правило: RuntimeStateManager не должен выводить фактическое появление network
interface только из успешного DeviceManager action. Concrete interfaces подтверждаются
`InterfaceInventoryInfo`.

### 7.6. TrafficStateRequest

**Kind:** RequestEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** TrafficManager  
**Subject:** complete managed traffic domain  
**Publication mode:** full desired snapshot

Передает семантическое желаемое traffic state целиком, чтобы TrafficManager мог обеспечить
согласованный переход между поколениями политики.

Request содержит данные уровня:

```text
Profiles participating in traffic
current selected/bound concrete interfaces per Profile
Profile direction/destination requirements
Device traffic-policy references needed by TrafficManager
other semantic traffic requirements
```

Он **не** содержит:

```text
route add/del commands
RPDB command sequence
nft command sequence
metric renumbering operations
sysctl command sequence
```

Эти детали принадлежат TrafficManager.

Стабильные technical metrics, transition barriers, fail-closed ordering и verification
также являются внутренней ответственностью TrafficManager и не входят в верхний event
contract.

### 7.7. TrafficStateInfo

**Kind:** InfoEvent  
**Publisher:** TrafficManager  
**Subscribers:** RuntimeStateManager; diagnostic/status subscribers  
**Subject:** managed traffic domain  
**Publication mode:** current state snapshot

Публикует текущее системно значимое состояние traffic domain.

Минимально различимы состояния, позволяющие верхнему policy layer понять, соответствует ли
traffic domain актуальному request и безопасна ли она.

Например:

```text
READY
CONVERGING
ISOLATED
LIMITED/DEGRADED   # если такое состояние будет реально необходимо
```

Полный enum фиксируется при проектировании TrafficManager.

Если TrafficManager обнаруживает состояние, безопасность которого не может доказать, его
локальная policy имеет право немедленно сделать managed domain более ограниченной
(fail closed) и затем опубликовать фактическое состояние. Для этого не требуется отдельный
верхнеуровневый failure workflow.

Пока актуальный TrafficStateRequest не заменен, TrafficManager сам отвечает за локальную
convergence/recovery policy своей области.

### 7.8. PublicationStateRequest

**Kind:** RequestEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** PublicationManager  
**Subject:** managed publication domain  
**Publication mode:** full desired snapshot

Определяет полный желаемый набор publication endpoints в предметных терминах.

### 7.9. PublicationStateInfo

**Kind:** InfoEvent  
**Publisher:** PublicationManager  
**Subscribers:** RuntimeStateManager; diagnostic/status subscribers  
**Subject:** managed publication domain  
**Publication mode:** current state snapshot

Публикует фактическое системно значимое состояние publication domain.

Низкоуровневые socket/session/worker details не должны выходить на верхний уровень, кроме
случаев, где они действительно являются частью системной policy.

### 7.10. ProfileStateInfo

**Kind:** InfoEvent  
**Publisher:** RuntimeStateManager  
**Subscribers:** status/log/UI/diagnostic subscribers  
**Subject:** Profile  
**Publication mode:** current state per Profile

Публикует вычисленное текущее состояние Profile после применения runtime policy к
CurrentRuntimeSnapshot.

Например, архитектурно уже различимы ситуации:

```text
SATISFIED
MINOR_DEGRADED   # основной service path есть, требуемый reserve не полностью выполнен
```

Полный Profile state enum и severity policy должны быть отдельно зафиксированы в NG2
policy model; этот документ не изобретает остальные состояния заранее.

## 8. CurrentRuntimeSnapshot

RuntimeStateManager поддерживает materialized current view.

Концептуально:

```text
CurrentRuntimeSnapshot
    normalized_config

    interface_inventory
    probe_states

    device_state
    traffic_state
    publication_state

    derived/current policy projections required for recalculation
```

Snapshot содержит только latest accepted projections текущего runtime epoch.

Для каждого source projection состояние до первой корректной публикации является
`UNKNOWN`, а не пустым множеством.

`UNKNOWN` нельзя молча интерпретировать как:

- отсутствие interfaces;
- probe failure;
- нулевую Device capacity;
- successful empty traffic state.

Политика работы с UNKNOWN должна быть fail-closed там, где неопределенность может расширить
traffic exposure.

## 9. Calculators внутри RuntimeStateManager

Calculators не являются участниками Event Delivery Environment.

На текущем уровне NG2 ожидаются как минимум следующие логические вычисления.

### 9.1. InterfaceSelectionCalculator

Вход:

- normalized Device configuration;
- current interface inventory;
- текущие системно наблюдаемые сведения, необходимые для survivor preservation;
- quotas/selectors.

Выход:

- текущий selected/admitted set interfaces по Device/ExpectedInterface.

Persisted candidate history между daemon runs не используется. Независимые запуски daemon
не наследуют admission history предыдущего запуска.

### 9.2. BindingCalculator

Вход:

- selected interfaces;
- Profiles;
- current condition state.

Выход:

```text
IsBound(concrete_interface, Profile) -> bool
```

Базовое условие — применимость selected interface к Profile через configured Device
relation.

При отсутствии дополнительных `interface_balancing` conditions подходящий selected
interface считается bound.

Дополнительные conditions образуют AND.

Условие `online` вычисляется из текущих interface properties/flags. Active probes
используют `ProbeStateInfo`.

Binding matrix является derived projection и не является отдельной event-driven subsystem.

### 9.3. ProbeDemandCalculator

Вход:

- config;
- selected interfaces;
- Profile balancing requirements.

Выход:

- полный desired probe set для `ProbeSetRequest`.

### 9.4. DeviceCapacityCalculator

Вход:

- Profile reserve requirements;
- binding matrix;
- current DeviceStateInfo;
- sharing of Devices between Profiles;
- normalized Device configuration.

Выход:

- desired Device domain state для `DeviceStateRequest`.

Calculator обязан агрегировать требования всех Profiles, использующих общие Devices.

Один Profile не может заставить удалить capacity, которая все еще требуется другому
Profile.

### 9.5. TrafficIntentCalculator

Вход:

- config;
- binding matrix;
- current semantic runtime facts.

Выход:

- полный semantic desired traffic projection для `TrafficStateRequest`.

Низкоуровневое kernel/network materialization не является частью Calculator.

### 9.6. PublicationIntentCalculator

Вход:

- normalized configuration;
- runtime facts, если они влияют на publication policy.

Выход:

- полный desired publication projection.

Если publication policy в конкретной версии полностью статична, Calculator вырождается в
простую projection конфигурации.

### 9.7. ProfileStateCalculator

Вход:

- Profile requirements;
- binding matrix;
- current Device state;
- current Traffic state;
- иные system-level facts, реально влияющие на fulfillment.

Выход:

- текущее Profile status и диагностические причины.

## 10. Recalculation и publication policy RuntimeStateManager

При принятии нового InfoEvent RuntimeStateManager:

```text
1. validates epoch/revision/subject
2. replaces corresponding latest projection
3. rebuilds affected CurrentRuntimeSnapshot view
4. runs affected Calculators
5. compares derived outputs with last published outputs
6. publishes only semantically changed RequestEvents/InfoEvents
7. updates diagnostic/log cache
```

Полный пересчет всех Calculators допустим как реализация, если он достаточно дешев.
Dependency-based partial recalculation является оптимизацией и не меняет semantics.

Повторный одинаковый input не должен создавать бесконечный event storm.

RuntimeStateManager может хранить last-published outputs для deduplication. Это
технологический cache, а не исторический source of truth.

## 11. Основные feedback loops

### 11.1. Появление интерфейса

```text
external interface change
        |
        v
InterfaceObservationAgent
        |
        +-- InterfaceInventoryInfo -->
                RuntimeStateManager
                    |
                    +-- interface selection
                    +-- binding
                    +-- probe demand
                    +-- device capacity
                    +-- traffic intent
                    |
                    +-- ProbeSetRequest ------> ProbeAgent
                    +-- DeviceStateRequest ---> DeviceManager
                    +-- TrafficStateRequest --> TrafficManager
```

Публикуются только реально изменившиеся outputs.

### 11.2. Probe failure для одного Profile path

```text
ProbeAgent
   |
   +-- ProbeStateInfo(UNREACHABLE)
            |
            v
    RuntimeStateManager
            |
         binding matrix changes
            |
            +-- TrafficStateRequest
            +-- maybe DeviceStateRequest
            +-- ProfileStateInfo
```

Один concrete interface может остаться bound в другом Profile, если условия того Profile
выполнены.

### 11.3. Device capacity меньше требуемой

```text
RuntimeStateManager
    |
    +-- DeviceStateRequest(desired capacity = 5)
            |
            v
       DeviceManager
            |
        managed environment settles at 4
            |
            +-- DeviceStateInfo(actual=4, effective_limit=4)
                        |
                        v
                RuntimeStateManager
                        |
                    recalculate
                        |
                        +-- Profile A = SATISFIED
                        +-- Profile B = MINOR_DEGRADED
```

RuntimeStateManager не обязан получать отдельный `StartFailed` response. Системно
значимым фактом является наблюдаемое состояние Device domain.

Если desired DeviceStateRequest остается тем же, RuntimeStateManager не спамит Manager
одинаковыми requests. Дальнейшая локальная реакция на изменения Device environment
принадлежит DeviceManager.

### 11.4. TrafficManager fail-closed

```text
TrafficManager detects unsafe/unknown local state
        |
        +-- locally moves managed domain to safe restriction
        |
        +-- TrafficStateInfo(ISOLATED)
                    |
                    v
            RuntimeStateManager
                    |
                recalculate Profile/system state
                    |
                publish changed outputs
```

Отдельные Guard/Recovery components не требуются, пока recovery является применением
обычной policy к новой текущей реальности.

TrafficManager не обязан получать новый TrafficStateRequest для каждого retry: текущий
request остается его управляющим input до superseding revision.

## 12. Correlation и causality

Event graph может образовывать длинные feedback chains.

Например:

```text
DeviceStateRequest R17
    -> DeviceManager
    -> external changes
    -> InterfaceInventoryInfo I44
    -> RuntimeStateManager
    -> TrafficStateRequest R23
    -> TrafficManager
    -> TrafficStateInfo I51
    -> ProfileStateInfo I52
```

Не требуется, чтобы каждый последующий event нес прямую транзитивную ссылку на R17.

`caused_by` используется там, где correlation действительно помогает диагностике или
локальному contract.

Корректность верхнего уровня определяется CurrentRuntimeSnapshot, а не восстановлением
полного causal history.

## 13. Что не является event contract верхнего уровня

Следующие детали намеренно не должны протекать в этот документ:

- systemd unit start/stop operations;
- process identifiers;
- concrete socket worker lifecycle;
- route/RPDB command sequences;
- nft rule command sequences;
- sysctl invocation;
- metric allocator mechanics;
- probe socket mechanics;
- retry counters;
- hysteresis implementation;
- local Manager transaction phases;
- Adapter method names.

Если такая деталь потребуется RuntimeStateManager для принятия policy decision, сначала
следует проверить, не протекла ли внутренняя ответственность Manager через его границу.

## 14. Event dependency graph

Верхнеуровневый steady-state graph:

```text
                         +----------------------+
                         | InterfaceObservation |
                         |        Agent         |
                         +----------+-----------+
                                    |
                         InterfaceInventoryInfo
                                    |
                                    v
+-------------+  ProbeStateInfo  +---------------------+
| ProbeAgent  +----------------->| RuntimeStateManager |
+------+------+                  +----+-----+-----+----+
       ^                              |     |     |
       | ProbeSetRequest              |     |     |
       +------------------------------+     |     |
                                            |     |
                              DeviceStateRequest   |
                                            |     |
                                            v     |
                                     +------+-----+--+
                                     | DeviceManager |
                                     +------+--------+
                                            |
                                     DeviceStateInfo
                                            |
                                            +-----------> RuntimeStateManager

                              TrafficStateRequest
                                      |
                                      v
                               +------+-------+
                               | TrafficManager|
                               +------+-------+
                                      |
                               TrafficStateInfo
                                      |
                                      +-----------> RuntimeStateManager

                           PublicationStateRequest
                                      |
                                      v
                             +--------+----------+
                             | PublicationManager|
                             +--------+----------+
                                      |
                           PublicationStateInfo
                                      |
                                      +-----------> RuntimeStateManager

RuntimeStateManager
    |
    +-- ProfileStateInfo --> status/log/UI/diagnostic subscribers
```

Все циклы верхнего уровня замыкаются Events. Синхронные Adapter dependencies остаются
внутри границ Agents/Managers и будут проектироваться отдельно.

## 15. Открытые вопросы следующего шага

Этот документ намеренно оставляет следующему этапу:

1. внутреннюю декомпозицию DeviceManager;
2. внутреннюю декомпозицию TrafficManager;
3. внутреннюю декомпозицию PublicationManager;
4. конкретные Adapters каждого Manager/Agent;
5. точные state enums и reason codes Manager outputs;
6. timing/retry/hysteresis probes;
7. конкретный transport Event Delivery Environment;
8. serialization и schema-versioning Events;
9. manager restart/resubscription/state-refresh protocol;
10. исчерпывающий Profile status/severity model.

До решения этих вопросов верхнеуровневый event contract должен оставаться стабильным:
верхний runtime оперирует только предметными Events и не зависит от внутренней механики
Managers.
