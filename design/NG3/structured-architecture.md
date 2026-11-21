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
5. `VPN-GATE-managed host state` *Явно owned часть ordinary-host network state: core host-publication mapping и отдельно включаемые host-side helper contributions. Остальной host остается соседним ambient Space.*
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

Для **внешнего** Space `Resident` может быть external actor/system/capability provider,
который не является компонентом VPN-GATE и поэтому не классифицируется как
Engine/Machinery по `design/component-model.md`. На него по-прежнему распространяются
Space/API/Interaction rules, но отдельный VPN-GATE component addendum не требуется, если
его внешний контракт уже достаточно описан в самом Space. Component roles и обязательные
component specs относятся к resident'ам, являющимся архитектурными компонентами VPN-GATE.

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

API Space — объединение внешне востребованных interaction points, предоставляемых:

1. API его resident'ов; и
2. явно объявленными boundary-capability Artifacts для пассивного/data-plane handoff, где
   отдельного обслуживающего component resident по смыслу нет.

Самостоятельного «магического» API поверх resident'ов/Artifacts у Space нет. Пассивный
Artifact interaction point не превращает Artifact в component: он лишь фиксирует реальную
capability Space, на которой заканчивается boundary interaction.

Для active/service interaction API принадлежит тому Space, внутри которого находится
обслуживающая сторона — server. Интерфейс является API Space только тогда, когда его client
находится вне этого Space.

Для bidirectional/passive data-plane boundary, где понятие server неприменимо или ничего не
добавляет, interaction point принадлежит Space явного boundary Artifact, реализующего эту
capability. Physical placement concrete endpoint само по себе ownership не меняет.

Если все стороны взаимодействия находятся внутри одного Space, это внутренний контракт, а не
API Space.

Асинхронность active/service правило не меняет. В конкретной точке взаимодействия существует
server-side broker/queue/API и его client; размещение обслуживающей стороны определяет
принадлежность этого API.

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

Если точка предоставляется boundary-capability Artifact, `@` в API-списке отмечает именно
его interaction point и не делает Artifact resident'ом/компонентом.

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

Каждый resident, являющийся компонентом VPN-GATE, получает отдельный Space-local spec с описанием ответственности, API,
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

Ниже существующие specs `Private network` уже собраны в `Annex C`. Annex пока неполон:
новые resident'ы, выявленные текущим Space-pass, получают свои specs в следующем
component-annex review unit; это не меняет завершенность самой карты Spaces.



# STACK

Внутренняя control-plane среда VPN-GATE. Здесь живут semantic Engines и Machinery,
которые принимают/нормализуют intent, поддерживают текущую payload-policy проекцию,
планируют наблюдение availability, оркестрируют bounded lifecycle и собирают truthful
runtime status. STACK не является data-plane network namespace: воздействие на сетевую
реальность выполняется через API соседних Spaces.

API

    @ProductLifecycleControl.start(...) — выполнить bounded startup и сообщить success только после требуемых readiness/safety postconditions.
    @ProductLifecycleControl.stop(...) — выполнить bounded containment/cleanup и сообщить success только после требуемых cleanup postconditions.
    @ProductLifecycleControl.restart(...) — скомпозировать stop + новый start из authoritative state.
    @ProductLifecycleControl.reload(...) — optional supported operation; отсутствует в текущей alpha и не подменяется скрытым restart.
    @ConfigurationAdapter.normalize(...) — принять внешнее configuration representation и вернуть validated normalized domain intents.
    @RuntimeStatusAgent.<current snapshot publication> — предоставить текущую user-facing status projection; concrete presentation/API surface пока заменяем.

Residents

1. `@ProductLifecycleControl` *Direct procedural Machinery product lifecycle; не является Engine и не вводит самостоятельную lifecycle policy/state machine.*
2. `@ConfigurationAdapter` *Direct boundary от external configuration representation к validated normalized domain intents.*
    1. `AvailabilityDescriptionResolver` *Pure Calculator, разрешающий Profile/Device availability description без runtime topology inference.*
3. `PayloadTrafficManager` *Manager текущей semantic payload-policy среды: structural intent, binding projection, availability confirmation и effective path order.*
    1. `PayloadPolicyCalculator` *Pure Calculator structural payload policy из normalized intent и уже подтвержденных внешних фактов.*
    2. `AvailabilityPriorityCalculator` *Pure Calculator effective path order из current membership, availability problem state, active path и reserve semantics.*
4. `AvailabilityProbeAgent` *Agent ongoing availability observation; планирует bounded checks и публикует normalized evidence, но не управляет наблюдаемой внешней доступностью.*
5. `@RuntimeStatusAgent` *Agent current-only status composition из authoritative owner snapshots; не актуирует наблюдаемые domains.*

Artifacts

1. `accepted normalized intent` *(observed, managed)* — текущие validated Device/Profile/availability/helper intents, от которых разрешено строить dependent desired state. Это не глобальный mutable config object и не копия external file syntax.
2. `payload semantic state` *(observed, managed)* — текущая owner projection `PayloadTrafficManager`.
    1. `structural payload intent` *(observed, managed)*
    2. `Device binding projection` *(observed, managed)* — bounded current logical binding state, а не endpoint inventory.
    3. `availability confirmation state` *(observed, managed)*
    4. `effective path-order state` *(observed, managed)* — current active path/effective order; не per-flow affinity.
