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

### 2.1. Residents tree и component addenda

Каждый Space обязан содержать раздел `Residents`.

Space без resident'ов для этой модели ненаблюдаем и неуправляем со стороны VPN-GATE и
считается признаком недоделанной архитектуры, а не законченной пустой областью.

`Residents` является **единственным источником иерархии компонентов Space**. Parent-child
отношение показывается вложенностью обычного списка и не дублируется уровнем заголовков,
порядком component specs или отдельными `Subcomponents`-блоками.

Элемент дерева оформляется так:

```text
1. `Имя` *краткое описание*
    1. `Child` *краткое описание*
2. `@Имя` *краткое описание*
3. `Имя <partial>` *краткое описание*
```

Все компоненты, встречающиеся в дереве `Residents`, описываются ниже в плоском
`Component addenda` этого Space. Все component specs внутри addendum имеют одинаковый
уровень заголовка. Иерархия из их расположения не выводится.

Если компонент представлен в Space как `<partial>` или иным review-marker, причина
маркера поясняется в его кратком component spec.

Если одна technical component identity представлена как `<partial>` в нескольких Spaces,
каждый Space содержит собственный addendum spec только для своей проекции этого компонента.
Общая technical identity не создает скрытого глобального spec поверх Spaces и не заменяет
Space-local описание ответственности/API этой partial occurrence.

### 2.1.1. Критерий вложенности

Компонент следует показывать child'ом другого компонента в дереве `Residents`, когда
одновременно выполняются два условия:

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

В дереве `Residents`:

```text
@NetworkPolicyAdapter
```

означает, что API этого resident'а непосредственно востребован клиентом из другого Space и
поэтому участвует в API текущего Space.

У глубоко вложенного resident префикс `@` является review signal: внешний client
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

## 4. Component addenda

После шапки Space и дерева `Residents` следует его `Component addenda`.

Каждый resident дерева получает отдельный component spec. Все specs внутри одного Space
оформляются на одном уровне заголовков независимо от глубины компонента в `Residents`.

Пример:

```text
## Component addenda

### ParentComponent

<краткое описание ответственности и границы>

API
    @space_level_method(...)
    internal_method(...)

Architectural decisions
    ...

### ChildComponent

<краткое описание ответственности и границы>

API
    internal_method(...)

Architectural decisions
    ...
```

Parenthood определяется только деревом `Residents`. Component spec не содержит
`Subcomponents` и не кодирует parenthood уровнем заголовка.

`API` перечисляет точки взаимодействия компонента до уровня метода/endpoint. `@` получают
только те из них, которые непосредственно входят в API текущего Space.

### Architectural decisions

При первоначальном переносе под component spec собираются относящиеся к нему решения из
текущей `design/NG3/architecture.md` без попытки одновременно исправить их decomposition.

Такой блок сначала является совокупностью еще не обработанных архитектурных решений.
Дальнейший review должен определить, какие решения действительно принадлежат компоненту,
какие относятся к его parent/children или другому Space, а какие обнаруживают необходимость
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
    1. `NetworkPolicyLayoutCalculator` *Детерминированно распределяет внутренние routing/RPDB/metric/nft resources между semantic owner scopes.*
    2. `NetworkPolicyEnforcer` *Достигает и подтверждает переданный Adapter'ом desired lower network-policy state.*
2. `@VPNPathAdapter` *Boundary наблюдения и проверки concrete VPN endpoints, уже присутствующих в Private network.*
3. `@ForwardingGate` *Самостоятельный verified control корневого IPv4 forwarding barrier; нужен как network-policy convergence, так и lifecycle/safety клиентам.*
    1. `ForwardingGateDriver` *Технический read/mutation boundary к managed-domain forwarding state.*

## Component addenda

### NetworkPolicyAdapter

Adapter принимает owner-scoped semantic network policy и скрывает ее lower representation,
allocation, observation и convergence. Payload policy и probe policy остаются разными
semantic owners даже при общей физической реализации.

API

    @observe_owned_policy(...) — наблюдать текущее owned policy state.
    @apply(...) — применить desired semantic policy и подтвердить postcondition.
    @cleanup(...) — удалить owned policy и подтвердить отсутствие.

Architectural decisions

1. `Semantic boundary` *Upper clients не знают route-table allocation, route protocol markers, RPDB priorities, gateway/onlink representation, nft/sysctl syntax, command ordering и transaction scratch state.*
2. `Owner separation` *Общая physical realization не сливает payload, probe и другие semantic owner scopes; ownership должен оставаться различимым при observation, mutation и cleanup.*
3. `Lower realization` *Adapter обязан получить достаточные verified lower facts и owned-resource allocation; неизвестную gateway/onlink или другую physical realization запрещено угадывать.*
4. `Cross-Space finding` *Существующий flat architecture также приписывает этому Adapter host-side Device publication mapping. В structured architecture этот sub-contract пока не заселяется сюда: его server находится вне Private network, а сохранение его под этим Adapter потребовало бы `<partial>` и отдельного review границы.*

