# Компонентно-событийная модель — внешние аналоги

**Статус:** ненормативная исследовательская записка  
**Дата:** 2026-11-13  
**Связанный нормативный документ:** `design/component-model.md`

Цель записки — проверить, является ли принятая компонентно-событийная модель новым
специальным изобретением проекта или комбинацией известных архитектурных подходов.

Вывод: единственного общепринятого паттерна, совпадающего с моделью целиком, не найдено.
Модель естественно складывается из нескольких хорошо известных подходов. Большая часть ее
правил имеет прямые аналоги; несколько ограничений являются более строгими локальными
правилами проектирования.

## 1. Publish/Subscribe и Event-Driven Architecture

Ближайший аналог Event Delivery Environment — publish/subscribe event channel или message
bus.

Microsoft Azure Architecture Center описывает event-driven architecture через producers,
consumers и event channels; producer не знает, какие consumers слушают событие. В
publish/subscribe каждый заинтересованный subscriber получает публикацию.

AWS аналогично выделяет producers, event router и consumers и рассматривает router как
механизм развязки участников.

Это практически совпадает с нашей базовой моделью:

```text
Publisher -> Event Delivery Environment -> Subscribers
```

При этом наша Event Delivery Environment намеренно является более абстрактной: документ не
требует внешнего broker, durable queue или распределенной реализации. Та же семантика может
быть реализована внутри одного процесса.

Источники:

- Microsoft, *Event-Driven Architecture Style*:  
  https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven
- Microsoft, *Publisher-Subscriber Pattern*:  
  https://learn.microsoft.com/en-us/azure/architecture/patterns/publisher-subscriber
- AWS, *Event-Driven Architecture*:  
  https://aws.amazon.com/event-driven-architecture/

## 2. InfoEvent и RequestEvent

Enterprise Integration Patterns различает Command Message, Document Message, Event Message
и Request-Reply.

Наша пара семантик отображается примерно так:

```text
InfoEvent
    ~ Event Message
    ~ Event Notification
    ~ иногда Document Message / event-carried state

RequestEvent
    ~ Command Message
    != обязательный Request-Reply
```

Это важное совпадение: управляющее намерение и сообщение о факте действительно принято
различать даже при использовании одного transport/message mechanism.

NServiceBus также выделяет commands и events как два разных смысла сообщений: command
просит выполнить действие, event сообщает, что нечто произошло.

При этом наша модель сознательно отличается от типового command contract:

- RequestEvent может иметь несколько заинтересованных subscribers;
- publisher не обязан знать исполнителя;
- RequestEvent не открывает обязательный response channel;
- корректность может подтверждаться последующим наблюдением среды, а не reply от
  исполнителя.

Martin Fowler в *What do you mean by "Event-Driven"?* отдельно предупреждает о
"passive-aggressive command": сообщение называется event, хотя sender на самом деле
ожидает конкретного изменения. Это прямо поддерживает наше решение делать управляющее
намерение явной отдельной семантикой.

Источники:

- Enterprise Integration Patterns, *Messaging Patterns Overview*:  
  https://www.enterpriseintegrationpatterns.com/patterns/messaging/
- Enterprise Integration Patterns, *Command Message*:  
  https://www.enterpriseintegrationpatterns.com/patterns/messaging/CommandMessage.html
- Enterprise Integration Patterns, *Event Message*:  
  https://www.enterpriseintegrationpatterns.com/patterns/messaging/EventMessage.html
- Enterprise Integration Patterns, *Request-Reply*:  
  https://www.enterpriseintegrationpatterns.com/patterns/messaging/RequestReply.html
- Particular Software, *Messages, events, and commands*:  
  https://docs.particular.net/nservicebus/messaging/messages-events-commands
- Martin Fowler, *What do you mean by "Event-Driven"?*:  
  https://martinfowler.com/articles/201701-event-driven.html

## 3. Current-state publication и Event-Carried State Transfer

Наша практика хранить latest known projections и собирать из них текущий snapshot без
переопроса всей среды близка к Fowler's Event-Carried State Transfer.

В этом подходе publisher передает достаточно состояния, чтобы consumers могли поддерживать
локальную копию нужной им информации и не обращаться к publisher за каждым чтением.

Совпадение:

```text
InfoEvents carrying current projections
        ->
subscriber maintains latest values
        ->
current local snapshot
```

Отличие: наша модель не требует, чтобы event stream был историческим source of truth.
Локальный snapshot является текущим materialized view, а не Event Sourcing.

Поэтому потеря технологического cache допустима, если он может быть восстановлен свежими
публикациями.

Источник:

- Martin Fowler, *What do you mean by "Event-Driven"?*, раздел
  *Event-Carried State Transfer*:  
  https://martinfowler.com/articles/201701-event-driven.html

## 4. Manager и Kubernetes Controller/Operator

Ближайший широко используемый аналог нашей роли Manager — Kubernetes controller/operator.

Kubernetes определяет controller как control loop, который наблюдает current state,
сравнивает его с desired state и делает или запрашивает изменения, приближающие фактическое
состояние к требуемому. Controller затем наблюдает и сообщает текущее состояние.

Operator добавляет domain-specific knowledge о том, как управлять конкретной приложением
или сервисом.

Это близко к нашей формуле:

```text
RequestEvent / local policy
        +
observed managed environment
        ->
Manager
        ->
actuation
        ->
InfoEvent with current managed state
```

Различия:

- Kubernetes использует API objects как общий storage/control-plane contract; наша модель
  не требует общей базы объектов;
- Manager скрывает свою managed domain за собственной событийной проекцией;
- внутренняя reconciliation/state-machine механика Manager не является контрактом верхнего
  уровня;
