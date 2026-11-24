# Компонентно-событийная модель — внешние аналоги

**Статус:** ненормативная исследовательская записка  
**Дата:** 2026-11-13  
**Связанный нормативный документ:** `design/component-model.md`

Цель — проверить, насколько принятая модель совпадает с известными архитектурными
подходами.

Вывод: прямого единственного аналога нет. Модель складывается из нескольких давно
известных практик, но вводит собственную компактную таксономию `Engines/Machinery` и
несколько более жестких review invariants.

## 1. Event space: Publish/Subscribe и Event-Driven Architecture

`Event Delivery Environment` близка к publish/subscribe message bus/event router:

```text
Publisher -> Event Delivery Environment -> Subscribers
```

Producer не знает конкретных consumers и не зависит от их непосредственного return value.

Аналоги:

- Microsoft Event-Driven Architecture;
- Microsoft Publisher-Subscriber Pattern;
- AWS Event-Driven Architecture;
- Reactive Manifesto message-driven systems.

Источники:

- https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven
- https://learn.microsoft.com/en-us/azure/architecture/patterns/publisher-subscriber
- https://aws.amazon.com/event-driven-architecture/
- https://www.reactivemanifesto.org/

## 2. InfoEvent и RequestEvent

Enterprise Integration Patterns различает Event Message и Command Message.
NServiceBus также разделяет commands и events по смыслу.

Наше соответствие:

```text
InfoEvent
    ~ Event Message / Event Notification

RequestEvent
    ~ Command Message
    != обязательный Request-Reply
```

Локальное отличие: `RequestEvent` не обязан иметь единственного адресата и не открывает
обязательный response channel. Результат может подтверждаться через последующее наблюдение
среды.

Martin Fowler отдельно предупреждает о "passive-aggressive command": сообщении, которое
называется event, хотя sender фактически ожидает конкретного изменения. Это поддерживает
наше явное разделение Info/Request semantics.

Источники:

- https://www.enterpriseintegrationpatterns.com/patterns/messaging/
- https://www.enterpriseintegrationpatterns.com/patterns/messaging/CommandMessage.html
- https://www.enterpriseintegrationpatterns.com/patterns/messaging/EventMessage.html
- https://www.enterpriseintegrationpatterns.com/patterns/messaging/RequestReply.html
- https://docs.particular.net/nservicebus/messaging/messages-events-commands
- https://martinfowler.com/articles/201701-event-driven.html

## 3. Manager: control loop / controller / autonomic manager

Наш `Manager` близок к Kubernetes controller/operator:

```text
desired/current inputs
        +
observed managed domain
        ->
control loop
        ->
actuation
        ->
new observed state
```

Kubernetes controller постоянно сравнивает current и desired state и воздействует на
окружение, приближая их друг к другу.

IBM Autonomic Computing / MAPE-K еще ближе описывает возможную внутреннюю кухню Manager:

```text
Monitor
Analyze
Plan
Execute
Knowledge
```

с sensors/effectors вокруг managed resource.

Локальное решение нашей модели: MAPE-K decomposition не является внешним контрактом
Manager. Она может существовать внутри, но верхний уровень видит только его event contract
и текущую managed-domain projection.

Источники:

- https://kubernetes.io/docs/concepts/architecture/controller/
- https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- https://www.redbooks.ibm.com/redbooks/pdfs/sg246665.pdf

## 4. Agent: sensor/observer side of control systems

`Agent` соответствует наблюдающей стороне control/monitoring systems:

- sensors в autonomic systems;
- observers/watchers;
- monitoring agents.

Наша локальная классификация строже по семантике:

```text
Agent   = observe
Manager = observe + actuate
```

Внутренний statefulness, timers или hysteresis не меняют эту классификацию.

## 5. Current-state publication и Event-Carried State Transfer

Хранение latest known projections близко к Fowler's Event-Carried State Transfer:

```text
InfoEvents carrying state
        ->
subscriber maintains current local projection
```

Но это не Event Sourcing:

- event history не является source of truth;
- cache можно восстановить свежими публикациями;
- прошлые events не обязаны сохраняться.

Источник:

- https://martinfowler.com/articles/201701-event-driven.html

## 6. Adapter: Ports & Adapters плюс semantic boundary

Текущий `Adapter` родственен Ports & Adapters, но используется шире как граница между
двумя предметными областями.

```text
Domain A
   |
 Adapter
   |
Domain B
```