3. `availability observation context` *(observed, managed)* — current requested subjects, cadence, bounded in-flight identities/generation tokens и diagnostics `AvailabilityProbeAgent`.
4. `controller ownership/readiness session` *(observed, managed)* — bounded procedural lifecycle state, включая retained single-controller ownership и текущий READY/cleanup result. Его наличие не превращает lifecycle в Engine.
5. `runtime status snapshot` *(observed, managed)* — current-only composition authoritative snapshots; не event history и не system-of-record.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `Operator.OperatorClient` / deployment control | `start / stop / restart / optional reload` | `@ProductLifecycleControl` |
| `@ProductLifecycleControl` | acquire/release single-controller ownership and maintain bounded session | `controller ownership/readiness session` |
| `Ambient host and external world.@ExternalConfigurationSource` | candidate configuration representation | `@ConfigurationAdapter` |
| `@ConfigurationAdapter` | resolve normalized availability descriptions | `AvailabilityDescriptionResolver` |
| `@ConfigurationAdapter` | accepted normalized domain intents | `accepted normalized intent` |
| `@ProductLifecycleControl` | validate/load candidate intent before dependent mutation | `@ConfigurationAdapter` |
| `@ProductLifecycleControl` | preflight/ensure/destroy managed data-plane environment | `Private network.@ManagedNetworkDomainLifecycle <partial>` |
| `@ProductLifecycleControl` | establish/remove ordinary-side managed boundary through the same current lifecycle transaction | `Ordinary-side transition.@ManagedNetworkDomainLifecycle <partial>` |
| `@ProductLifecycleControl` | converge/cleanup enabled host-side contribution | `VPN-GATE-managed host state.@HostRoutingContribution` |
| `@ProductLifecycleControl` | activate/cleanup desired lower network policy | `Private network.@NetworkPolicyAdapter` |
| `accepted normalized intent` | current structural inputs | `PayloadTrafficManager` |
| `PayloadTrafficManager` | calculate structural semantic projection | `PayloadPolicyCalculator` |
| `PayloadTrafficManager` | calculate effective availability-dependent ordering | `AvailabilityPriorityCalculator` |
| `PayloadTrafficManager` | observe/verify current endpoint bindings | `Private network.@VPNPathAdapter` |
| `PayloadTrafficManager` | apply/reconcile current desired lower policy | `Private network.@NetworkPolicyAdapter` |
| `PayloadTrafficManager` | own/update current semantic state | `payload semantic state` |
| `accepted normalized intent` / current bindings | synchronize requested observation subjects | `AvailabilityProbeAgent` |
| `AvailabilityProbeAgent` | own current check schedule/context | `availability observation context` |
| `AvailabilityProbeAgent` | execute one physical check | `Private network.@ActiveProbeDriver` |
| `AvailabilityProbeAgent` | `AvailabilityEvidence` InfoEvent | `PayloadTrafficManager` |
| `PayloadTrafficManager` | current payload projection InfoEvent | `@RuntimeStatusAgent` |
| `AvailabilityProbeAgent` | current observation/diagnostic InfoEvent | `@RuntimeStatusAgent` |
| `@ProductLifecycleControl` | lifecycle/readiness/cleanup projection | `@RuntimeStatusAgent` |
| `@RuntimeStatusAgent` | compose/update | `runtime status snapshot` |
| `@RuntimeStatusAgent` | current snapshot publication | `Operator.OperatorClient` / presentation environment |

Findings

1. `Status presentation boundary` — architecture intentionally leaves CLI/API/text/file
   presentation replaceable. Current alpha writes `status.json`, but that file path/format is
   not yet a stable product API; structured model therefore terminates on semantic current
   snapshot publication rather than blessing the alpha mechanism.
2. `Lifecycle decomposition` — current procedural startup directly composes lower lifecycle,
   host contribution and policy activation. No accepted need justifies a `LifecycleManager`;
   decomposition should happen only where lower Space boundaries now expose independent
   Machinery contracts.

Component diagram

```text
+-------------------------- Operator / deployment --------------------------+
             | lifecycle control                         ^ status
             v                                           |
+------------+-------------------------------------------------------------+
|                                  STACK                                   |
|                                                                          |
| @ProductLifecycleControl ----------------------------+                   |
|       |                |               |             |                   |
|       |                |               |             v                   |
|       |                |               |      @RuntimeStatusAgent        |
|       |                |               |             ^                   |
|       v                |               |             | InfoEvents        |
| @ConfigurationAdapter  |               |      +------+---------+         |
|       |                |               |      |                |         |
|       v                |               | PayloadTrafficManager |         |
| AvailabilityDescriptionResolver       |      ^                |         |
|       |                                |      | evidence       |         |
| [accepted normalized intent] ----------+----> |                |         |
|                                              |                |         |
|                                     AvailabilityProbeAgent ----+         |
|                                              |                           |
|                 +----------------------------+------------------+        |
|                 |                                               |        |
+-----------------|-----------------------------------------------|--------+
                  |                                               |
       lower policy/lifecycle                              physical probe
                  |                                               |
        +---------v-------------------+             +-------------v---------+
        | Private network / transition|             | Private network       |
        +-----------------------------+             +-----------------------+
                  |
                  +--------------------------> VPN-GATE-managed host state
```


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

    @ManagedNetworkDomainLifecycle <partial>.preflight_managed_network_domain(...) — read-only проверить существующую combined domain/boundary realization; transition-проекция результата подтверждает exact/absent либо conflict.
    @ManagedNetworkDomainLifecycle <partial>.ensure_managed_network_domain(...) — создать отсутствующую combined realization либо подтвердить существующую; transition-проекция success означает established usable boundary.
    @ManagedNetworkDomainLifecycle <partial>.destroy_managed_network_domain(...) — удалить owned combined realization; transition-проекция success подтверждает отсутствие boundary.
    @managed L3 boundary realization.<private-side IP handoff> — passive bidirectional handoff к Private network.
    @managed L3 boundary realization.<host-side IP handoff> — passive bidirectional handoff к ordinary host network.

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
- remote Profile destination/SNAT routing selection на host — `VPN-GATE-managed host state` либо
  administrator-owned host state;
