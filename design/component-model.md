# Компонентно-событийная модель

**Статус:** нормативный переносимый проектный документ  
**Область:** проектирование, декомпозиция и ревью событийных управляющих систем  
**Привязка к VPN-GATE:** отсутствует; конкретные архитектуры проекта могут ссылаться на этот документ

Документ задает общий словарь компонентов и правил взаимодействия. Он намеренно не
привязан к конкретному продукту, протоколу, операционной системе или реализации доставки
сообщений.

## 1. Два семейства компонентов

Все рассматриваемые компоненты относятся к одному из двух семейств:

```text
Components
├── Engines
│   ├── Manager
│   └── Agent
│
└── Machinery
    ├── semantic roles
    │   ├── Calculator
    │   ├── Adapter
    │   ├── Executor
    │   └── Driver
    │
    └── execution primitives
        └── Runner
```

Разделение задается способом участия компонента в архитектуре, а не сложностью его
внутренней реализации.

### 1.1. Engines

**Engine** — активный участник асинхронного событийного пространства.

Engine:

- подписывается на Events;
- может публиковать Events;
- существует между отдельными обработками событий;
- может иметь семантически значимое текущее состояние;
- не обязан завершать предметную реакцию внутри чужого call stack.

В этой модели Engine является семейством, а не синонимом stateful algorithm.

### 1.2. Machinery

**Machinery** — компонент, который вызывается из чужого execution flow и сам не является
участником event graph.

Machinery может быть внутренне сколь угодно сложной и stateful, но для вызывающей
предметной области рассматривается как **externally stateless**:

> корректность caller не должна зависеть от скрытой истории его предыдущих обращений к
> Machinery.

Если предыдущий результат необходим для следующего вызова, соответствующие данные должны
быть явно представлены в контракте.

Внутри Machinery допустимы cache, connection pool, state machines, transactions, retries,
persistent storage и даже самостоятельная нижележащая система. Все это остается
внутренним делом скрытой области, пока не входит в явный контракт.

## 2. Events

### 2.1. Event

**Event** — асинхронно распространяемое сообщение между Engines.

Event не является синхронным вызовом и не создает обязательного response channel.
Publisher не вызывает subscriber напрямую и не должен зависеть от return value его
обработчика.

Event имеет одну из двух семантик:

- **InfoEvent**;
- **RequestEvent**.

### 2.2. InfoEvent

**InfoEvent** означает:

> Я сообщаю, что наблюдаемая мной реальность или мой текущий результат имеет такое
> значение. Мне не требуется знать, кто и как на это отреагирует.

InfoEvent не предполагает обязательного ответа.

Публикация может быть snapshot, delta или очередным observation stream item. Конкретная
форма является частью контракта event type.

### 2.3. RequestEvent

**RequestEvent** означает:

> Я публикую управляющее намерение и ожидаю, что реакция заинтересованных участников
> приведет к изменению внешней среды.

RequestEvent не является RPC и не требует непосредственного response.

Subscriber может:

- изменить свою управляемую среду;
- инициировать другие RequestEvent;
- опубликовать связанные InfoEvent;
- не публиковать непосредственного ответа вообще.

Publisher может определить успех по последующему наблюдаемому изменению своей
подответственной среды, даже если ни один прямой response на исходный RequestEvent ему не
пришел.

Correlation/request identifiers допустимы для диагностики и контрактов, которым они нужны,
но не должны заменять наблюдение фактической среды там, где именно она является source of
truth.

### 2.4. Publisher и Subscriber

Publisher и Subscriber — capabilities Engines, а не отдельные типы компонентов.

- **Publisher** публикует Events.
- **Subscriber** объявляет интерес к event types/scopes и получает соответствующие
  публикации.

## 3. Event Delivery Environment

**Event Delivery Environment** — абстрактная среда доставки Events от publishers
заинтересованным subscribers.

Она:

- маршрутизирует события;
- не знает domain policy;
- не владеет предметным состоянием;
- не интерпретирует RequestEvent как RPC;
- не решает, что subscriber должен сделать с сообщением.

Реализация может быть callback dispatcher, queue, broker, socket, process-local bus или
другой механизм.

Если event edge используется для разрыва синхронного dependency cycle, граница должна быть
фактически асинхронной: publication не должна зависеть от завершения subscriber handler.

## 4. Manager

**Manager** — Engine, представляющий управляемую предметную среду.

