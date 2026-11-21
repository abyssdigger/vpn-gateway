# VPN-GATE NG3 — структурированная архитектура

**Статус:** рабочий структурированный вид архитектуры NG3  
**Исходная архитектура:** `design/NG3/architecture.md`  
**Компонентная модель:** `design/component-model.md`  
**Требования:** `design/NG3/requirements.md`

Этот документ создается рядом с текущей плоской архитектурой как человекочитаемая
структурированная проекция тех же архитектурных решений.

До завершения последовательного переноса и review источником уже принятых архитектурных
решений остается `design/NG3/architecture.md`. Перенос решения сюда сам по себе не меняет
его семантику, requirement traceability или evidence.

## 1. Проект

VPN-GATE — управляемый сетевой узел для передачи выбранного IP-трафика между обычной сетью
и поддерживаемыми VPN-путями в соответствии с текущей политикой продукта.

На верхнем уровне архитектура рассматривается как набор непересекающихся **Spaces**.
Space — самостоятельная архитектурная область со своими состоянием, жителями и доступными
из других Spaces точками взаимодействия. Space может быть большой предметной областью или
маленьким переходным «тамбуром», связывающим две существенно разные среды.

Transition Space остается полноценным Space: он может иметь собственное состояние и API,
может быть заменен другой реализацией и не считается органической частью соседних Spaces
только потому, что текущая реализация мала.

### Spaces

Имена в первом проходе рабочие; границы важнее конкретного названия.

1. `STACK` *Внутренняя среда VPN-GATE, в которой живут верхнеуровневая policy, orchestration и другие core-компоненты продукта.*
2. `STACK-HOST transition` *Переходный Space между STACK и host-side сетевой средой; отдельный заменяемый «тамбур» со своим состоянием и контрактами.*
3. `Private network` *Отдельная управляемая и наблюдаемая из STACK сетевая реальность, содержащая принадлежащее VPN-GATE сетевое состояние и machinery доступа к нему.*
4. `VPN external ends` *Совокупная внешняя VPN-среда; для архитектуры VPN-GATE существенна прежде всего обращенная к нему сторона ее VPN-интерфейсов/endpoints.*
5. `Helper-managed host` *Часть host state, которой VPN-GATE явно управляет через свои host-side helpers.*
6. `Ambient host and external world` *Остальной host и внешний мир, воспринимаемый через него, не принадлежащие core ownership VPN-GATE.*
7. `Operator` *Среда оператора VPN-GATE и его точки взаимодействия с продуктом.*

## 2. Нотация

### 2.1. Residents и Subcomponents

Каждый Space обязан содержать раздел `Residents`.

Space без resident'ов для этой модели ненаблюдаем и неуправляем со стороны VPN-GATE и
считается признаком недоделанной архитектуры, а не законченной пустой областью.

Компонент может содержать `Subcomponents`; этот раздел приводится только когда
subcomponents действительно существуют.

Все списки Spaces, Residents и Subcomponents оформляются одинаково:

```text
1. `Имя` *краткое описание*
2. `@Имя` *краткое описание*
3. `Имя <partial>` *краткое описание*
```

Вложенный компонент оформляется подразделом своего parent-компонента.

### 2.1.1. Критерий вложенности

Компонент следует помещать в `Subcomponents` parent-компонента, когда одновременно
выполняются два условия:

1. API компонента не востребован самостоятельно клиентами вне parent;
2. корректность, lifecycle или используемые им инварианты существенно определяются
   контрактом parent, поэтому независимое существование компонента на этом уровне не дает
   отдельной архитектурной границы.

Если компонент имеет самостоятельных внешних клиентов, независимый lifecycle/state contract
или является общей зависимостью нескольких равноправных parent'ов, его следует поднимать к
ближайшему общему уровню, а не прятать под удобного caller'а.

Наличие глубокого `@` допускается как честное описание текущей архитектуры, но является
основанием проверить, не пропущен ли такой подъем или отдельная boundary.

