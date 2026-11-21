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
2. `Ordinary-side transition` *Прозрачный L3-переход между `Private network` и ordinary host-side сетевой средой; отдельный заменяемый «тамбур», основная собственная семантика которого состоит в lifecycle/materialization границы.*
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

### 2.6. Структурная согласованность

Для каждого Space должны механически выполняться следующие правила:

1. каждый distinct resident, показанный в дереве `Residents`, имеет component spec в
   `Component addenda` этого Space;
2. каждый component spec в addendum соответствует resident'у из дерева этого Space;
3. parent-child relation существует только в дереве `Residents` и не выводится из порядка
   или heading depth specs;
4. каждый `@Resident` имеет хотя бы одну непосредственно востребованную извне точку API,
   отмеченную `@` в его component spec;
5. каждая строка Space `API` разрешается в конкретную `@`-точку API resident'а из
   `Residents`;
6. internal method без `@` не должен появляться как Space API только потому, что его parent
   экспортирует другой метод;
7. marker `@` относится к occurrence/API относительно данного Space и не является частью
   canonical component name в addendum heading;
8. каждый Artifact, на который ссылается interaction или component spec, объявлен в
   `Artifacts` текущего Space либо явно является boundary target другого Space;
9. каждая нижняя техническая связь Driver/Reader/Executor заканчивается на объявленном
   Artifact либо на явной Space boundary;
10. `Interactions` и `Component diagram` представляют один и тот же граф; при
    расхождении `Interactions` является источником истины.

Нарушение этих правил считается структурным finding документа даже тогда, когда underlying
implementation технически работает.

### 2.7. Artifacts

Artifact — объект, состояние или доступная способность реальности, находящаяся внутри
Space и представляющая самостоятельный предмет observation, management и/или использования
resident'ами. Artifact не является компонентом: Driver/Reader/Executor может наблюдать,
изменять или использовать Artifact, но от этого Artifact не получает component API и не
становится resident'ом.

При **прямом проектировании** Artifact inventory выводится из той реальности Space,
которую необходимо наблюдать, изменять или использовать для реализации требований. На
практике эту потребность удобно выявлять через проектирование responsibilities/engines с
абстрактными lower contracts: предметы этих contracts становятся кандидатами в Artifacts
до выбора concrete backend и наполнения его деталями реальной среды.

При **reverse-engineering** уже существующей архитектуры направление инвертируется:
фактические Reader/Driver/Executor contracts используются как основной источник для
восстановления того, какие Artifacts реализация действительно наблюдает, изменяет или
использует. Полученный список затем проверяется на архитектурную самостоятельность и
очищается от случайных implementation details.

В обоих проходах предметное знание о том, «что вообще существует в сети/Linux», само по
себе не создает Artifact. Обратное тоже верно: локальная capability, через которую resident
реально взаимодействует с boundary (например IP portal), может быть Artifact даже без
отдельного management API, если именно на ней заканчивается осмысленная local-side
interaction.

Space не следует отождествлять с конкретным техническим контейнером его текущей реализации.
Например Linux network namespace может быть одним из Artifacts, материализующих
`Private network`, но сам Space является архитектурной областью и не исчезает из модели,
когда этот Artifact еще не создан или уже удален. Lifecycle machinery в таком случае
создает, проверяет, приводит к требуемому состоянию или удаляет materialization Artifacts,
а не «создает/уничтожает Space» как архитектурное понятие.

Раздел `Artifacts` перечисляет самостоятельные объекты реальности Space. Для каждого
Artifact следует указывать характер доступа там, где он полезен для чтения:

- `observed` — VPN-GATE только наблюдает объект;
- `managed` — VPN-GATE изменяет объект;
- `observed, managed` — VPN-GATE и наблюдает, и изменяет его.

Физическое расположение объекта в Linux, файле, namespace, nft table или другом контейнере
само по себе не определяет artifact hierarchy.

### 2.7.1. Иерархия Artifacts

Artifact следует показывать child'ом другого Artifact только тогда, когда это отражает
архитектурную семантику observation/management, а не физическую вложенность реализации.

Parent-child relation оправдана, если lower Artifacts совместно образуют один управляемый
объект/способность либо их lifecycle, invariants или проверяемый postcondition **конститутивно**
определяются контрактом parent Artifact. Несколько разных Drivers могут при этом управлять
разными lower частями одного parent Artifact.