Manager:

1. получает Events;
2. наблюдает свою подответственную среду;
3. воздействует на нее согласно своей локальной policy;
4. публикует системно значимую текущую проекцию этой среды;
5. скрывает внутреннюю механику управления.

```text
Events
  |
  v
+---------+
| Manager |
+---------+
  |
  +--> Machinery
  |
  v
managed domain
  |
  v
InfoEvents
```

Внутри Manager допустимы retries, hysteresis, state machines, optimizers, transactions,
control loops и иная логика любой сложности.

Manager не обязан публиковать отдельный response на каждый RequestEvent. Он может
наблюдать изменение собственной среды, в том числе вызванное реакцией других участников,
и публиковать только итоговую актуальную проекцию.

## 5. Agent

**Agent** — Engine, представляющий наблюдаемую, но не управляемую им предметную среду.

Agent:

1. получает Events или внешние triggers;
2. наблюдает свою предметную среду;
3. при необходимости использует Machinery;
4. публикует результаты наблюдения как Events;
5. не оказывает управляющего воздействия на ту же предметную среду.

Кратко:

```text
Agent   = observe
Manager = observe + actuate
```

Agent может иметь timers, retries, debounce, hysteresis и другую внутреннюю stateful
логику. Это не делает его Manager, пока он не управляет представляемой им средой.

## 6. Machinery: Direct и Indirect

Direct/Indirect — характеристика completion semantics Machinery.

**Machinery is expected to be Direct by default.** Обычный контракт должен быть
сформулирован так, чтобы синхронный return являлся завершенным результатом именно той
операции, которую caller запросил.

Например внешний асинхронный механизм не делает Adapter автоматически Indirect:

```text
submit(job) -> submitted / not submitted
```

остается Direct-вызовом, если контракт метода — именно постановка задания.

### 6.1. Direct Machinery

Для **Direct Machinery** синхронный return является завершенным результатом заявленной
операции:

```text
input
  |
  v
Direct Machinery
  |
  v
result
```

Caller вправе использовать returned value как результат данного обращения.

Немаркированные Calculator, Adapter, Executor и Driver предполагают Direct semantics. Runner обычно является Direct execution primitive.

### 6.2. Indirect Machinery

**Indirect** — исключительная и явно маркируемая semantics, а также design-review warning.
Она используется, когда вызываемая операция действительно не может быть естественно
сформулирована как Direct.

Для **Indirect Machinery** синхронный вызов только инициирует, передает или ставит работу:

```text
input
  |
  v
Indirect Machinery
  |
  v
accepted / rejected / delivered / handle
```

Интересующий предметный результат появляется позже и возвращается в рассматриваемую
систему через event space.

Нормативные правила:

> return Indirect Machinery не является доказательством результата инициированной работы.

> Если Indirect-контракт можно естественно переформулировать как Direct-операцию
> (`submit`, `enqueue`, `request` и т. п.), следует предпочесть Direct.

> Смешение Direct и Indirect completion semantics в одном Machinery-компоненте следует
> избегать; `MixedAdapter` и аналогичные конструкции требуют отдельного архитектурного
> обоснования.

Indirect не запрещен. Он может быть полезен как **transition artefact**: на текущем этапе
декомпозиции `FooIndirectCalculator` или `BarIndirectDriver` может быть понятнее, чем
раннее введение нового Adapter и скрытой за ним нижней предметной области. При этом
маркер `Indirect` намеренно сохраняет design debt видимым и требует повторного review
границы ответственности.

Особенно подозрительны `IndirectCalculator` и `IndirectDriver`.

Чаще всего они означают одно из двух:

1. скрытый командный Adapter к самостоятельной нижней системе;
2. неправильно сформулированную смысловую нагрузку метода.

Например:

```text
FinanceIndirectDriver.getThreeYearSummary()
```

может фактически означать:

```text
FinanceReportAdapter.submitThreeYearSummaryJob()
    -> submitted / not submitted
```

Второй контракт является Direct: запрошенная операция состоит именно в постановке job.
Будущий отчет принадлежит уже жизненному циклу нижней системы и возвращается через ее
наблюдение/Event path.

Аналогично `IndirectCalculator` часто оказывается Adapter к самостоятельному
вычислителю, а не Calculator в строгом смысле. Однако модель сохраняет Indirect-формы
явно, чтобы промежуточная архитектура могла быть описана честно до следующего прохода
декомпозиции.