- host-global forwarding/firewall/NAT — ordinary host ownership, если отдельный helper
  contract явно не принимает конкретную часть этого state.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `STACK.@ProductLifecycleControl` | lifecycle `observe / establish / remove` | `@ManagedNetworkDomainLifecycle <partial>` |
| `@ManagedNetworkDomainLifecycle <partial>` | observe/materialize/remove exact boundary state | `managed L3 boundary realization` |
| `Private network.@ordinary-side IP portal.<IP handoff>` | bidirectional IP handoff | `@managed L3 boundary realization.<private-side IP handoff>` |
| `@managed L3 boundary realization.<host-side IP handoff>` | bidirectional IP handoff | `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` |
| `VPN-GATE-managed host state` | routes selected host traffic toward the explicit managed host endpoint | `managed L3 boundary realization` |

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
Она содержит принадлежащее VPN-GATE сетевое состояние data plane и локальные capabilities,
через которые ordinary-side и VPN-side среды становятся достижимы. Linux network namespace
является текущей materialization этого Space, но не самим Space.

API

    @ManagedNetworkDomainLifecycle <partial>.preflight_managed_network_domain(...) — read-only проверить текущую materialization Private network как часть существующего combined lifecycle contract.
    @ManagedNetworkDomainLifecycle <partial>.ensure_managed_network_domain(...) — материализовать/подтвердить Private network как часть combined lifecycle contract.
    @ManagedNetworkDomainLifecycle <partial>.destroy_managed_network_domain(...) — удалить текущую Linux-materialization Private network как часть combined lifecycle contract.
    @NetworkPolicyAdapter.observe_owned_policy(...) — вернуть свежую owner-scoped проекцию управляемой network policy.
    @NetworkPolicyAdapter.apply(...) — применить semantic desired policy и подтвердить postcondition.
    @NetworkPolicyAdapter.cleanup(...) — удалить owned policy scope и подтвердить его отсутствие.
    @VPNPathAdapter.observe_device_endpoints(...) — наблюдать текущие candidate VPN endpoints в Private network.
    @VPNPathAdapter.verify_path_binding(...) — подтвердить однозначный current binding logical path к endpoint.
    @ActiveProbeDriver.execute(...) — выполнить один bounded probe через заранее подтвержденный current VPN-side execution context.
    @ForwardingGate.observe(∅) — вернуть свежий authoritative state корневого IPv4 forwarding gate.
    @ForwardingGate.converge(...) — установить требуемое состояние gate и подтвердить его свежим наблюдением.
    @ordinary-side IP portal.<IP handoff> — passive bidirectional ordinary-side data-plane handoff.
    @VPN-side IP portal.<IP handoff> — passive bidirectional VPN-side data-plane handoff.

Artifacts

1. `managed network environment realization` *(observed, managed)* — текущая Linux-materialization внутренней сетевой среды; не является самим Space.
    1. `network namespace instance` *(observed, managed)* — Linux network namespace instance.
    2. `loopback operational state` *(observed, managed)* — lifecycle invariant namespace loopback.
2. `stack-local IPv4 identity` *(observed, managed)* — собственная адресуемая service identity Private network. Она не является transit next-hop identity ordinary-side transition.
3. `ordinary-side default routing state` *(observed, managed)* — внутренняя routing decision, что ordinary-side IP достигается через текущую host boundary; current Linux realization — device-only default route.
4. `ordinary-side IP portal` — локальная capability передачи/приема IP через прозрачный `Ordinary-side transition`. Concrete endpoint двери принадлежит transition, даже когда физически расположен в managed namespace.
5. `VPN-side IP portal` — локальная capability отправки/приема IP через текущие VPN endpoints; не является конкретным path/interface/remote endpoint.
6. `VPN endpoint inventory` *(observed)* — fresh inventory concrete VPN endpoint generations внутри Private network, используемый для verified logical-path binding.
7. `IPv4 forwarding state` *(observed, managed)* — корневой forwarding barrier Private network.
8. `payload routing state` *(observed, managed)* — единый semantic lower state payload routing.
    1. `payload route state` *(observed, managed)*
    2. `payload RPDB state` *(observed, managed)*
9. `probe routing state` *(observed, managed)* — exact route+selector precondition path-specific probes.
    1. `probe route state` *(observed, managed)*
    2. `probe RPDB state` *(observed, managed)*