### 2.2. API Space

API Space — объединение той части API его resident'ов, которая востребована клиентами из
других Spaces.

Самостоятельного «магического» API поверх resident'ов у Space нет.

Для конкретного взаимодействия действуют два механических правила:

1. API принадлежит тому Space, внутри которого находится обслуживающая сторона
   взаимодействия — server.
2. Интерфейс является API Space только тогда, когда его client находится вне этого Space.

Если и server, и все clients находятся внутри одного Space, это внутренний контракт, а не
API Space.

Асинхронность правило не меняет. В конкретной точке взаимодействия существует server-side
broker/queue/API и его client; размещение обслуживающей стороны определяет принадлежность
этого API.

### 2.3. Маркер `@`

Префикс `@` означает непосредственный внешний вход в текущий Space.

В списке Residents/Subcomponents:

```text
@NetworkPolicyAdapter
```

означает, что API этого resident'а непосредственно востребован клиентом из другого Space и
поэтому участвует в API текущего Space.

У глубоко вложенного subcomponent префикс `@` является review signal: внешний client
пробивает несколько уровней внутренней структуры, поэтому границу/decomposition следует
перепроверить.

В списке API префикс ставится у конкретной точки взаимодействия, входящей в API Space:

```text
@NetworkPolicyAdapter.apply(...)
@vpn_iff[].<outbound port>
```

Если внешний вызов приходит в метод parent-компонента, а тот внутри использует метод
subcomponent, API Space содержит метод parent. Внутренний метод subcomponent от этого не
становится методом Space.

### 2.4. Метод

`Method` используется как универсальное обозначение адресуемой точки взаимодействия.
Конкретная форма зависит от природы resident'а.

Для обычного программного контракта:

```text
apply(desired_state)
observe(...)
health(∅)
```

Для интерфейсной/сетевой точки допустима предметная форма:

```text
<inbound socket>
<outbound port>
```

Обозначения параметров:

- `(...)` — параметры существуют, но их состав намеренно не раскрывается на этом уровне;
  например контракт еще меняется или полный список мешает чтению;
- `(∅)` — метод точно не принимает параметров;
- явный список параметров приводится, когда он устойчив и полезен именно на этом уровне.

Подробный контракт метода может жить в его собственном описании; краткая архитектурная
структура не обязана дублировать длинную сигнатуру.

### 2.5. `<partial>`

Если один архитектурный компонент фактически предоставляет API нескольких Spaces, он
показывается в каждом таком Space как частичная проекция:

```text
ComponentName <partial>
```

`<partial>` описывает существующий факт, но одновременно является review signal: следует
проверить, действительно ли компонент должен пересекать несколько Spaces или архитектура
пропустила естественную границу decomposition.

Смысл `<partial>` и любых будущих дополнительных suffix/prefix markers кратко поясняется в
описании соответствующего компонента. Такие markers не должны превращаться в способ
маскировать непонятную архитектуру.

## 3. Форма описания Space

Каждый Space оформляется отдельным разделом.

Минимальная шапка:

```text
# <Space>

<краткое описание назначения и границы>

API
    @Resident.method(...)
    @Resident.<interaction point>

Residents
    1. `@ResidentA` *краткое описание*
    2. `ResidentB` *краткое описание*
```

Раздел `Residents` обязателен.

Раздел `API` может быть опущен, если краткое описание Space уже однозначно отсылает к API
помеченных `@` resident'ов и отдельный список ничего не добавляет.

## 4. Форма описания компонента

Resident оформляется подразделом своего Space. Вложенный компонент — подразделом parent.

Шапка компонента:

```text
## @ComponentName

<краткое описание ответственности, границы и применимых suffix/prefix markers>

API
    @space_level_method(...)
    internal_method(...)

Subcomponents
    1. `ChildA` *краткое описание*
    2. `@ChildB` *краткое описание*

Architectural decisions
    ...
```

