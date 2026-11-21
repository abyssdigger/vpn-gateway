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
    ├── semantic component roles
    │   ├── Calculator
    │   ├── Adapter
    │   ├── Enforcer
    │   └── Driver
    │
    └── technical operation roles
        ├── Reader
        └── Executor
```

Разделение задается способом участия компонента в архитектуре, а не сложностью его
внутренней реализации.

`Reader` и `Executor` описывают технические ответственности операции и не требуют
автоматического выделения самостоятельного компонента. Они становятся отдельной Machinery
только там, где это создает полезную архитектурную границу; в простом случае их
функциональность может оставаться методом `Driver`.

`Backend` не является дополнительным типом компонента. Это логическая композиционная
единица реализации: сформированный проектом внутренний API к внешней технической среде или
ее части, который может собирать несколько Drivers, Readers, Executors и локальных
технических преобразований. Нормативная семантика Backend определена в §11.4.

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

Немаркированные Calculator, Adapter, Enforcer и Driver предполагают Direct semantics.
Выделенные в самостоятельную Machinery Reader и Executor также предполагают Direct
semantics, если явно не указано иное.

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
- Enforcers;
- Drivers и их Reader/Executor operations;
- Backend-композиции;
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

## 9. Enforcer

**Enforcer** — Machinery, принимающая заданное состояние или проверяемое постусловие и
отвечающая за его достижение в рамках одного вызова.

Ключевая граница ответственности:

> Enforcer не выбирает, **какое** desired state нужно предметной области, но отвечает за
> то, чтобы переданное ему desired state / postcondition было достигнуто и подтверждено либо
> операция завершилась доказанным failure.

Типичный Direct-контракт:

```text
desired state / postcondition
    |
    v
Enforcer
    |
    +--> fresh observation
    +--> plan required changes
    +--> Reader / Executor operations
    +--> fresh observation
    +--> verification
    |
    v