Типичная схема:

```text
Manager
   |
   +-- sync --> Indirect Machinery
   |             |
   |             +--> lower/external domain
   |
   <----- accepted

... later ...

Agent/Manager observes resulting reality
   |
   +-- InfoEvent --> event space
```

## 7. Calculator

**Calculator** — Machinery, назначение которой состоит в вычислении производного результата
из явно заданных входных данных.

### 7.1. Direct Calculator

Обычный случай:

```text
output = f(input)
```

Direct Calculator не выполняет внешнего I/O и не требует от caller знания скрытой истории.

### 7.2. Indirect Calculator

Вычисление может выполняться во внешнем процессе, БД, solver, compute cluster или другой
нижней подсистеме:

```text
submit(input) -> accepted/handle

later:
result -> InfoEvent
```

Смысл компонента все равно остается вычислительным: он производит derived result, а не
управляет внешней предметной средой ради изменения этой среды как конечной цели.

## 8. Adapter

**Adapter** — Machinery, соединяющая две предметные области и преобразующая контракт одной
области в контракт другой.

Adapter является **границей архитектурной видимости**.

Для вызывающей области все, что находится за этой границей, является частью Adapter,
независимо от внутренней сложности нижней стороны. За Adapter могут скрываться:

- Managers и Agents;
- собственная Event Delivery Environment;
- Calculators;
- другие Adapters;
- Drivers;
- transactions;
- persistent state;
- отдельный процесс или распределенная система.

Adapter может быть Direct или Indirect.

### 8.1. Direct Adapter

Caller получает завершенный результат заявленной операции через тот же синхронный вызов.

Adapter может иметь несколько методов с различным назначением. Например stateful
реализация может явно предоставлять:

```text
apply(desired)   -> SUCCESS | FAILURE
renewState()     -> SUCCESS | FAILURE
getLastState()   -> State
```

Это не нарушает externally-stateless contract: caller зависит только от явно объявленного
state contract, а не от скрытой истории предыдущих вызовов.

### 8.2. Indirect Adapter

Синхронный return означает только успешную или неуспешную передачу управляющего намерения
через границу:

```text
caller -> Adapter -> lower domain
       <- accepted/delivered
```

Итог нижней предметной операции наблюдается независимо и возвращается через Events.

Это особенно важно для Adapter, за которым находится самостоятельная система: ответ
Adapter обычно означает «передал», а не «вот итог всей скрытой системы».

## 9. Executor

**Executor** — Machinery, принимающая заданное состояние или проверяемое постусловие и
отвечающая за его достижение.

Ключевая граница ответственности:

> Executor не выбирает, **какое** desired state нужно предметной области, но отвечает за
> то, чтобы переданное ему desired state / postcondition было достигнуто либо операция
> завершилась доказанным failure.

Типичный Direct-контракт:

```text
desired state / postcondition
    |
    v
Executor
    |
    +--> external actions
    +--> fresh observation
    +--> verification
    |
    v
SUCCESS | FAILURE
```

Executor может:

- использовать один или несколько Drivers;
- использовать Runner напрямую;
- самостоятельно выполнять driver-level external interactions, если выделение отдельного
  Driver не создает полезной переиспользуемой semantic boundary.

Наличие прямого внешнего I/O поэтому **не делает компонент Driver автоматически**.
Определяющий признак Executor — ответственность за convergence / verified postcondition.

Executor не должен выбирать предметную policy, ради которой desired state был выбран.
Эта ответственность остается у Manager или иного вышележащего caller.

Executor не обязан быть классом. Stateless cohesive convergence operation может быть
функцией или набором процедур, если отдельный object boundary не дает архитектурной
ценности.

### 9.1. Direct Executor

Обычный случай: return завершает попытку convergence и сообщает, достигнуто ли требуемое
постусловие.

### 9.2. Indirect Executor

Indirect Executor допустим только с явно описанной completion semantics. Его synchronous
return не доказывает достижение desired state; фактическое завершение должно наблюдаться
отдельно.

Такая форма требует review особенно внимательно: часто она означает, что за границей
фактически скрыта самостоятельная нижняя система и верхнему уровню нужен Adapter либо
Manager/Agent boundary.

## 10. Driver

**Driver** — Machinery, непосредственно взаимодействующая с конкретным внешним техническим
механизмом.