Adapter может скрывать целую нижележащую систему и преобразовывать domain-A contract в
domain-B contract.

Это также близко к:

- Anti-Corruption Layer;
- Facade;
- Gateway;
- client library к самостоятельной подсистеме.

Локальная особенность: все, что находится за Adapter boundary, для вызывающей области
считается частью Adapter независимо от внутренней сложности.

Источник для базовой Ports & Adapters идеи:

- https://alistair.cockburn.us/hexagonal-architecture

## 7. Driver: technical edge

После уточнения терминологии непосредственная техническая граница к kernel, systemd, DB,
socket API и т. п. называется `Driver`.

Это хорошо соответствует обычному смыслу driver:

```text
internal representation
        ->
Driver
        ->
specific external mechanism
```

Driver не является предметным boundary между двумя semantic domains; он знает внешний
технический protocol/API.

Такое разделение полезно, потому что Ports & Adapters часто использует слово adapter и для
semantic, и для technical boundary. Наша модель намеренно различает их.

## 8. Machinery: Direct и Indirect

Разделение Direct/Indirect имеет аналоги в обычном synchronous/asynchronous API design.

### Direct

```text
call -> requested result
```

### Indirect

```text
call -> accepted/submitted
...
result -> later observation/event
```

Это близко к:

- asynchronous command submission;
- job/queue APIs;
- promise-of-work semantics без обязательного future в том же call graph;
- task submission в orchestration/process-management systems.

Локальное правило сильнее обычного API-разделения:

> acknowledgement Indirect Machinery никогда не является доказательством достигнутого
> предметного результата.

Результат возвращается в рассматриваемую систему через Engine/Event path.

## 9. Engines и Machinery

Таксономия:

```text
Engines
    Managers
    Agents

Machinery
    Calculators
    Adapters
    Drivers
```

является локальным проектным словарем. Прямого стандартного паттерна с такими двумя
семействами не найдено.

Однако разделение совпадает с распространенным различием между:

- active objects / actors / controllers / workers;
- callable services/helpers/gateways/drivers.

Ключевое локальное свойство Machinery — **externally stateless** относительно caller:
скрытая история ее внутренних вызовов не должна быть частью correctness contract верхней
области.

## 10. Synchronous dependency DAG

Правило:

```text
synchronous dependency graph inside one domain -> DAG
event graph                                   -> cycles allowed
```

является нашим нормативным review invariant.

Оно согласуется с общими практиками:

- избегать cyclic dependencies;
- использовать asynchronous messaging для decoupling;
- строить layered/acyclic dependency structures.

Но точная формулировка относительно domain boundary — локальная:

1. внутри рассматриваемой предметной области проверяется полный synchronous dependency DAG;
2. Adapter завершает архитектурную видимость нижней области;
3. нижняя область не должна устанавливать независимый synchronous back-edge обратно через
   эту границу;
4. asynchronous Event feedback через границу допустим.

## 11. Что является собственным решением модели

Локально зафиксированы:

- два семейства компонентов: Engines и Machinery;
- Manager/Agent как две роли Engines;
- Calculator/Adapter/Driver как роли Machinery;
- Direct/Indirect как независимая характеристика Machinery;
- externally-stateless contract Machinery;
- Adapter как semantic/domain boundary;
- Driver как technical boundary;
- InfoEvent/RequestEvent без обязательного response;
- текущие projections вместо event history как source of truth;
- synchronous DAG внутри каждой предметной области;
- запрет independent synchronous back-edge через Adapter boundary;
- возможность рекурсивно скрывать целую событийную систему за Adapter.

## 12. Итоговая карта

```text
Наша модель                     Ближайшие аналоги

Event Delivery Environment  ->  Pub/Sub, Message Bus, Event Router
InfoEvent                   ->  Event Message, Event Notification
RequestEvent                ->  Command Message
Manager                     ->  Controller / Operator / Autonomic Manager
Agent                       ->  Observer / Sensor / Monitoring Agent
latest projections          ->  Event-Carried State Transfer
Adapter                     ->  Ports & Adapters / ACL / Facade / Gateway
Driver                      ->  technical driver/client to external mechanism
Indirect Machinery          ->  async submission / job API
Engine/Machinery taxonomy   ->  локальная классификация
sync DAG invariant          ->  локально усиленное dependency rule
```

Общий вывод: модель использует известные архитектурные идеи, но сознательно собирает их в
более строгий и локально проверяемый словарь.