`API` перечисляет точки взаимодействия компонента до уровня метода/endpoint. `@` получают
только те из них, которые непосредственно входят в API текущего Space.

`Subcomponents` приводится только при наличии вложенных компонентов.

### Architectural decisions

При первоначальном переносе под компонент собираются относящиеся к нему решения из текущей
`design/NG3/architecture.md` без попытки одновременно исправить их decomposition.

Такой блок сначала является совокупностью еще не обработанных архитектурных решений.
Дальнейший review должен определить, какие решения действительно принадлежат компоненту,
какие относятся к его subcomponents или другому Space, а какие обнаруживают необходимость
нового архитектурного принципа.

Перенос решения в структурированный документ не является основанием менять его requirement
traceability, semantics или evidence.

# Private network

Отдельная сетевая среда VPN-GATE, управляемая и наблюдаемая из STACK.
Содержит VPN-GATE-owned сетевое состояние и resident'ов, через которые другие Spaces
наблюдают и изменяют эту реальность. Технические детали Linux/network namespace являются
внутренней реализацией resident'ов, пока отдельный внешний контракт не требует иного.

API

    @NetworkPolicyAdapter.observe_owned_policy(...) — вернуть свежую owner-scoped проекцию управляемой network policy.
    @NetworkPolicyAdapter.apply(...) — применить semantic desired policy и подтвердить postcondition.
    @NetworkPolicyAdapter.cleanup(...) — удалить owned policy scope и подтвердить его отсутствие.
    @VPNPathAdapter.observe_device_endpoints(...) — наблюдать текущие candidate endpoints в Private network.
    @VPNPathAdapter.verify_path_binding(...) — подтвердить однозначный current binding logical path к endpoint.
    @ForwardingGate.observe(∅) — вернуть свежий authoritative state корневого forwarding gate.
    @ForwardingGate.converge(...) — установить требуемое состояние gate и подтвердить его свежим наблюдением.

Residents

1. `@NetworkPolicyAdapter` *Semantic boundary между policy клиентов из STACK и ее lower realization/convergence внутри Private network.*
2. `@VPNPathAdapter` *Boundary наблюдения и проверки concrete VPN endpoints, уже присутствующих в Private network.*
3. `@ForwardingGate` *Самостоятельный verified control корневого IPv4 forwarding barrier; нужен как network-policy convergence, так и lifecycle/safety клиентам.*

## @NetworkPolicyAdapter

Adapter принимает owner-scoped semantic network policy и скрывает ее lower representation,
allocation, observation и convergence. Payload policy и probe policy остаются разными
semantic owners даже при общей физической реализации.

API

    @observe_owned_policy(...) — наблюдать текущее owned policy state.
    @apply(...) — применить desired semantic policy и подтвердить postcondition.
    @cleanup(...) — удалить owned policy и подтвердить отсутствие.

Subcomponents

1. `NetworkPolicyEnforcer` *Достигает и подтверждает переданный Adapter'ом desired lower network-policy state; сам desired state не выбирает.*

Architectural decisions

1. `Semantic boundary` *Upper clients не знают route-table allocation, route protocol markers, RPDB priorities, gateway/onlink representation, nft/sysctl syntax, command ordering и transaction scratch state.*
2. `Owner separation` *Общая physical realization не сливает payload, probe и другие semantic owner scopes; ownership должен оставаться различимым при observation, mutation и cleanup.*
3. `Lower realization` *Adapter обязан получить достаточные verified lower facts и owned-resource allocation; неизвестную gateway/onlink или другую physical realization запрещено угадывать.*
4. `Cross-Space finding` *Существующий flat architecture также приписывает этому Adapter host-side Device publication mapping. В structured architecture этот sub-contract пока не заселяется сюда: его server находится вне Private network, а сохранение его под этим Adapter потребовало бы `<partial>` и отдельного review границы.*

### NetworkPolicyEnforcer