SUCCESS | FAILURE
```

Enforcer может использовать один или несколько Backend/Driver boundaries и их Reader /
Executor operations. Он может самостоятельно содержать локальные технические операции, если
их выделение не создает полезной переиспользуемой границы.

Наличие прямого внешнего I/O поэтому **не делает компонент Driver автоматически**.
Определяющий признак Enforcer — ответственность за разовое достижение и подтверждение
caller-supplied desired state / postcondition.

Enforcer не должен выбирать предметную policy, ради которой desired state был выбран.
Эта ответственность остается у Manager или иного вышележащего caller.

Enforcer не является долговременным Controller/Manager только потому, что внутри одного
вызова использует цикл `observe -> plan -> actuate -> re-observe`. После завершения
вызова он не владеет обязанностью непрерывно поддерживать состояние среды; если такая
обязанность существует, ее lifecycle принадлежит Engine.

Enforcer не обязан быть классом. Stateless cohesive convergence operation может быть
функцией или набором процедур, если отдельный object boundary не дает архитектурной
ценности.

### 9.1. Direct Enforcer

Обычный случай: return завершает попытку materialization/convergence и сообщает, достигнуто
ли требуемое постусловие.

### 9.2. Indirect Enforcer

Indirect Enforcer допустим только с явно описанной completion semantics. Его synchronous
return не доказывает достижение desired state; фактическое завершение должно наблюдаться
отдельно.

Такая форма требует review особенно внимательно: часто она означает, что за границей
фактически скрыта самостоятельная нижняя система и верхнему уровню нужен Adapter либо
Manager/Agent boundary.

## 10. Driver

**Driver** — Machinery, являющаяся технической границей доступа к конкретному внешнему
механизму или технической среде и делающая эту среду доступной внутренней системе для
наблюдения и/или управления через определенный контракт.

Примеры внешних механизмов:

- kernel/netlink;
- nftables;
- sysctl;
- systemd;
- database protocol;
- process API;
- socket API;
- filesystem.

Driver знает технический контракт механизма и отвечает за корректную границу взаимодействия
с ним. В его ответственность могут входить:

- установление и проверка технического доступа к среде;
- namespace/socket/session/API/process boundary;
- преобразование contract inputs в конкретную техническую форму;
- нормализация ошибок доступа, transport/protocol failures и иных технических отказов;
- предоставление Reader- и/или Executor-операций непосредственно своими методами.

Driver не должен знать предметную policy вышележащего Engine и не владеет convergence к
caller-selected desired state.

Driver также может быть Direct или Indirect.

### 10.1. Direct Driver

Примеры:

```text
read current routes -> route snapshot
add route(spec)      -> technical execution result
```

Обе операции могут быть методами одного Driver, если выделение отдельных Reader/Executor
компонентов не дает архитектурной пользы.

### 10.2. Indirect Driver

Пример:

```text
submit long database job -> accepted/job_id
```

Внешняя операция продолжается после return. Ее результат при необходимости наблюдается
отдельным Engine, обычно Agent, использующим соответствующий read contract.

Наличие synchronous return у Driver никогда само по себе не доказывает, что внешняя
реальность достигла желаемого конечного состояния.

## 11. Reader, Executor и Backend

### 11.1. Reader

**Reader** — read-only техническая ответственность Machinery: выполнить предусмотренную
контрактом операцию наблюдения внешней технической среды и вернуть осмысленное текущее
представление наблюдаемого состояния.

Примеры:

```text
read_routes()        -> RouteSnapshot
read_forwarding()    -> ForwardingState
read_nft_owner()     -> NftOwnerSnapshot
```

Reader может выполнять parsing/normalization технического ответа, если это необходимо для
его contract result. Он не изменяет наблюдаемую им целевую среду и не является Engine:
самостоятельный polling, timers, publication и ownership наблюдаемого domain относятся к
Agent/Manager, а не к Reader.

### 11.2. Executor

**Executor** — техническая ответственность Machinery: выполнить одну конкретную
предусмотренную контрактом операцию изменения/воздействия на внешнюю техническую среду и
вернуть ее технический execution result.

Примеры:

```text
add_route(spec)          -> SUCCESS | technical failure
delete_rule(spec)        -> SUCCESS | technical failure
set_forwarding(DISABLED) -> SUCCESS | technical failure
```

Executor не решает:

- нужно ли выполнять эту операцию для достижения предметной цели;
- в каком порядке она должна выполняться относительно других операций;
- достигнут ли более широкий desired state после ее выполнения;
- нужно ли повторять, компенсировать или откатывать последовательность действий.

Эти обязанности, когда они нужны, принадлежат Enforcer либо вышележащему Engine.

Executor — не generic CLI/API passthrough. Его контракт задает конкретную техническую
операцию. Детали raw invocation могут быть скрыты внутри Driver/Executor implementation.

### 11.3. Когда Reader/Executor являются отдельными компонентами

Reader и Executor описывают ответственность, а не обязательную гранулярность декомпозиции.

Их следует выделять в самостоятельные Machinery-компоненты только когда это дает
практическую архитектурную ценность, например:

- переиспользуемый контракт;
- независимое тестирование или замена реализации;
- четкую границу ответственности;
- заметное упрощение композиции нескольких callers.

Если операция проста и естественно принадлежит конкретному Driver, Reader-/Executor-
функциональность может быть реализована непосредственно методом этого Driver.

Например оба варианта допустимы:

```text
RoutingDriver
    read_routes()
    add_route()
    delete_route()
```

и:

```text
RoutingDriver
    +--> RoutingReader
    +--> RouteExecutor