Примеры внешних механизмов:

- kernel/netlink;
- nftables;
- sysctl;
- systemd;
- database protocol;
- process API;
- socket API;
- filesystem.

Driver знает технический контракт механизма, но не должен знать предметную policy
вышележащего Engine.

Driver также может быть Direct или Indirect.

### 10.1. Direct Driver

Пример:

```text
read current routes -> route snapshot
write sysctl        -> immediate technical result
```

### 10.2. Indirect Driver

Пример:

```text
submit long database job -> accepted/job_id
```

Внешняя операция продолжается после return. Ее результат при необходимости наблюдается
отдельным Engine, обычно Agent, использующим соответствующий read Driver или иной
механизм наблюдения.

Наличие synchronous return у Driver никогда само по себе не доказывает, что внешняя
реальность достигла желаемого конечного состояния.


## 11. Runner

**Runner** — низкоуровневый execution / transport primitive внутри Machinery.

Runner механически передает конкретный внешний вызов и возвращает его сырой
transport/execution result. Он не имеет semantic model управляемого объекта.

Типичная форма:

```text
argv / request bytes / stdin / execution options
    |
    v
Runner
    |
    v
return code / response bytes / stdout / stderr
```

Runner не знает, означает ли вызов «добавить маршрут», «изменить sysctl», «послать probe»
или «удалить conntrack entry».

### 11.1. Runner vs Driver

Граница между Runner и Driver семантическая, а не технологическая.

**Runner**:

- транспортирует сырой invocation;
- возвращает сырой execution/transport result;
- не предоставляет осмысленной операции над управляемым объектом.

**Driver**:

- знает конкретный внешний технический механизм;
- предоставляет осмысленную техническую операцию над ним;
- может использовать Runner как реализацию transport/execution boundary;
- не владеет convergence к caller-selected desired state.

Например:

```text
run(argv) -> rc/stdout/stderr
```

— Runner.

```text
probe(request) -> REPLY | NO_REPLY | ERROR
```

— Driver, даже если внутри он запускает process через Runner.

### 11.2. Кто использует Runner

Нормальный dependency shape:

```text
Manager
    |
    v
Executor
    |
    +--> Driver --> Runner --> external mechanism
    |
    +------------> Runner --> external mechanism
```

Это не требование создавать каждый слой для каждой операции.

- Driver обычно использует Runner для конкретного внешнего взаимодействия.
- Executor может использовать Drivers и/или Runner напрямую.
- Manager обычно должен работать через semantic Machinery boundaries, а не через Runner.
  Прямая зависимость Manager -> Runner не запрещена формально, но требует отдельного
  обоснования, потому что смешивает domain lifecycle/policy с raw transport mechanics.
- Adapter может скрывать Runner внутри своей нижней реализации, но Runner не должен
  становиться частью semantic upper-domain contract только ради передачи сырого вызова.

Runner не является peer semantic-role рядом с Calculator / Adapter / Executor / Driver.
Это implementation primitive под ними.

## 12. Externally stateless Machinery

Для рассматриваемой предметной области Calculator, Adapter, Executor, Driver и Runner считаются externally
stateless независимо от их внутренней реализации.

Это означает прежде всего отсутствие зависимости от **неявной** истории вызовов:

- caller не опирается на скрытую последовательность прошлых обращений;
- скрытая нижняя система может помнить сколько угодно;
- явно экспонированный state contract (`renewState/getLastState`, token, generation,
  handle и т. п.) допустим;
- если предыдущий результат нужен следующему вызову, эта зависимость должна быть видна в
  API;
- восстановление caller после restart не должно требовать знания внутренней истории
  Machinery сверх явного контракта.

Это определение не требует физической stateless-реализации.

## 13. Current state и технологический cache Engines

Engine может хранить latest known projections:

```text
latest A
latest B
latest C
```

для построения текущего snapshot без повторного опроса всей среды.

Такой cache не является историческим domain state только потому, что живет между
обработками Events.

Полезный тест:

> если после перезапуска свежих текущих входных проекций и текущей policy достаточно для
> получения того же системно значимого результата, потерянные значения были cache, а не
> необходимой историей предметной области.

## 14. Синхронные зависимости и циклы

Внутри одной рассматриваемой предметной области строится полный граф независимых
синхронных зависимостей между видимыми компонентами.

Нормативно:

```text
synchronous dependency graph -> DAG
event graph                  -> cycles allowed
```

Допустимо:

```text
Manager A -> Manager B -> Manager C
```

Недопустимо:

```text
Manager A -> Manager B -> Manager C -> Manager A
```

Правило не зависит от конкретной формы синхронного вызова.

Цикл может быть разорван фактически асинхронной event boundary:

```text
A ->sync-> B ->sync-> C ->event-> A
```

Это допустимый причинный feedback loop.

### 14.1. Adapter boundary

Adapter завершает архитектурную видимость синхронного графа рассматриваемой области:

```text
our domain -> Adapter -> hidden lower domain
```

Внутренние синхронные циклы скрытой области являются ответственностью ее архитектуры.

Но существует обязательный boundary invariant:

> адаптированная область не должна устанавливать независимую синхронную зависимость обратно
> в нашу предметную область.

Возврат результата исходного Adapter call не является обратной зависимостью.

Запрещено:

```text
our domain
    ->sync-> Adapter B
               -> subsystem B

subsystem B
    ->sync-> anything in our domain
```

Допустимо:

```text
our domain
    ->sync-> Adapter B
               -> subsystem B

subsystem B
    ->event-> our domain
```

Если двум сторонам необходима взаимная синхронная зависимость, граница предметных областей
скорее всего проведена неверно и стороны следует рассмотреть как одну интегрированную
область.

## 15. Иерархическая композиция

Модель применяется рекурсивно.

То, что на одном уровне является целой системой:

```text
Managers
Agents
Machinery
Event Delivery Environment
```

на верхнем уровне может быть скрыто за одним Adapter.

Каждая предметная область сама отвечает за:

- свой event graph;
- свой synchronous dependency DAG;
- свои Manager/Agent boundaries;
- внутреннюю структуру Machinery;
- отсутствие synchronous back-edge через исходящие Adapter boundaries.

## 16. Review rules

### 16.1. Engine boundary

Следует проверить:

- действительно ли компонент участвует в event space;
- не протекает ли наружу его внутренняя retry/transaction кухня;
- не превращается ли InfoEvent в скрытый command;
- не маскируется ли управляющее намерение как пассивное сообщение.

### 16.2. Manager vs Agent

Если компонент изменяет ту же предметную среду, которую представляет, он Manager.

Если он только наблюдает ее, он Agent.

### 16.3. Machinery boundary

Следует проверить:

- не зависит ли caller от скрытой истории Machinery;
- является ли Direct return действительно результатом обращения;
- не принимается ли acknowledgement Indirect Machinery за конечный результат;
- нет ли скрытого synchronous back-edge через Adapter;
- не протекла ли предметная policy в Driver.

### 16.4. Adapter vs Executor vs Driver vs Runner

Adapter соединяет **предметные области**.

Executor отвечает за достижение **заданного postcondition / desired state**.

Driver соединяет внутреннюю систему с **конкретным внешним техническим механизмом** через
осмысленные технические операции, но не владеет convergence к caller-selected desired
state.

Runner передает **сырой invocation** и возвращает сырой execution/transport result.

Если компонент скрывает целую нижнюю предметную систему и представляет ее через контракт
верхней, это Adapter.

Если компонент принимает desired state и сам materialize/observe/verify его, это Executor,
даже если он напрямую вызывает Linux/netlink/nft/systemd/DB operations.

Если компонент предоставляет одну осмысленную техническую операцию над механизмом, это
Driver.

Если компонент знает только форму raw command/request и raw response, это Runner.

## 17. Краткая таблица

```text
Engine
    active event participant

Manager
    Engine: observe + control managed domain

Agent
    Engine: observe-only domain facade

Machinery
    invoked from another execution flow;
    externally stateless to caller

Direct
    requested result returns through the call

Indirect
    call initiates/transfers work;
    meaningful result returns later through event space

Calculator
    Machinery for derived computation

Adapter
    Machinery bridging two semantic/domain models;
    architectural visibility boundary

Executor
    Machinery responsible for reaching/verifying a supplied desired state or postcondition

Driver
    Machinery exposing meaningful operations over an external technical mechanism
    without owning caller-selected convergence

Runner
    low-level execution/transport primitive for raw invocations and raw results

Event Delivery Environment
    asynchronous delivery only

InfoEvent
    "this is what I know/observe"

RequestEvent
    "I expect the environment to change as a consequence"
```