10. `nft policy scaffold` *(observed, managed)* — invariant owned nft table/base-chain structure, являющаяся prerequisite semantic policy owners, но не parent этих owners.
11. `Profile forwarding policy` *(observed, managed)*
12. `Device firewall policy` *(observed, managed)*
13. `payload NAT policy` *(observed, managed)*
14. `local publication policy` *(observed, managed)* — local INPUT/OUTPUT admission для Device publication внутри Private network.
15. `VPN integration local policy` *(observed, managed)* — bounded local transport admission, необходимая supported VPN integration.
16. `probe local admission policy` *(observed, managed)* — local policy, допускающая только exact probe execution/reply context.
17. `return-affinity state` *(observed, managed)* — общий postcondition association remote-initiated flow с исходным VPN routing domain.
    1. `return-affinity nft association/restore policy` *(observed, managed)*
    2. `return-affinity RPDB mark-dispatch state` *(observed, managed)*

`route-priority state` не является отдельным Artifact: priority machinery изменяет
свойства тех же `payload route state`. Аналогично readiness probe execution является
производным условием exact `probe routing state` + `probe local admission policy` +
current endpoint identity, а не самостоятельным `Probe IP transport` Artifact.

Residents

1. `@ManagedNetworkDomainLifecycle <partial>` *Private-network проекция текущей combined lifecycle machinery: materialization namespace/local identity/default routing; пересечение с ordinary-side transition остается decomposition finding.*
2. `@NetworkPolicyAdapter` *Semantic boundary между policy клиентов из STACK и lower realization/convergence внутри Private network.*
    1. `NetworkPolicyLayoutCalculator` *Детерминированно распределяет internal routing/RPDB/metric/nft resources между semantic owner scopes.*
    2. `NetworkPolicyEnforcer` *Достигает и подтверждает переданный Adapter'ом desired lower network-policy state.*
3. `@VPNPathAdapter` *Boundary fresh observation и verification concrete VPN endpoints уже присутствующих в Private network.*
4. `@ActiveProbeDriver` *Bounded lower execution одного активного probe через заранее подтвержденные probe-policy и endpoint facts.*
5. `@ForwardingGate` *Самостоятельный verified control корневого IPv4 forwarding barrier.*
    1. `ForwardingGateDriver` *Technical read/mutation boundary к managed-domain forwarding state.*

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `STACK.@ProductLifecycleControl` | lifecycle preflight / ensure / destroy | `@ManagedNetworkDomainLifecycle <partial>` |
| `@ManagedNetworkDomainLifecycle <partial>` | observe/materialize/remove namespace + loopback | `managed network environment realization` |
| `@ManagedNetworkDomainLifecycle <partial>` | observe/materialize/remove local service address | `stack-local IPv4 identity` |
| `@ManagedNetworkDomainLifecycle <partial>` | observe/materialize/remove ordinary-side default | `ordinary-side default routing state` |
| `@ManagedNetworkDomainLifecycle <partial>` | same current transaction also manages the door realization | `Ordinary-side transition.managed L3 boundary realization` |
| `Ordinary-side transition.@managed L3 boundary realization.<private-side IP handoff>` | bidirectional IP handoff | `@ordinary-side IP portal.<IP handoff>` |
| `STACK.PayloadTrafficManager` / `STACK.@ProductLifecycleControl` | semantic observe/apply/cleanup | `@NetworkPolicyAdapter` |
| `@NetworkPolicyAdapter` | allocate internal lower resources | `NetworkPolicyLayoutCalculator` |
| `@NetworkPolicyAdapter` | converge desired lower policy | `NetworkPolicyEnforcer` |
| `NetworkPolicyEnforcer` | converge/verify payload dispatch and path routes | `payload routing state` |
| `@NetworkPolicyAdapter` | converge/verify dedicated probe route/RPDB owner through lower probe-routing machinery | `probe routing state` |
| `@NetworkPolicyAdapter` | observe/prepare invariant activation prerequisite through lower scaffold machinery | `nft policy scaffold` |
| `NetworkPolicyEnforcer` | converge/verify semantic nft owners | `Profile forwarding policy`, `Device firewall policy`, `payload NAT policy`, `local publication policy`, `VPN integration local policy`, `probe local admission policy` |
| `@NetworkPolicyAdapter` | converge/verify independently owned established-flow return-affinity postcondition under the shared safety barrier | `return-affinity state` |
| `NetworkPolicyEnforcer` | structural safety barrier | `@ForwardingGate` |
| `STACK.PayloadTrafficManager` | fresh endpoint observation / binding verification | `@VPNPathAdapter` |
| `@VPNPathAdapter` | observe current concrete endpoint generations | `VPN endpoint inventory` |
| `VPN external ends.@VPNChannel[].<vpn-interface endpoint>` | presence/replacement/removal changes the freshly observed endpoint set | `VPN endpoint inventory` |
| `STACK.AvailabilityProbeAgent` | execute one confirmed physical probe attempt | `@ActiveProbeDriver` |
| `STACK.AvailabilityProbeAgent` | require confirmed probe execution precondition before invoking the Driver | `probe routing state`, `probe local admission policy`, `VPN endpoint inventory` |
| `@ActiveProbeDriver` | send/receive probe IP | `@VPN-side IP portal.<IP handoff>` |
| `@VPN-side IP portal.<IP handoff>` | bidirectional IP handoff | `VPN external ends.@VPNChannel[].<vpn-interface endpoint>` |
| `STACK.@ProductLifecycleControl` | lifecycle/preflight/stop containment | `@ForwardingGate` |
| `@ForwardingGate` | technical read/mutation | `ForwardingGateDriver` |
| `ForwardingGateDriver` | read/write | `IPv4 forwarding state` |