### NetworkPolicyLayoutCalculator

Pure Calculator внутреннего resource layout. Он получает semantic owner demand и injected
platform resource space и возвращает детерминированное распределение внутренних
routing-table, RPDB, route-marker, metric и nft namespace ресурсов.

API

    allocate(payload_profiles, probe_routing_demands, platform) — построить NetworkPolicyLayout без observation или mutation внешней среды.

Его API не входит в API Space: numeric/internal allocation требуется только
`NetworkPolicyAdapter` и не является самостоятельным контрактом для STACK.

Architectural decisions

1. `Semantic ownership first`
   *Allocation начинается от semantic owner scopes. Kernel table/rule/protocol/metric numbers являются internal realization и не становятся identity пользователя или policy owner.*

2. `Deterministic current allocation`
   *Одинаковый accepted owner set и platform space дают одинаковый layout. Durable allocation journal/hash map не требуется, а стабильность numeric IDs между structural configuration changes не обещается.*

3. `Separated resource classes`
   *Payload и probe используют раздельные table/RPDB pools. Probe RPDB должен иметь более высокий precedence, payload RPDB — выполняться до ambient/main lookup.*

4. `Payload domain completeness`
   *Каждый enabled payload Profile получает собственную internal routing table даже при zero-path state. Zero-path Profile сохраняет table/terminal guard allocation, но не получает preference/scratch metric space.*

5. `Metric workspace`
   *Для Profile с реализованными paths выделяются strictly increasing preference slots, при необходимости отдельный scratch slot для make-before-break и отдельный terminal guard metric. Непредставимый path count отвергается до mutation.*

6. `Dispatch ordering`
   *Payload dispatch priorities распределяются детерминированно: longest prefix first, затем network address, затем Profile ID только как deterministic tie-break.*

7. `Allocation is not cleanup authority`
   *Reserved pool membership и current allocation map сами по себе не доказывают ownership произвольного kernel object. Stale/foreign cleanup требует отдельной exact observation/shape classification.*

8. `Injected platform contract`
   *Конкретные Linux numeric pools, protocol markers и nft namespace приходят через platform contract, не из user configuration. Их конкретные значения являются evidence-gated platform facts, а не частью semantic API Calculator.*

### NetworkPolicyEnforcer

Enforcer отвечает только за достижение и подтверждение переданного desired state.
Он не является Space API: в дереве `Residents` его parent — `NetworkPolicyAdapter`,
а independently demanded safety/lifecycle API вынесен в sibling `@ForwardingGate`.

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
   *Перед allowing structural mutation Enforcer требует независимо подтвержденный `ForwardingGate=DISABLED`. Сам `ForwardingGate` не является child Enforcer: его API независимо востребован lifecycle/safety клиентами. Gate блокирует routed IPv4 forwarding, но не делает автоматически безопасным local `stack_input/stack_output` traffic; такие owner classes сохраняют собственные atomic/exact safety contracts.*

4. `Exact-before-release`
   *Structural state изменяется под закрытым gate: сначала restrictive guards и удаление stale activation/routing state, затем required routes и nft state, затем activation dispatch. Gate может быть открыт только после exact routing+nft postcondition; после открытия выполняется fresh final verification.*

5. `Failure postcondition`
   *После partial/failed mutation Enforcer заново наблюдает authoritative state и не продолжает stale plan. Неподтвержденное состояние остается restrictive. Если final verification после открытия gate не проходит, Enforcer пытается вернуть gate в verified DISABLED и сообщает failure, а не success. Любая более поздняя retry/reconciliation attempt принадлежит caller/Manager и начинается из нового fresh state.*

6. `Lower technical boundary`
   *Drivers/Readers/Executors и Backend-композиции предоставляют observation/actuation primitives, но не выбирают desired state и не владеют convergence. Linux JSON/argv shapes, numeric pools и platform constants принадлежат lower technical realization, а не API Enforcer.*

Исходная flat architecture смешивает с этой ответственностью несколько соседних решений.
В structured view они намеренно отделены:

- complete structural desired-state projection относится к Adapter/Calculator side и является input Enforcer;
- raw route/RPDB/nft observation formats относятся к lower Reader/Backend;
- корневой `ForwardingGate` является отдельным resident Private network;
- будущий administrative payload-containment control не является разновидностью structural
  Enforcer и требует отдельного публичного operational contract.

### VPNPathAdapter

Adapter является boundary между logical VPN-path semantics и уже provisioned concrete VPN
endpoint внутри Private network. Он наблюдает/проверяет lower-domain facts, но не создает и
не управляет VPN session как таковой.