```

Не следует создавать отдельный компонент для каждой однострочной технической операции
только ради соответствия словарю ролей.

### 11.4. Backend

**Backend** — логическая композиционная единица реализации, предоставляющая сформированный
проектом внутренний API к конкретной внешней технической среде или ее части.

Backend может объединять:

- один или несколько Drivers;
- Reader/Executor responsibilities;
- technical parsers/normalizers;
- environment-specific constants/handles/configuration;
- небольшие локальные преобразования, необходимые для единого lower API.

Backend **не является отдельной component role** и не должен использоваться как название
для любого произвольного нижнего класса.

Backend не владеет:

- предметной policy;
- собственным desired state;
- convergence/reconciliation к caller-selected desired state;
- lifecycle внешней среды;
- скрытой историей предыдущих применений, от которой зависит корректность caller;
- orchestration последовательности действий ради достижения более широкого postcondition.

Backend может свежим образом наблюдать внешнее состояние и может хранить технические
handles/configuration, необходимые для доступа. Это не делает его state owner.

Практический смысл Backend:

> сгруппировать удобный для проекта lower API к одной технической среде, не превращая эту
> композицию в новый архитектурный тип или самостоятельный оркестратор.

### 11.5. Переход со старой терминологии

До этого изменения модель использовала термины `Executor` и `Runner` в других смыслах.
Для текущей архитектуры и реализации действует следующий transition mapping:

```text
old Executor
    owned desired-state convergence / postcondition verification
        -> Enforcer

old Runner
    executed one concrete contract-defined external technical action
        -> Executor

old read-only Driver/Backend slice
    isolated only when useful
        -> Reader
        or remains a read method of Driver

old narrow *Backend
    one concrete mechanism boundary rather than a composition bundle
        -> review as Driver / Reader / Executor

Backend
    retained only as a logical composition/facade term,
    not as a peer component role
```

Исторические review/experiment/result artifacts сохраняют использованную в них терминологию
как часть исходной доказательной записи. Текущая нормативная архитектура и текущий код должны
использовать новую терминологию при очередном затрагивании соответствующих имен.

## 12. Externally stateless Machinery

Для рассматриваемой предметной области Calculator, Adapter, Enforcer, Driver, а также
выделенные Reader и Executor считаются externally stateless независимо от их внутренней
реализации. Backend как композиция обязан сохранять тот же externally-stateless contract
для caller.

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
- не выбирает ли Enforcer предметный desired state вместо получения его от caller;
- не взял ли Driver/Backend на себя convergence к caller-selected desired state;
- не превратился ли Executor в скрытый Enforcer, самостоятельно решающий порядок и
  postcondition нескольких операций;
- не превратился ли Reader в Agent, самостоятельно владеющий polling/lifecycle/event
  publication;
- не назван ли узкий Driver/Reader/Executor словом Backend без реальной композиции;
- не протекла ли предметная policy в Driver/Backend.

### 16.4. Adapter vs Enforcer vs Driver vs Reader/Executor vs Backend

Adapter соединяет **предметные области**.

Enforcer отвечает за разовое достижение и подтверждение **заданного postcondition /
desired state**.

Driver является **технической границей доступа** к конкретному внешнему механизму/среде и
нормализует interaction/access failures.

Reader выполняет конкретную **операцию наблюдения**.

Executor выполняет конкретную **операцию изменения/воздействия**.

Backend группирует внутренний lower API к внешней технической среде, но сам не является
дополнительной component role.

Если компонент скрывает целую нижнюю предметную систему и представляет ее через контракт
верхней, это Adapter.

Если компонент принимает desired state и сам materialize/observe/verify его, это Enforcer,
даже если он напрямую использует Linux/netlink/nft/systemd/DB operations.

Если компонент отвечает прежде всего за техническую доступность и контракт конкретного
механизма, это Driver. Его read/write operations могут оставаться методами Driver.

Если отдельная read-only operation имеет полезную самостоятельную границу, это Reader.

Если отдельная mutation/action operation имеет полезную самостоятельную границу, это
Executor.

Если несколько таких lower responsibilities объединены в удобный проекту stateless facade
без собственной orchestration/convergence ответственности, эта композиция может называться
Backend.

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

Enforcer
    Machinery responsible for reaching/verifying a supplied desired state or postcondition

Driver
    technical boundary that makes one external mechanism/environment observable/manageable
    through an internal contract and normalizes interaction/access failures

Reader
    read-only technical operation returning an observed current representation;
    separate component only when useful

Executor
    one contract-defined technical actuation operation returning its execution result;
    separate component only when useful

Backend
    logical stateless composition/facade for the project's lower API to an external
    technical environment; not a separate component role

Event Delivery Environment
    asynchronous delivery only

InfoEvent
    "this is what I know/observe"

RequestEvent
    "I expect the environment to change as a consequence"
```