Finding: current `ManagedNetworkDomain` lifecycle still merges artifacts from this Space
with `Ordinary-side transition`. The structured ownership above intentionally does not
inherit that implementation transaction boundary.

Component diagram

```text
                     +----------------------+
                     |        STACK         |
                     +--+----+----+----+----+
                        |    |    |    |
             lifecycle  |    |    |    | probe execution
                        |    |    |    |
+-----------------------v----v----v----v-----------------------------+
|                         Private network                             |
|                                                                     |
| @ManagedNetworkDomainLifecycle <partial>                            |
|      |        |        |                                            |
|      v        v        v                                            |
| [environment] [stack-local /32] [ordinary default]                  |
|                                                                     |
| @NetworkPolicyAdapter --> NetworkPolicyLayoutCalculator             |
|          |                                                          |
|          +-------------> NetworkPolicyEnforcer ------+              |
|                         |    |    |    |             |              |
|                         v    v    v    v             v              |
|                      routing probe  nft owners   @ForwardingGate     |
|                                                   |                 |
|                                                   v                 |
|                                           ForwardingGateDriver       |
|                                                   |                 |
|                                                   v                 |
|                                          [IPv4 forwarding]          |
|                                                                     |
| @VPNPathAdapter ----------> [VPN endpoint inventory]                 |
|                                   ^                                 |
|                                   |                                 |
| @ActiveProbeDriver --------------+                                  |
|        |                                                            |
|        +--> [probe routing] / [probe local admission]                |
|        |                                                            |
|        v                                                            |
| [VPN-side IP portal]                                                |
|                                                                     |
| [ordinary-side IP portal]                                           |
+-----------^--------------------------------------------+-------------+
            |                                            |
            | IP                                         | IP
+-----------+------------+                    +----------v-----------+
| Ordinary-side transition|                    | VPN external ends    |
+--------------------------+                    +----------------------+
```

# VPN external ends

Внешняя по отношению к core VPN-GATE VPN-среда: administrator-provisioned VPN channels,
их protocol-specific runtime/session semantics и обращенные к `Private network`
data-plane endpoints. Physical placement не задает ownership: Release-1 OpenVPN process
может выполняться внутри managed network namespace, оставаясь resident'ом этого Space,
потому что VPN-specific configuration/session lifecycle принадлежат external integration.

API

    @VPNChannel[].<vpn-interface endpoint> — bidirectional IP endpoint текущей VPN channel generation, доступный `Private network`.
    @VPNChannel[].<transport provenance> — optional integration-proven transport endpoint fact; отсутствует, если supported integration не умеет доказать его без inference.

Residents

1. `@VPNChannel[]` *Administrator-provisioned VPN integration instance. В Release 1 supported OpenVPN/systemd shape использует отдельный stack-specific service, policy-neutral VPN configuration и создает current VPN data-plane endpoint внутри managed network domain.*

Artifacts

1. `VPN-specific configuration` — administrator-owned protocol configuration; VPN-GATE не переписывает и не превращает ее в Device/Profile policy.
2. `VPN channel runtime/session state` — external VPN implementation state, включая process/cgroup/session lifecycle. Для supported Release-1 service им управляет systemd, а не VPN-GATE process supervisor.
3. `VPN endpoint generation` *(observed by VPN-GATE)* — current concrete interface generation, которую channel предоставляет в `Private network`; identity включает фактическую interface generation и не наследуется same-name replacement автоматически.
4. `remote path availability property` *(observed)* — внешнее сетевое свойство, которое активные checks пытаются наблюдать относительно configured normalized criterion/target; VPN-GATE его не актуирует.
5. `transport endpoint provenance` *(optional, observed)* — доказанный integration-specific transport fact exact current channel generation; не выводится из interface name/peer/ambient routes.

`VPN endpoint inventory` не дублируется здесь: это локальная fresh observation projection
в `Private network`. Аналогично availability confirmation/hysteresis принадлежат STACK,
а не наблюдаемой внешней среде.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `Operator.OperatorClient` | provision VPN-specific configuration / stack-specific service integration | `@VPNChannel[]` |
| `Ambient host and external world.@systemd` | start/stop/restart explicitly bound supported VPN service/cgroup | `@VPNChannel[]` |
| `@VPNChannel[]` | maintain protocol-specific runtime/session | `VPN channel runtime/session state` |
| `@VPNChannel[]` | realize current concrete endpoint generation | `VPN endpoint generation` |
| `Private network.@VPNPathAdapter` | fresh observe / verify current endpoint identity | `@VPNChannel[].<vpn-interface endpoint>` |
| `Private network.@VPNPathAdapter` | optionally consume proven integration transport fact | `@VPNChannel[].<transport provenance>` |
| `@VPNChannel[].<vpn-interface endpoint>` | bidirectional tunneled IP handoff | `Private network.@VPN-side IP portal.<IP handoff>` |
| `@VPNChannel[]` | VPN underlay/control traffic admitted by bounded local owner | `Private network.VPN integration local policy` |
| `@VPNChannel[]` | VPN underlay IP exits/enters ordinary side | `Private network.@ordinary-side IP portal.<IP handoff>` |
| `STACK.AvailabilityProbeAgent` via `Private network.@ActiveProbeDriver` | configured active observation | `remote path availability property` |
| `Ambient host and external world.@systemd` | supported deployment stop removes bound process/cgroup and endpoint before managed-domain teardown | `VPN channel runtime/session state` / `VPN endpoint generation` |