**Implements:**
- `VPNG0001-R1.R3.R1`
- `VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R3.R3`
- `VPNG0001-R1.R3.R4`
- `VPNG0001-R1.R3.R4.R1`
- `VPNG0001-R1.R3.R4.R2`
- `VPNG0001-R1.R3.R4.R3`
- `VPNG0001-R1.R3.R4.R3.R1`
- `VPNG0001-R1.R3.R4.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R5`

API

    @observe_device_endpoints(...) — получить свежие candidate endpoints из Private network.
    @verify_path_binding(...) — подтвердить current endpoint для logical path либо вернуть absent/ambiguous/wrong-domain/unusable result.

Architectural decisions

1. `Observation, not provisioning`
   *Adapter только наблюдает и проверяет уже существующий endpoint. Создание VPN session, credentials, protocol configuration и помещение endpoint в Private network принадлежат внешней VPN integration/admin side.*

2. `Fresh authoritative observation`
   *Каждое observation получает новый полный snapshot relevant endpoint inventory. Periodic timer является только wakeup mechanism; cache/generation registry не становится source of truth.*

3. `Failure is not absence`
   *Command/parse/observation failure возвращается как observation failure и не превращается в пустой endpoint set. Неизвестное состояние нельзя интерпретировать как доказанное отсутствие.*

4. `Concrete endpoint identity`
   *Current endpoint различается по concrete interface generation, включая exact `(ifname, ifindex)`. Same-name replacement не наследует current binding автоматически.*

5. `Binding postcondition`
   *Успешный binding должен доказать, что endpoint находится в Private network, соответствует normalized logical-path intent, выбран однозначно и не является superseded generation. Новый endpoint становится current только после нового observation+verification.*

6. `No upper policy ownership`
   *Adapter не выбирает Profile policy, Device preference, payload eligibility или availability health и не определяет human configuration grammar.*

7. `Optional transport provenance`
   *Если supported integration может доказать transport endpoint provenance, факт привязывается к exact current `PathBinding`, а не к стабильному `LogicalPathId`. Provenance нельзя угадывать из interface prefix/name, inner peer, ambient routes или другого unrelated lower fact; при отсутствии достаточного evidence он остается absent/unresolved.*

Маршрутная gateway/onlink realization из current binding намеренно пока не включена в этот
spec: flat architecture требует такой lower integration fact, но точная component ownership
этого контракта еще не установлена в structured tree.

### ForwardingGate

Самостоятельный bounded Enforcer корневого IPv4 forwarding state Private network. Его
verified DISABLED state используется как structural safety barrier, но тот же contract нужен
startup, shutdown и recovery независимо от `NetworkPolicyAdapter`.

API

    @observe(∅) — получить свежий authoritative gate state.
    @converge(...) — observe, при необходимости выполнить mutation и свежим reread подтвердить requested state.

Architectural decisions

1. `Owned state`
   *Gate управляет IPv4 forwarding state внутри Private network. Это не host-global forwarding state и не право изменять ordinary host namespace.*

2. `Verified state change`
   *Один converge-вызов выполняет fresh observe -> optional mutation -> fresh observe. Lower write result не является подтверждением. Даже failed write может завершиться success только если независимое финальное observation уже доказывает exact desired state.*

3. `Barrier postcondition`
   *Для structural mutation достаточным barrier является только freshly observed `DISABLED`. Невозможность наблюдать или подтвердить это состояние не разрешает начинать/продолжать allowing structural rebuild.*

4. `Scope of protection`
   *`DISABLED` блокирует routed IPv4 forwarding во всем Private network и поэтому может временно затронуть Profiles, чья policy не менялась. Он не блокирует local INPUT/OUTPUT traffic; соответствующие local owner classes требуют собственных safety contracts.*

5. `Mechanism independence`
   *Gate находится ниже пользовательской configuration/policy и не зависит от Profile direction, NAT/firewall grammar или текущего resource allocation. Глобальный forwarding primitive выбран в том числе потому, что остается применимым, когда nft ownership или routing/path realization еще не доверены.*

6. `Bounded lifecycle`
   *Enforcer не содержит hidden retry loop и не владеет continuous maintenance. Повторная попытка, если она нужна, начинается caller'ом из нового fresh state.*

### ForwardingGateDriver

Технический Driver к managed-domain forwarding state. В дереве `Residents` он является
child `ForwardingGate`, но его spec остается плоским addendum-соседом остальных компонентов
Space.

API

    observe_forwarding_gate(∅) — вернуть свежий technical gate state.
    set_forwarding_gate(...) — выполнить одну lower mutation attempt без implied confirmation.

Architectural decisions

1. `Technical boundary`
   *Driver предоставляет только fresh observation и одну mutation attempt. Он не выбирает desired state, не подтверждает Enforcer postcondition и не владеет retry/reconciliation.*

2. `Linux realization`
   *Текущая Linux-реализация читает/изменяет managed-network-namespace `net.ipv4.ip_forward`; process/command success остается техническим результатом и не заменяет fresh observation.*