Самой зависимости недостаточно. Если higher capability лишь требует другого самостоятельного
Artifact как prerequisite/reference, но не определяет его identity/lifecycle/ownership как
свою часть, такой Artifact остается sibling, а зависимость показывается в `Interactions`.
Иначе artifact tree превращается в dependency graph.

И наоборот, нахождение нескольких объектов внутри одного Linux namespace, nft table,
процесса или другого implementation container не делает их автоматически parent/child.
Если их можно независимо наблюдать и/или управлять ими через самостоятельные контракты,
они остаются соседними Artifacts. Границы Backend/Driver/Executor также не определяют
artifact hierarchy: несколько engines могут работать с разными проекциями одного Artifact,
а один composite engine может технически обслуживать несколько самостоятельных Artifacts.

Например один функциональный Artifact может состоять из нескольких independently
materialized частей:

```text
return-affinity state
    ├── nft flow-association state
    └── RPDB mark-dispatch state
```

Иерархия здесь выражает общий управляемый postcondition, а не тот факт, где именно Linux
хранит каждую часть.

### 2.7.2. Artifact и граница Space

Нижняя техническая связь компонента должна заканчиваться на том Artifact, который компонент
фактически наблюдает, использует или изменяет, либо на явной границе с другим Space.

Не следует придумывать локальный Artifact только для того, чтобы визуально завершить
стрелку к чужой среде. Но и удаленная предметная цель не становится Artifact текущего Space,
если компонент взаимодействует с ней через уже настроенную локальную транспортную
способность.

Для active probe это различие выглядит так:

```text
Private network
    ActiveProbeDriver
        -> VPN-side IP portal
             -> boundary interaction
                  -> VPN external ends.@vpn-interface endpoint
```

Driver отправляет и принимает IP из `Private network` через `VPN-side IP portal`;
VPN-interface endpoint является server-side API соседнего Space. Сам факт, что пакет в итоге проверяет удаленную
доступность, не переносит Driver или remote target в `Private network`.

### 2.7.3. Transition Space и прозрачная граница

Transition Space («тамбур») определяется не физическим местом его текущей реализации, а
контрактом перехода между двумя соседними средами. Его artifacts могут физически находиться
по разные стороны Linux namespace/process/device boundary и от этого не становятся artifacts
соседних Spaces.

«Дверь» перехода остается частью transition Space даже тогда, когда ее concrete endpoint
физически расположен внутри соседней среды. Для соседнего Space штатно установленный
transition может быть прозрачен: local portal воспринимается как прямая граница с дальней
средой, а внутренняя machinery тамбура раскрывается только при рассмотрении самого
transition Space.

Transition Space может быть lifecycle-dominant: основная самостоятельная семантика состоит
в observation/materialization/removal exact перехода, тогда как established steady state
почти не требует собственного data-plane management. Пока отдельный gate не является
реальным independently managed contract, состояние `established` включает пригодность
перехода для требуемого handoff; будущие `open/closed` режимы не следует добавлять
предвосхищением возможной реализации.

При разборе implementation, который одним lifecycle transaction пересекает несколько
Spaces, transaction boundary не переносится автоматически в artifact ownership. Каждый
наблюдаемый/изменяемый факт раскладывается по тому Space, чей контракт обязан сохранять
его при замене реализации перехода.

### 2.8. Interactions и Component diagram

Раздел `Interactions` является первичным проверяемым представлением графа текущего Space.
Он должен позволять восстановить, кто с кем взаимодействует и на каком resident/API/Artifact
заканчивается связь. Конкретная табличная раскладка может уточняться, но каждая строка должна
однозначно задавать source, interaction и target.

При structural review должны выполняться как минимум следующие правила:

1. каждый resident, участвующий в поведении Space, появляется в interaction graph;
2. каждый внешний `@`-вход соответствует boundary interaction с другим Space;
3. нижняя техническая связь Driver/Reader/Executor заканчивается либо на объявленном
   Artifact текущего Space, либо на явной границе с соседним Space;
4. interaction не ссылается на неизвестный resident, Artifact или Space;
5. Space API соответствует boundary edges interaction graph.

`Component diagram` является производной визуализацией того же графа и располагается
последним в описании Space. Соседние Spaces на диаграмме показываются black boxes: диаграмма
раскрывает внутренность только текущего Space.