- один Manager может быть верхнеуровневой оболочкой над целой нижней событийной
  подсистемой.

Источники:

- Kubernetes, *Controllers*:  
  https://kubernetes.io/docs/concepts/architecture/controller/
- Kubernetes, *Operator pattern*:  
  https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- Kubernetes, *Custom Resources / Custom controllers*:  
  https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/

## 5. Manager и IBM Autonomic Computing / MAPE-K

Еще более близкий исторический аналог внутреннего устройства Manager — autonomic manager
из IBM Autonomic Computing.

MAPE-K decomposes управление на:

```text
Monitor
Analyze
Plan
Execute
Knowledge
```

Autonomic manager получает данные от managed element через sensors и воздействует на него
через effectors. IBM также описывает иерархические варианты, где нижние managers управляют
частями среды, а верхний координирует их.

Это почти точное концептуальное описание того, что **может находиться внутри** нашего
Manager.

Однако наша внешняя модель сознательно не фиксирует MAPE-K decomposition. Для системы
верхнего уровня Manager остается black box с семантическим контрактом:

```text
Events in
managed-domain state out
```

Полезное различие: MAPE-K — возможная внутренняя реализация Manager, но не обязательная
структура каждого Manager.

Источники:

- IBM Redbooks, *Problem Determination Using Self-Managing Autonomic Technology*:  
  https://www.redbooks.ibm.com/redbooks/pdfs/sg246665.pdf
- IBM Redbooks, *IBM Virtualization Engine, V1: Planning and Installation Guide*:  
  https://www.redbooks.ibm.com/redbooks/pdfs/sg246771.pdf

## 6. Adapter и Ports & Adapters

Наша роль Adapter непосредственно родственна Hexagonal Architecture / Ports and Adapters
Alistair Cockburn.

Общее:

- предметная логика не должна знать техническую природу внешнего механизма;
- adapter переводит стабильный внутренний contract в конкретный внешний API/protocol;
- внешняя технология может быть заменена без изменения предметной модели;
- adapter является boundary, а не владельцем domain policy.

Наша модель намеренно вводит дополнительное локальное ограничение:

> Adapter является только синхронной технической границей.

Асинхронная связь вынесена в Event Delivery Environment и не называется Adapter. Такое
ограничение не является требованием оригинальной Hexagonal Architecture; оно принято ради
однозначности dependency graph и code review.

Источник:

- Alistair Cockburn, *Hexagonal Architecture / Ports and Adapters*:  
  https://alistair.cockburn.us/hexagonal-architecture

## 7. Message-driven и composability

Reactive Manifesto формулирует message-driven communication как способ получить loose
coupling, isolation и location transparency между компонентами. Ошибки при этом также могут
передаваться сообщениями.

Это соответствует нашей установке:

- peer participants связываются через Events;
- publisher не знает subscriber;
- feedback loop нормально замыкается через event edges;
- subsystem может быть скомпонована и затем представлена верхнему уровню как единый ресурс.

Источник:

- *The Reactive Manifesto*:  
  https://www.reactivemanifesto.org/

## 8. Синхронный DAG и асинхронный разрыв циклов

Правило:

```text
synchronous Adapter graph -> DAG
event graph               -> cycles allowed
```

не найдено как единый специализированный pattern с точно нашей формулировкой.

Оно является естественным следствием двух известных практик:

1. синхронные dependency cycles создают неявную взаимную ownership/reentrancy dependency;
2. asynchronous messaging используется для развязки producers и consumers.

Поэтому это следует считать **нашим нормативным review invariant**, а не ссылаться на
конкретный внешний паттерн как на его источник.

Особенно важно, что не любая "event-like" abstraction разрывает цикл. Если delivery
реализована inline и publisher зависит от завершения subscriber handler, синхронный cycle
фактически сохраняется. Для архитектурного разрыва требуется реальная asynchronous
boundary.

## 9. Что в модели является собственным решением

Следующие свойства являются локальными решениями, а не прямым копированием одного
внешнего подхода:

- всего две семантики межкомпонентных сообщений: InfoEvent и RequestEvent;
- RequestEvent не требует reply и может подтверждаться наблюдением среды;
- Agent определяется как observe-only частный случай Manager;
- Adapter используется только для synchronous technical boundary;
- event и synchronous Adapter dependencies разделяются на разные графы;
- synchronous Adapter graph обязан быть DAG;
- lower-level event-driven subsystem может быть свернута в единый resource за Adapter;
- statefulness не является отдельной архитектурной ролью;
- термин Engine не используется как тип компонента;
- технологический latest-state cache не считается историческим domain state.

## 10. Итоговое соответствие

```text
Наша модель                     Ближайшие внешние аналоги

Event Delivery Environment  ->  Pub/Sub, Message Bus, Event Router
InfoEvent                   ->  Event Message, Event Notification,
                                Event-Carried State Transfer
RequestEvent                ->  Command Message
Manager                     ->  Controller / Operator,
                                Autonomic Manager / MAPE-K
Agent                       ->  observational/sensor side of control systems
Adapter                     ->  Ports & Adapters
latest-state snapshot       ->  materialized/event-carried current state
event feedback loop         ->  message-driven/reactive control loop
sync Adapter DAG            ->  локально усиленное правило dependency design
```

Общий вывод: компонентно-событийная модель не противоречит сложившимся best practices и
не вводит новый механизм ради нового механизма. Она представляет собой более строгую
комбинацию известных подходов с небольшим набором собственных правил, полезных именно для
проведения и проверки границ ответственности.