Findings

1. `Physical placement is not Space ownership` — OpenVPN `MainPID` and `vpn0` can be
   physically inside the managed netns while VPN-specific lifecycle/configuration remains in
   this Space. `Private network` owns observation/binding and surrounding policy, not VPN
   session semantics.
2. `Additional integrations` — OpenVPN/systemd is the currently evidenced Release-1
   onboarding mechanism. Other technologies do not become supported merely because they can
   expose a superficially similar interface; each requires applicability evidence or reviewed
   equivalence.

Component diagram

```text
+---------------- Operator ----------------+    +------ Ambient host ------+
| VPN-specific provisioning               |    | systemd service control |
+----------------+-------------------------+    +------------+-------------+
                 |                                           |
                 v                                           v
+----------------+--------------------------------------------------------+
|                           VPN external ends                              |
|                                                                          |
| @VPNChannel[]                                                            |
|      |                                                                   |
|      +--> [VPN config / runtime-session state]                            |
|      +--> [remote availability property]                                 |
|      |                                                                   |
|      +---- @<vpn-interface endpoint> -------------------+                 |
+--------------------------------------------------------|-----------------+
                                                         | tunneled IP
                                                         v
+--------------------------------------------------------+-----------------+
|                          Private network                                 |
| @VPNPathAdapter -> [endpoint inventory]     [VPN-side IP portal]         |
| @ActiveProbeDriver -----------------------> configured observation       |
| [VPN integration local policy] + [ordinary-side IP portal] <- underlay   |
+--------------------------------------------------------------------------+
```



# VPN-GATE-managed host state

Явно owned часть ordinary-host network state. Этот Space существует потому, что VPN-GATE
имеет ограниченные host-side postconditions, которые нельзя ни прятать внутрь
`Private network`, ни смешивать с administrator-owned ambient host. В Release 1 здесь
сосуществуют два независимых owner scope: обязательная при запрошенной server publication
host mapping и optional peaceful host-routing contribution.

API

    @NetworkPolicyAdapter <partial>.observe_host_publication(...) — fresh observation отдельного host-publication owner scope.
    @NetworkPolicyAdapter <partial>.apply_host_publication(...) — converge desired host publication mappings и fresh verify.
    @NetworkPolicyAdapter <partial>.cleanup_host_publication(...) — удалить только owned host-publication objects и подтвердить отсутствие.
    @HostRoutingContribution.converge(∅) — установить complete lifecycle-scoped peaceful host-routing contribution.
    @HostRoutingContribution.cleanup(∅) — удалить только still-identifiable owned contribution.

Residents

1. `@NetworkPolicyAdapter <partial>` *Host-side projection того же semantic Adapter, который для Device publication координирует отдельный host mapping postcondition; host owner не сливается с managed-domain nft owner.*
2. `@HostRoutingContribution` *Direct lifecycle Machinery optional peaceful helper. Current Release-1 realization — `LinuxPeacefulHostRoutingContribution`; continuous host-routing supervision отсутствует.*

Artifacts

1. `host publication mapping state` *(observed, managed)* — отдельный ownership-marked host DNAT/publication scope, переводящий только явно выбранную local host publication surface в current stack-local publication target.
2. `peaceful host routing contribution` *(observed, managed)* — complete lifecycle-scoped host-routing state для выбранного helper traffic scope.
    1. `helper destination route state` *(observed, managed)* — remote Profile destinations и при необходимости Profile-SNAT identity routes в dedicated helper table.
    2. `helper dispatch RPDB state` *(observed, managed)* — selector-scoped preserve-main + helper lookup pairs и absolute managed-boundary bypass.

Эти Artifacts не являются children общего «host networking» Artifact: у них разные semantic
owners, lifecycle и postconditions. Общая Linux namespace лишь physical container.

Не принадлежат этому Space:

- host-global IPv4 forwarding;
- foreign/admin routing, RPDB, nft firewall/NAT;
- ordinary host interface/address lifecycle;
- aggressive authoritative helper state — capability postponed и не проектируется здесь;
- managed L3 door itself — `Ordinary-side transition`.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `STACK.PayloadTrafficManager` / policy assembly | desired Device publication | `@NetworkPolicyAdapter <partial>` |
| `@NetworkPolicyAdapter <partial>` | observe/converge/cleanup distinct owner scope | `host publication mapping state` |
| `@NetworkPolicyAdapter <partial>` | observe host forwarding/interface/address prerequisites without ownership | `Ambient host and external world.@OrdinaryHostNetwork.<host network observation>` |
| `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` | inbound traffic to selected local publication surface | `host publication mapping state` |
| `host publication mapping state` | DNAT toward current stack-local service/publication identity through managed boundary | `Ordinary-side transition.@managed L3 boundary realization.<host-side IP handoff>` |
| `STACK.@ProductLifecycleControl` | build/converge enabled helper contribution | `@HostRoutingContribution` |
| `@HostRoutingContribution` | converge/cleanup | `peaceful host routing contribution` |
| `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` | selected host traffic enters helper-owned RPDB scope | `peaceful host routing contribution` |
| `peaceful host routing contribution` | route selected traffic to explicit managed host endpoint | `Ordinary-side transition.@managed L3 boundary realization.<host-side IP handoff>` |
| `Ordinary-side transition.@managed L3 boundary realization.<host-side IP handoff>` | traffic emitted from Private network bypasses helper recapture and resumes ordinary host routing | `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` |

Findings

1. `NetworkPolicyAdapter cross-Space projection` — one semantic Device publication currently
   produces a managed-domain local-admission postcondition and a separate host mapping
   postcondition. Keeping one Adapter identity across both Spaces is valid via `<partial>`,
   but remains a decomposition review signal rather than evidence that host state belongs to
   Private network.
2. `Host forwarding prerequisite` — publication machinery may observe and report
   host-global forwarding disabled, but current requirements do not authorize enabling it.
3. `Peaceful helper lifecycle` — Release 1 owns only start/reload-update/stop contribution.
   Administrator changes between lifecycle operations are not helper drift, so no Manager is
   introduced.

Component diagram

```text
+---------------------------- STACK --------------------------------+
| PayloadTrafficManager                 @ProductLifecycleControl     |
+-----------+-----------------------------------+--------------------+
            | publication desired               | helper lifecycle
            v                                   v
+-----------+--------------------------------------------------------+
|                  VPN-GATE-managed host state                       |
|                                                                    |
| @NetworkPolicyAdapter <partial>      @HostRoutingContribution      |
|              |                                |                    |
|              v                                v                    |
| [host publication mapping]      [peaceful host routing contribution]|
|              |                                |                    |
+--------------|--------------------------------|--------------------+
               |                                |
               v                                v
+---------------------------+        +------------------------------+
| Ordinary-side transition  |        | Ordinary-side transition     |
+---------------------------+        +------------------------------+
               ^
               |
+--------------+----------------------------------------------------+
|                Ambient host and external world                    |
| forwarding/interfaces/routes not explicitly owned above           |
+-------------------------------------------------------------------+
```


# Ambient host and external world

Обычный host и внешний IP-мир за пределами явно owned VPN-GATE state. Этот Space является
источником/приемником ordinary-side traffic и предоставляет host/deployment mechanisms,
которыми VPN-GATE может пользоваться или которые может наблюдать, но не получает право
менять их только потому, что они влияют на его работу.

API

    @OrdinaryHostNetwork.<IP handoff> — ordinary-side IP environment, связанная с managed boundary.
    @OrdinaryHostNetwork.<host network observation> — наблюдение interface/address/routing/forwarding prerequisites там, где это требуется owned contracts.
    @systemd.<unit lifecycle> — selected Release-1 deployment/service-management interface для controller и explicitly bound VPN services.
    @ExternalConfigurationSource.read(...) — предоставить external configuration representation; current deployment may realize this as host file input.

Residents

1. `@OrdinaryHostNetwork` *Administrator/kernel-owned ordinary host network environment: interfaces, addresses, routing/RPDB, forwarding и foreign firewall/NAT.*
2. `@systemd` *Selected Release-1 deployment/service manager; обеспечивает controller readiness ordering и lifecycle explicitly bound VPN service units/cgroups.*
3. `@ExternalConfigurationSource` *Replaceable source external configuration representation consumed by STACK configuration boundary.*

Artifacts

1. `ordinary host interface/address state` *(observed where required; not core-managed)*.
2. `administrator routing/RPDB state` *(used; not core-managed)* — включает ordinary main/default и любые foreign policy rules вне явно reserved VPN-GATE owner scopes.
3. `host-global IPv4 forwarding state` *(observed where required; not core-managed)*.
4. `foreign host firewall/NAT state` *(not managed)*.
5. `ordinary external IP connectivity` — external network reality reachable through host; VPN-GATE не принимает ее ownership.
6. `deployment service state` — systemd controller/VPN unit state and ordering owned by deployment/service manager.
7. `external configuration representation` — operator-maintained input representation, из которой STACK строит normalized intent.

Явно owned host publication/helper objects исключены отсюда и находятся в
`VPN-GATE-managed host state`. Managed L3 door исключена и находится в
`Ordinary-side transition`.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `Ordinary-side transition.managed L3 boundary realization` | bidirectional ordinary-side IP handoff | `@OrdinaryHostNetwork` |
| `@OrdinaryHostNetwork` | ordinary traffic / underlay connectivity | `ordinary external IP connectivity` |
| `VPN-GATE-managed host state.@NetworkPolicyAdapter <partial>` | observe forwarding/interface/address prerequisites only | `@OrdinaryHostNetwork` |
| `Operator.OperatorClient` | create/change external configuration representation | `@ExternalConfigurationSource` |
| `@ExternalConfigurationSource` | candidate representation | `STACK.@ConfigurationAdapter` |
| `Operator.OperatorClient` | start/stop/restart controller deployment | `@systemd` |
| `@systemd` | invoke/contain controller service lifecycle and wait for readiness semantics | `STACK.@ProductLifecycleControl` |
| `Operator.OperatorClient` | start/stop/restart supported stack-specific VPN service | `@systemd` |
| `@systemd` | supervise explicitly bound VPN process/cgroup | `VPN external ends.@VPNChannel[]` |
| `@systemd` | reverse dependency/order stop bound VPN service before final managed-domain teardown | `VPN external ends` / `STACK.@ProductLifecycleControl` |