При изменении архитектуры первично изменяется `Interactions`; diagram затем
перерисовывается/регенерируется из той же структуры. Несовпадение таблицы и diagram является
ошибкой документации; до исправления нормативным считается `Interactions`.

### 2.9. Размещение component specs

В целевой форме документа сначала описываются все Spaces: их границы, API, `Residents`,
`Artifacts`, `Interactions` и `Component diagram`. Подробные component specs
располагаются после карты Spaces как Annexes, а не вставляются между описаниями Spaces.

Каждому Space соответствует стабильная буква Annex. Заголовок не дублирует слово `Space`:

```text
# Annex C. Private network components

## C.001 NetworkPolicyAdapter
## C.002 NetworkPolicyEnforcer
...
```

Annex содержит плоский набор specs. Component hierarchy задается только деревом
`Residents` соответствующего Space и не кодируется ни порядком specs, ни глубиной
заголовков.

Буква Annex принадлежит Space. Если компонент архитектурно переезжает в другой Space,
меняется и его адрес в structured document. Для `<partial>` каждый Space содержит
собственный local spec соответствующей occurrence; скрытого общего spec поверх Spaces нет.

Для крупного проекта Annex может быть вынесен в отдельный документ без изменения этой
адресации и семантики.

Пока structured migration не завершена, уже перенесенные inline-блоки
`Component addenda` допускаются как временная форма. Их наличие не отменяет целевое
правило и не делает inline placement частью архитектурной семантики.

## 3. Форма описания Space

Каждый Space оформляется отдельным разделом.

Минимальная форма:

```text
# <Space>

<краткое описание назначения и границы>

API
    @Resident.method(...)
    @Resident.<interaction point>

Residents
    1. `@ResidentA` *краткое описание*
    2. `ResidentB` *краткое описание*

Artifacts
    - `Artifact A` — observed, managed
    - `Artifact B` — observed

Interactions

| From | Interaction | To |
| --- | --- | --- |
| ... | ... | ... |

Component diagram

<derived diagram>
```

`Residents`, `Artifacts` и `Interactions` обязательны для законченного Space.
`Component diagram` располагается последним и является производной визуализацией
`Interactions`.

Раздел `API` может быть опущен, если краткое описание Space уже однозначно отсылает к API
помеченных `@` resident'ов и отдельный список ничего не добавляет.

## 4. Component Annexes

Целевая структура component specs задана в §2.9: specs всех Spaces собираются после
описаний Spaces в Annexes и остаются плоскими относительно `Residents`.

Каждый resident получает отдельный Space-local spec с описанием ответственности, API,
requirement traceability, архитектурных решений и при необходимости unresolved
`Findings`. `@` получают только те точки component API, которые непосредственно входят
в API соответствующего Space.

`Architectural decisions` содержит только принятые решения, которые в текущей structured
decomposition действительно принадлежат этому component spec. Перенос решения из
`design/NG3/architecture.md` сам по себе не меняет его semantics, requirement traceability
или evidence.

`Findings` является ненормативным блоком обнаруженных проблем decomposition/placement/
ownership. После разрешения finding принятый результат переносится в правильный Space,
resident/artifact/interaction или component spec; активный structured document не должен
выдавать finding за принятое решение.

Ниже пока сохранен существующий inline `Component addenda` для `Private network` как
миграционное состояние до отдельного structural pass.



# Ordinary-side transition

Прозрачный L3-переход между `Private network` и ordinary host-side сетевой средой.
Transition владеет «дверью», но не traffic-selection policy соседних Spaces. После успешного
establishment он не должен добавлять самостоятельную data-plane semantics: для
`Private network` открытый переход наблюдается как прямая host boundary, а для host-side
среды — как explicit managed L3 endpoint.

Текущая Release-1 realization — routed veth + Proxy ARP. Конкретный link type является
backend detail: архитектурный контракт перехода допускает другую lower realization без
изменения Device/Profile semantics или соседних Spaces.

API

    @ManagedNetworkDomainLifecycle.observe_transition(...) — получить fresh exact/absent/conflict projection текущей boundary realization.
    @ManagedNetworkDomainLifecycle.establish_transition(...) — материализовать отсутствующий transition и подтвердить exact usable postcondition.
    @ManagedNetworkDomainLifecycle.remove_transition(...) — удалить owned transition realization и подтвердить отсутствие.

Отдельного `open/closed` API сейчас нет. `established` означает, что требуемый L3 handoff
уже пригоден для передачи IP. Возможный будущий gate для aggressive helper не проектируется
до появления отдельного принятого контракта.