Enforcer отвечает только за достижение и подтверждение переданного desired state.
Он не является Space API: в выбранной декомпозиции его клиентом является
`NetworkPolicyAdapter`, а independently demanded safety/lifecycle API вынесен в
`@ForwardingGate`.

**Implements:**
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0003-R3.R9`
- `VPNG0004-R4.R3.R2`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R5`

API

    converge_priority(...) — изменить только effective order неизменного набора eligible paths.
    converge_structural(...) — привести более широкое structural policy state к desired postcondition.

Architectural decisions

1. `Общий контракт convergence`
   *Каждая попытка строится от fresh authoritative observation: observe -> plan -> bounded actuation -> fresh observation -> exact postcondition verification. Успех lower command не является подтверждением результата; stale plan не переигрывается, hidden retry отсутствует.*

2. `Два класса transition`
   *Pure-priority transition и structural transition имеют разные safety proofs и не должны схлопываться в один универсальный mutation algorithm.*

   1. `Pure priority`
      *Когда меняется только порядок того же eligible path set, используется make-before-break permutation внутри одного independently observable route-key domain. Path membership сохраняется; временная duplicate route допустима только для того же logical path; Profile считается converged только после fresh verification всех затронутых domains.*

   2. `Structural`
      *Изменение membership, direction, filtering/NAT или другой structural semantics допускает временное ограничение forwarding. Enforcer принимает complete desired lower state как input и не является владельцем его semantic compilation.*

3. `Structural barrier dependency`
   *Перед allowing structural mutation Enforcer требует независимо подтвержденный `ForwardingGate=DISABLED`. Сам `ForwardingGate` не является subcomponent Enforcer: его API независимо востребован lifecycle/safety клиентами.*

4. `Exact-before-release`
   *Structural state изменяется под закрытым gate: сначала restrictive guards и удаление stale activation/routing state, затем required routes и nft state, затем activation dispatch. Gate может быть открыт только после exact routing+nft postcondition; после открытия выполняется fresh final verification.*

5. `Failure and recovery`
   *После partial/failed mutation authoritative state устанавливается заново. Неподтвержденное состояние остается restrictive. Если final verification после открытия gate не проходит, Enforcer пытается вернуть gate в verified DISABLED и сообщает failure, а не success.*

6. `Lower technical boundary`
   *Drivers/Readers/Executors и Backend-композиции предоставляют observation/actuation primitives, но не выбирают desired state и не владеют convergence. Linux JSON/argv shapes, numeric pools и platform constants принадлежат lower technical realization, а не API Enforcer.*

Исходная flat architecture смешивает с этой ответственностью несколько соседних решений.
В structured view они намеренно отделены:

- complete structural desired-state projection относится к Adapter/Calculator side и является input Enforcer;
- raw route/RPDB/nft observation formats относятся к lower Reader/Backend;
- корневой `ForwardingGate` является отдельным resident Private network;
- будущий administrative payload-containment control не является разновидностью structural
  Enforcer и требует отдельного публичного operational contract.

## @VPNPathAdapter

Adapter наблюдает уже существующие в Private network concrete VPN endpoints и проверяет их
соответствие logical VPN-path intent. Он не создает, не перемещает и не конфигурирует VPN
session/endpoint.

API

    @observe_device_endpoints(...) — получить свежие candidate endpoints из managed domain.
    @verify_path_binding(...) — подтвердить current endpoint для logical path либо вернуть absent/ambiguous/unusable result.

## @ForwardingGate

Самостоятельный Enforcer корневого IPv4 forwarding state Private network. Его verified
DISABLED state используется как structural safety barrier, но тот же contract нужен startup,
shutdown и recovery независимо от `NetworkPolicyAdapter`.

API

    @observe(∅) — получить свежий authoritative gate state.
    @converge(...) — observe, при необходимости выполнить mutation и свежим reread подтвердить requested state.

Subcomponents

1. `ForwardingGateDriver` *Технический доступ к managed-domain forwarding state: свежий read и одна mutation attempt без самостоятельного postcondition ownership.*