Finding: `Ambient breadth` — этот Space намеренно объединяет ordinary host и внешний
ordinary IP world, пока внутри них нет самостоятельной VPN-GATE-managed semantics,
требующей дополнительной boundary. Наличие множества Linux objects само по себе не повод
дробить Space.

Component diagram

```text
+---------------------------- Operator ------------------------------+
| config / lifecycle / VPN-service commands                          |
+----------+----------------------+----------------------------------+
           |                      |
           v                      v
+----------+-----------+   +------+----------------------------------+
| ExternalConfigSource|   | systemd                                  |
+----------+-----------+   +------+----------------+-----------------+
           |                      |                |
           v                      v                v
+----------+-----------+     +----+-----+   +------+-----------------+
|        STACK         |     |  STACK   |   | VPN external ends      |
+----------------------+     +----------+   +------------------------+

+-------------------------------------------------------------------+
|               Ambient host and external world                     |
|                                                                   |
| @OrdinaryHostNetwork                                              |
|   [interfaces/addresses] [admin routing/RPDB] [host forwarding]   |
|   [foreign firewall/NAT]                                          |
|              |                                                    |
|              v                                                    |
|      [ordinary external IP connectivity]                          |
+--------------^----------------------------------------------------+
               |
               | ordinary-side IP
+--------------+-------------------+
| Ordinary-side transition          |
+-----------------------------------+
```


# Operator

Человеческая либо automation-среда, задающая deployment/product intent и потребляющая
наблюдаемое состояние продукта. Operator не является владельцем внутреннего semantic
runtime state VPN-GATE и не получает implicit authority над managed lower state в обход
опубликованных control/configuration boundaries.

Residents

1. `OperatorClient` *Человек или automation, использующие документированные configuration, lifecycle, VPN-onboarding и status/diagnostic surfaces.*

Artifacts

1. `operator configuration intent` *(managed by operator)* — желаемая Device/Profile/helper configuration до ее проверки STACK.
2. `VPN onboarding intent` *(managed by operator)* — VPN-specific configuration/service preparation, остающаяся отделенной от VPN-GATE Device/Profile policy.
3. `observed product status` *(observed)* — current truthful status/diagnostic projection, а не источник authoritative runtime truth.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `OperatorClient` | edit/provide candidate product configuration | `Ambient host and external world.@ExternalConfigurationSource` |
| `OperatorClient` | product `start / stop / restart / supported update` through deployment/control mechanism | `Ambient host and external world.@systemd` / `STACK.@ProductLifecycleControl` |
| `OperatorClient` | prepare stack-specific VPN service/config according to supported onboarding contract | `VPN external ends.@VPNChannel[]` |
| `OperatorClient` | VPN service start/stop/restart through selected service manager | `Ambient host and external world.@systemd` |
| `STACK.@RuntimeStatusAgent` / presentation environment | current status/diagnostics | `OperatorClient` |
| `OperatorClient` | inspect current result; choose later explicit action if required | `observed product status` |

Не существует interaction «Operator напрямую исправляет owned kernel state» как нормального
product API. Root/admin intervention вне supported boundaries остается внешним вмешательством
и может привести к containment/unready state; оно не превращается в штатную management
semantics.

Component diagram

```text
+-------------------------------------------------------------------+
|                              Operator                             |
|                                                                   |
| OperatorClient                                                    |
|    | config             | lifecycle        | VPN onboarding       |
|    |                    |                  |                      |
|    +--------------------+------------------+------------------+   |
|                                                           ^   |   |
|                                                status ----+   |   |
+---------------------------------------------------------------|---+
            |                    |                    |          |
            v                    v                    v          |
+-----------+-----------+  +-----+------+  +----------+-------+  |
| External config source|  |   systemd   |  | VPN external ends|  |
+-----------------------+  +-----+------+  +------------------+  |
                                |                                |
                                v                                |
                         +------+----------------+               |
                         |       STACK           |---------------+
                         | lifecycle / status    |
                         +-----------------------+
```



# Annex C. Private network components

## C.001 NetworkPolicyAdapter

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

7. `Cross-Space Device publication`
   *Один normalized Device publication intent требует двух independently verified postconditions: managed-domain local admission в `Private network` и host publication mapping в `VPN-GATE-managed host state`. Host-side occurrence того же semantic Adapter показывается в соседнем Space как отдельный `NetworkPolicyAdapter <partial>`; физическое размещение host nft state не расширяет ownership этого Private-network occurrence.*

## C.002 NetworkPolicyLayoutCalculator

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

## C.003 NetworkPolicyEnforcer

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

## C.004 VPNPathAdapter

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

## C.005 ForwardingGate

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

## C.006 ForwardingGateDriver

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