Residents

1. `@ManagedNetworkDomainLifecycle <partial>` *Текущая lifecycle machinery, transition-проекция которой наблюдает, устанавливает и удаляет managed L3 boundary realization. Та же technical identity сейчас также обслуживает materialization `Private network`, поэтому marker является decomposition finding.*

Artifacts

1. `managed L3 boundary realization` *(observed, managed)* — целостная установленная ordinary-side L3 «дверь». Current exact postcondition включает обе стороны selected boundary backend, их operational/backend invariants и host-side reachability contribution, необходимую самой границе. Конкретные veth peer identities, Proxy ARP, `rp_filter` и другие backend-specific детали не поднимаются в самостоятельные Artifacts, пока ими не требуется независимо управлять.

Состояния Artifact на этом уровне:

```text
absent
established
conflict
```

`established` включает exact backend invariants и usable bidirectional IP handoff.
`conflict` означает, что наблюдаемая reality не может быть безопасно принята как owned
exact realization. Текущий lifecycle не обязан ремонтировать произвольную partial realization
in place.

Не принадлежат этому Space:

- stack-local IPv4 identity — собственная identity `Private network`;
- private-side default routing decision toward ordinary side — routing state `Private network`;
- remote Profile destination/SNAT routing selection на host — `Helper-managed host` либо
  administrator-owned host state;
- host-global forwarding/firewall/NAT — ordinary host ownership, если отдельный helper
  contract явно не принимает конкретную часть этого state.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `STACK` | lifecycle `observe / establish / remove` | `@ManagedNetworkDomainLifecycle <partial>` |
| `@ManagedNetworkDomainLifecycle <partial>` | observe/materialize/remove exact boundary state | `managed L3 boundary realization` |
| `Private network.ordinary-side IP portal` | bidirectional IP handoff | `managed L3 boundary realization` |
| `managed L3 boundary realization` | bidirectional IP handoff | `Ambient host and external world` |
| `Helper-managed host` | routes selected host traffic toward the explicit managed host endpoint | `managed L3 boundary realization` |

Finding: current `ManagedNetworkDomain` lifecycle transaction crosses the
`Private network` / `Ordinary-side transition` boundary. Its existing preflight therefore
treats `namespace present XOR host boundary present` as one structural failure although
the decomposed architecture admits an independently present Private network materialization
with absent transition. This is a concrete candidate for later architecture/code
decomposition, not a reason to merge the Spaces.

Component diagram

```text
+---------------------+
|        STACK        |
+----------+----------+
           |
           | lifecycle
           v
+----------+--------------------------------------------------+
| Ordinary-side transition                                   |
|                                                             |
| @ManagedNetworkDomainLifecycle <partial>                    |
|           |                                                 |
|           | observe / establish / remove                    |
|           v                                                 |
| [ managed L3 boundary realization ]                         |
|          ^                         ^                        |
+----------|-------------------------|------------------------+
           | bidirectional IP        | selected host traffic /
           | handoff                 | host-side IP handoff
           |                         |
+----------+----------+    +---------+------------------------+
|   Private network   |    | Helper-managed / ambient host    |
| ordinary-side       |    |                                 |
| IP portal           |    |                                 |
+---------------------+    +----------------------------------+
```


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

Artifacts

1. `managed network environment realization` *(observed, managed)* — текущая Linux-materialization сетевой среды, которой lifecycle machinery управляет через один exact/absent contract; этот Artifact не является самим Space `Private network`.
    1. `network namespace instance` *(observed, managed)* — экземпляр Linux network namespace, наличие которого lifecycle machinery наблюдает, создаёт и удаляет.
    2. `loopback operational state` *(observed, managed)* — требуемое lifecycle-инвариантом состояние namespace loopback; самостоятельно верхними клиентами не управляется.
2. `ordinary-side IP portal` *(observed, managed; decomposition pending)* — обращённая к ordinary-side transition локальная способность `Private network` принимать и отдавать IP-трафик. Текущая Linux-realization и её точная artifact decomposition разбираются отдельно.

Текущий `ManagedNetworkDomain` lifecycle технически проверяет единым postcondition не только
namespace/loopback, но и private-side boundary facts вместе с соответствующими host-side
peer/sysctl/route facts. Эта implementation transaction boundary сама по себе не задаёт
artifact hierarchy и не переносит host-side объекты внутрь `Private network`.

Для существующей lifecycle machinery допустимы целостные состояния `absent` и `exact`.
Частично присутствующая materialization считается ошибкой preflight; текущий `ensure`
не трактует её как набор независимо ремонтируемых child Artifacts. `destroy` удаляет
текущую Linux-materialization, а не архитектурный Space.

Finding: lower composition и Space-boundary contract `ordinary-side IP portal` требуют
отдельного pass по transition Space. До него managed-side interface, stack-local IPv4
identity, endpoint sysctls, private-side default route и host-side peer/route не объявляются
здесь автоматически отдельными child Artifacts только из-за текущей Linux-realization.

Residents

1. `@NetworkPolicyAdapter` *Semantic boundary между policy клиентов из STACK и ее lower realization/convergence внутри Private network.*
    1. `NetworkPolicyLayoutCalculator` *Детерминированно распределяет внутренние routing/RPDB/metric/nft resources между semantic owner scopes.*
    2. `NetworkPolicyEnforcer` *Достигает и подтверждает переданный Adapter'ом desired lower network-policy state.*
2. `@VPNPathAdapter` *Boundary наблюдения и проверки concrete VPN endpoints, уже присутствующих в Private network.*
3. `@ForwardingGate` *Самостоятельный verified control корневого IPv4 forwarding barrier; нужен как network-policy convergence, так и lifecycle/safety клиентам.*
    1. `ForwardingGateDriver` *Технический read/mutation boundary к managed-domain forwarding state.*

## Component addenda

### NetworkPolicyAdapter

Adapter является shared boundary от owner-scoped semantic network policy клиентов STACK к
lower network-policy domain Private network. Общая physical realization не сливает
различные semantic owners.

**Implements:**
- `VPNG0001-R1.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0005-R5.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R2`
- `VPNG0007-R7.R5`

API

    @observe_owned_policy(...) — наблюдать текущее owned policy state.
    @apply(...) — применить desired semantic policy и подтвердить postcondition.
    @cleanup(...) — удалить owned policy и подтвердить отсутствие.

Architectural decisions

1. `Semantic boundary`
   *Upper callers передают semantic policy, а не Linux realization. Route tables, RPDB priorities, protocol markers, gateway/onlink representation, nft/sysctl syntax, command ordering и transaction scratch state остаются ниже Adapter.*

2. `Owner preservation`
   *Payload policy, probe policy и другие semantic owner scopes остаются различимыми при allocation, observation, mutation и cleanup даже при общей physical machinery.*

3. `Realization composition`
   *Для lower policy Adapter соединяет semantic Profile/path intent, current verified path/integration facts и internal owned-resource layout. Ни один из этих lower фактов не добавляется в human configuration только потому, что он нужен Linux.*

4. `Fail-closed incomplete realization`
   *Missing/ambiguous gateway, onlink или другой required physical fact нельзя угадывать из ambient routing либо молча выбрасывать. Зависимый lower policy остается unconfirmed/restrictive, пока достаточная realization не будет доказана.*

5. `Internal resource allocation`
   *Numeric/internal resource layout выбирается ниже semantic boundary. `NetworkPolicyLayoutCalculator` строит layout из semantic owner demand и injected platform space; route-priority realization types являются consumers этого layout, а не authority его глобального выбора.*

6. `Convergence delegation`
   *`NetworkPolicyEnforcer` получает уже выбранный desired lower state/postcondition и отвечает за его достижение/verification. Он не выбирает semantic policy и не расширяет API Space вокруг Adapter.*

Findings

1. `Host-side publication placement` *Flat architecture также приписывает этому Adapter host-side Device publication mapping. Его server находится вне Private network; сохранение того же technical component через несколько Spaces потребовало бы `<partial>`. Окончательное расселение откладывается до structured pass по host/transition Spaces.*

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

Findings

1. `Administrative payload containment` *Future public containment capability по `VPNG0004-R5` не является режимом structural Enforcer. Ее exact lower composition остается open; текущий `ForwardingGate` может быть только частью решения, потому что отдельный ordinary-side block тоже необходим.*

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

Findings

1. `Route realization ownership` *Flat architecture требует integration-specific verified gateway/onlink realization в дополнение к current binding, но structured tree пока не доказывает, является ли это методом VPNPathAdapter, отдельным child component или контрактом другого transition/VPN-end Space.*

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
