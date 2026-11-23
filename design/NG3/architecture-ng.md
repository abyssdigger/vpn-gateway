# VPN-GATE NG3 — структурированная архитектура

**Статус:** текущая authoritative архитектура NG3  
**Предыдущий плоский отчет:** удалён из current tree; последнее полное тело — `38607e247f39a87a361a4541e3dace6585c8d52a:design/NG3/architecture.md`  
**Компонентная модель:** `design/component-model.md`  
**Требования:** `design/NG3/requirements.md`

Этот документ является единственным текущим источником принятых архитектурных решений NG3.
Новые архитектурные решения, изменения component/API/interaction contracts и architecture
closure requirements вносятся и трассируются здесь.

Бывший `design/NG3/architecture.md` удалён из current tree. Полное последнее тело плоского
отчета доступно в Git history на baseline
`38607e247f39a87a361a4541e3dace6585c8d52a`; старые ссылки в review/research/evidence
продолжают обозначать соответствующий исторический baseline и не делают удалённый отчет
текущим источником архитектуры.

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

### 2.1. Residents tree и component specs

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

Все resident'ы, являющиеся компонентами VPN-GATE, описываются после карты Spaces в
Space-local Component Annex (§2.9). Все component specs внутри Annex имеют одинаковый
уровень заголовка. Иерархия из их расположения не выводится.

Если компонент представлен в Space как `<partial>` или иным review-marker, причина
маркера поясняется в его кратком component spec.

Если одна technical component identity представлена как `<partial>` в нескольких Spaces,
Annex каждого Space содержит собственный spec только для своей проекции этого компонента.
Общая technical identity не создает скрытого глобального spec поверх Spaces и не заменяет
Space-local описание ответственности/API этой partial occurrence.

Для **внешнего** Space `Resident` может быть external actor/system/capability provider,
который не является компонентом VPN-GATE и поэтому не классифицируется как
Engine/Machinery по `design/component-model.md`. На него по-прежнему распространяются
Space/API/Interaction rules, но отдельный VPN-GATE component spec не требуется, если
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

1. каждый distinct resident, являющийся компонентом VPN-GATE, имеет Space-local component
   spec в соответствующем Component Annex; external residents отдельного VPN-GATE spec не требуют;
2. каждый component spec в Annex соответствует resident occurrence из дерева этого Space;
3. parent-child relation существует только в дереве `Residents` и не выводится из порядка
   или heading depth specs;
4. каждый `@Resident`, являющийся компонентом VPN-GATE, имеет хотя бы одну непосредственно
   востребованную извне точку API, отмеченную `@` в его component spec; boundary API external
   resident'а описывается его Space contract без искусственного VPN-GATE spec;
5. каждая строка Space `API` разрешается либо в конкретную `@`-точку API resident'а из
   `Residents`, либо в явно объявленную `@`-точку boundary-capability Artifact;
6. internal method без `@` не должен появляться как Space API только потому, что его parent
   экспортирует другой метод;
7. marker `@` относится к occurrence/API относительно данного Space и не является частью
   canonical component name в Annex heading;
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

Inline component specs между Space sections не используются: карта Spaces остается
непрерывной, а подробные specs находятся только в соответствующих Annexes.

Для materialized component spec поддерживается двунаправленная implementation trace.

Полный production-code edge хранится в `design/NG3/implementation-traceability.md`: каждый
production implementation unit обязан там ровно один раз разрешаться в один или несколько
Annex/spec IDs. Component-local блок `Implementation` остается кратким списком основных
entry/reference units и не обязан дублировать полный lower implementation graph. Локальный
`Architecture:` marker в таком unit является полезной самодокументацией и обязателен для
unit, явно перечисленного в component-local `Implementation`.

Нормативная requirement trace остается в component spec. Requirement IDs в code comment
допустимы как convenience, но не являются вторым источником истины. Production unit без
нормального requirement path допускается только как явно описанный `Architecture debt` в
полном trace manifest; такой debt является finding и должен быть видимым механической
проверке.

Таким образом минимальная цепочка reverse trace имеет вид:

```text
code
    -> implementation trace manifest
    -> Annex X.YYY component spec
    -> Implements / Constrained by
    -> requirement
```

Если один implementation unit обслуживает несколько component occurrences, marker перечисляет
каждый из них явно. File placement, import graph или имя Linux primitive сами по себе не
считаются архитектурной traceability.



Канонический heading component spec записывает стабильный ID в квадратных скобках, например
`## [A.011] ProtectiveModeManager`. Обычное текстовое упоминание использует `A.011`.
Если ID является текстом гиперссылки, допустима обычная Markdown-форма
`[A.011](...)`; она не является каноническим spec heading.

Каждая requirement-связь в блоках `Implements`, `Implements / supports` и
`Supports implementation of` имеет явный статус материализации:

- [`full`] — вся текущая архитектурная обязанность данного компонента по указанному R/C
  материализована в рабочей реализации продукта и имеет требуемую для этой обязанности
  трассировку на реализацию и подтверждающие материалы;
- [`partial`] — материализована только часть текущей архитектурной обязанности компонента;
  конкретный отсутствующий остаток обязан быть явно описан в этом component spec;
- [`none`] — материализация текущей архитектурной обязанности компонента в рабочей реализации
  отсутствует; component spec обязан явно назвать отсутствующую часть и применимое условие,
  ограничение или другую причину, если она существует.

Этот статус относится только к вкладу данного компонента в R/C и не заменяет статус
требования. Фактическое исполнение требования определяется по совокупности всех обязательных
архитектурных вкладов с учетом применимых ограничений. Изменение реализации внутри уже
заявленного `full`, `partial` или `none` не требует редакции архитектуры, пока не
меняется сам статус или архитектурная обязанность.

### 2.9.1. Stable evidence references

Стабильная архитектура ссылается на executable/review evidence только через IDs из
`design/NG3/evidence-index.md` вида `EV-00000`, `EV-00010`, ... . Шаг 10 оставляет
пространство для поздних вставок без перенумерации существующих ссылок.

Конкретные CI workflow/run IDs, commit SHAs и experiment result artifacts принадлежат записи
evidence index либо связанному review/result artifact. Они не являются стабильными адресами
архитектурного решения.

### 2.9.2. Lower technical-boundary reuse

Lower Machinery переиспользуется только при совпадении **полного технического контракта**,
а не потому, что разные owners вызывают один executable или Linux subsystem.

- Driver может объединять свои Reader/Executor operations, если их отдельное выделение не
  дает независимой переиспользуемой/заменяемой границы.
- Отдельный Reader/Executor вводится только при самостоятельной архитектурной ценности:
  exact reuse, независимая замена/тестирование или заметное упрощение нескольких callers.
- Raw `run(argv)` / stdin-script runner остается implementation primitive ниже component
  model и не считается generic Executor.
- Generic `NftDriver`, `IpRouteDriver`, `SysctlDriver` или универсальные
  route/rule Readers не вводятся без совпадающего owner-safe контракта. Ownership,
  generation-stability checks, reserved-resource classification и допустимые mutations
  остаются в узких lower boundaries.
- `Backend` сохраняется только для реальной stateless композиции нескольких lower
  responsibilities/mechanisms. Узкая граница одного technical mechanism contract является
  Driver; самостоятельная read-only operation — Reader.

Текущая Release-1 realization применяет это правило так:

- shared `LinuxStructuralRoutingDriver` переиспользуется payload/probe routing там, где
  route mutation contract действительно совпадает;
- NG3 nft namespace inventory является отдельным Reader;
- structural-policy, composite-nft, probe-routing и stack-return-affinity остаются
  Backend-композициями;
- narrow nft scaffold/owner, route-priority и host-managed-routing boundaries являются
  Drivers.

**Evidence:** `EV-00010`.



### 2.9.3. Target production-runtime language boundary

**Covers:** `VPNG-D001-R1.R1.R8.R1`, `VPNG-D001-R1.R1.R8.R2`.

Rust является target implementation boundary, а не component role и не источником product
semantics. Финальная stable production runtime boundary включает configuration normalization,
lifecycle/runtime state, policy calculation/reconciliation, VPN-path observation и
OS/network-state observation/actuation. Для release, который заявляет соответствие этой
финальной boundary, non-exempt runtime responsibilities должны выполняться Rust
implementation; Python reference не может оставаться скрытой dependency этих обязанностей.

Текущий `design/NG3/code/python/rou/` остается executable reference/evidence, пока
семантика и applicability доказываются. Disposable experiments, CI/evidence harnesses, test
fixtures, build/install tooling, code generation и research/reference implementations могут
использовать другой подходящий язык и не мигрируют только ради production-language rule.

Production Rust по умолчанию safe. `unsafe`/memory-unsafe FFI допустимы только на узкой
необходимой lower boundary, с явным soundness invariant и focused evidence; ими нельзя
обходить ownership/state invariants, выразимые safe Rust.

Host-routing helper language exception и Python-completion ordering задаются уже принятыми
`VPNG-D001-R1.R1.R8.C1`, `VPNG-D001-R1.R1.R8.C2`, `VPNG-D001-R1.R1.R8.C3` и остаются
implementation-replacement constraints, а не поводом менять component semantics.


### 2.9.4. Deliberately omitted machinery

Текущая архитектура намеренно не вводит универсальные механизмы, для которых нет
самостоятельного принятого Requirement/Constraint. Это применение
`VPNG-D001-R1.R1.R1`, а не обещание никогда не вводить такие механизмы.

Без нового принятого требования или обнаруженного необходимого контракта не вводятся:

- global event journal или generic reliable replay bus;
- universal revision/epoch framework;
- global availability state machine или attempt-history storage;
- отдельный route-priority Manager или отдельный availability route writer;
- independent global lifecycle Engine/LifecycleManager;
- configuration super-object, объединяющий внутренние состояния всех subsystem;
- universal probe-mechanism framework шире узкого `ActiveProbeDriver` contract;
- kernel-specific routing allocation objects в upper Managers;
- generic Linux subsystem Drivers/Readers только ради общей формы вызова.

Конкретные компоненты могут появиться позже, если новый принятый requirement делает их
необходимыми. До этого отсутствие такой machinery считается частью минимально достаточной
архитектуры, а не незакрытым architecture gap.

## 2.10. Closed requirement architecture coverage index

Этот индекс закрывает requirement -> architecture направление там, где requirement является
parent/root либо cross-cutting contract и поэтому не должен искусственно приписываться одному
component spec. Он не дублирует Statement: каждая группа указывает реальные архитектурные
owners/sections, через которые реализуется соответствующее обязательство.

### Managed VPN routing and supported VPN integration

**Requirements:** `VPNG-U001`, `VPNG-U001-R1`, `VPNG-U001-R1.R3`,
`VPNG-U001-R1.R3.C1`, `VPNG-U001-R1.R3.C1.R1.R1`,
`VPNG-U001-R1.R3.C1.R1.R2`, `VPNG-U001-R1.R3.C3`,
`VPNG-U001-R1.R3.C3.R1`, `VPNG-U001-R1.R3.R6`,
`VPNG-U001-R1.R3.R6.R1`, `VPNG-U001-R1.R3.R6.R2`.

**Architecture coverage:** STACK `PayloadTrafficManager`, Private
`NetworkPolicyAdapter`/`VPNPathAdapter`, ordinary-side transition, Space
`VPN external ends`, A.001 lifecycle composition and the evidence-backed OpenVPN/systemd
integration boundary. Bounded client transport/control admission is normalized by A.002 and
materialized through C.001 local-integration policy; server transport publication uses the
two-postcondition C.001 managed-local admission plus E.001 host publication mapping. VPN
runtime remains externally provisioned/supervised where the integration contract says so;
VPN-GATE owns its own network policy rather than VPN-specific configuration.

### Ordinary-host integration and helper scope

**Requirements:** `VPNG-U001-R2.R1`, `VPNG-U001-R2.R1.R1`,
`VPNG-U001-R5`, `VPNG-U001-R5.R1`, `VPNG-U001-R5.R1.R1`,
`VPNG-U001-R5.R2.C1`.

**Architecture coverage:** Annex E `HostRoutingContribution` plus Spaces
`VPN-GATE-managed host state` and `Ambient host and external world`. Core forwarding does
not require the peaceful helper when administrator routing satisfies the host-integration
contract. Aggressive authoritative helper semantics remain outside Release-1; E.002
explicitly prevents peaceful helper machinery from silently acquiring them. Current aggressive
architecture is separated into E.003/E.004 and remains constrained out of Release 1 by
`VPNG-U001-R5.R2.C1`; it is not folded into the peaceful helper.

### Aggressive host routing and administrative protective mode

**Requirements:** `VPNG-U001-R5.R2`, `VPNG-U001-R5.R2.R1`,
`VPNG-U001-R5.R2.R2`, `VPNG-U001-R5.R2.R3`,
`VPNG-U001-R5.R2.R3.R1`, `VPNG-U001-R5.R2.R3.R2`,
`VPNG-U004-R5`, `VPNG-U004-R5.R1`, `VPNG-U004-R5.R2`,
`VPNG-U004-R5.R3`, `VPNG-U004-R5.R4`.

**Architecture coverage:** E.003 `AggressiveHostRoutingManager` owns continuous aggressive
semantics and escalation; child E.004 `AggressiveHostRoutingEnforcer` owns bounded composite
routing + escape-protection convergence with fail-closed ordering. A.011
`ProtectiveModeManager` owns source-scoped public protective requests, continuous
confirmation and safe release; C.010 `ProtectivePayloadGate` owns the single
Private-network containment gate. EXP-081 rejects owned-object-only routing authority,
EXP-084 validates independent aggressive escape protection, and EXP-083 validates the
selected one-gate protective lower mechanism.

### Human configuration and Device/Profile policy model

**Requirements:** `VPNG-U001-R4`,
`VPNG-U001-R1.R4`, `VPNG-U001-R1.R4.R1`, `VPNG-U001-R1.R4.R2`,
`VPNG-U001-R1.R4.R2.R1.C1`,
`VPNG-U001-R4.R5.R1`, `VPNG-U001-R4.R5.R2`,
`VPNG-U001-R4.R5.R3`, `VPNG-U001-R4.R5.R4`,
`VPNG-U001-R4.R4.R1`, `VPNG-U001-R4.R4.R1.C1`,
`VPNG-U001-R4.R4.R2`, `VPNG-U001-R4.R4.R2.R1`,
`VPNG-U001-R4.R4.R3`, `VPNG-U001-R4.R4.R4`,
`VPNG-U001-R4.R4.R4.R2`, `VPNG-U001-R4.R4.R4.R3`,
`VPNG-U001-R4.R4.R4.R4`, `VPNG-U001-R4.R4.R4.R4.C1`,
`VPNG-U001-R4.R4.R5`, `VPNG-U001-R4.R4.R6`,
`VPNG-U001-R4.R4.R6.R1`, `VPNG-U001-R4.R4.R6.R2`,
`VPNG-U001-R4.R4.R6.R2.R1`, `VPNG-U001-R4.R4.R6.R2.R2`,
`VPNG-U001-R4.R4.R6.R2.R3`, `VPNG-U001-R4.R4.R6.R2.R4`,
`VPNG-U001-R4.R4.R6.R2.R5.C1`,
`VPNG-U001-R4.R4.R6.R3`, `VPNG-U001-R4.R4.R6.R4`,
`VPNG-U001-R4.R4.R6.C1`.

**Architecture coverage:** A.002 `ConfigurationAdapter` owns strict human representation
normalization and reference validation; A.005 `PayloadPolicyCalculator` preserves
Device/Profile semantic separation; C.001/C.003 materialize normalized firewall/NAT/
publication policy without leaking Linux IDs into user intent. Ordered fields remain ordered
semantic input; set-like declarations and disabled placeholders do not acquire hidden runtime
meaning.

### Inbound source identity, packet matching and return affinity

**Requirements:** `VPNG-U001-R3`, `VPNG-U002-R2.R1.R3`,
`VPNG-U003-R4`.

**Architecture coverage:** A.005/C.001/C.003 preserve literal payload source/destination/type
matching before managed source translation; Profile source identity translation remains
inside the managed policy boundary rather than rewriting the meaning of the policy match.
C.001-owned return-affinity state preserves the accepted VPN ingress routing domain for
established return traffic instead of reclassifying it onto another allowed path.

### Explicit VPN traffic policy and inbound first-release bound

**Requirements:** `VPNG-U002`, `VPNG-U002-R2`, `VPNG-U002-R2.R2.R2`,
`VPNG-U002-R2.R3.C1`, `VPNG-U002-R2.R3.C1.R1`.

**Architecture coverage:** A.002/A.005 define explicit Profile/Device intent and pre-actuation
validation; A.004 derives current membership only from valid bindings; C.004 proves current
endpoint bindings; C.001/C.003 materialize only allowed traffic. Release-1 multi-path
inbound/bidirectional capacity is rejected during normalization rather than guessed after
runtime discovery.

### Multi-path preference and availability adaptation

**Requirements:** `VPNG-U003`, `VPNG-U003-R3`, `VPNG-U003-R3.R1.R1`,
`VPNG-U003-R3.R2.R1`, `VPNG-U003-R3.R5.R1`, `VPNG-U003-R3.R5.R2`,
`VPNG-U003-R3.R6.R3.R1.C1`.

**Architecture coverage:** A.004 `PayloadTrafficManager`, A.006
`AvailabilityPriorityCalculator`, A.007 `AvailabilityProbeAgent` and C.008
`ActiveProbeDriver`. Baseline order and stable current binding identity are preserved;
availability is only a negative priority modifier with bounded degradation/recovery
confirmation. Release-1 physical probe mechanism is ICMP only.

### Safety, recovery and operator truth

**Requirements:** `VPNG-U004`, `VPNG-U004-R4.R6`,
`VPNG-U004-R5.C1`, `VPNG-M001-R1.R1.R2.R1`,
`VPNG-M001-R1.R1.R3.R1`, `VPNG-M001-R1.R1.C1.R1`, `VPNG-M001-R2`.

**Architecture coverage:** C.003 exact/fail-closed enforcement and C.005 forwarding barrier
provide restrictive failure behavior; A.004/A.007 and alpha reconciliation perform finite
cadence fresh observation/recovery for authoritative active state; A.001 owns bounded
lifecycle recovery/cleanup; A.008/A.009 expose truthful current status and A.010 provides
separate event/reaction history without making logs the source of current truth.
Administrator-facing recovery documentation must preserve the ownership split between
authoritative product state, external integration state and peaceful-helper contributions
returned to administrator control.

### Maintainability, continuity, evidence and development boundaries

**Requirements:** `VPNG-D001-R1`, `VPNG-D001-R1.R1`, `VPNG-D001-R1.R1.R2`,
`VPNG-D001-R1.R1.R3.R5`, `VPNG-D001-R1.R1.R3.R4`,
`VPNG-D001-R1.R1.R3.R4.R1`, `VPNG-D001-R1.R1.R4`,
`VPNG-D001-R1.R1.R6.R1`, `VPNG-D001-R1.R1.R6.R2`,
`VPNG-D001-R1.R1.R7.R1`, `VPNG-D001-R1.R1.R8.R1`,
`VPNG-D001-R1.R1.R8.R2`, `VPNG-D001-R3`, `VPNG-D001-R3.R1`,
`VPNG-D001-R3.R1.R1`, `VPNG-D001-R3.R2`, `VPNG-D001-R3.R3`,
`VPNG-D001-R3.C1`.

**Architecture coverage:** the Space/component decomposition and `design/component-model.md`
localize responsibilities and lower mechanism boundaries; §2.9 implementation trace,
`design/NG3/implementation-traceability.md` and the EV index provide bidirectional
trace/evidence; binding/interface generation contracts preserve cross-boundary identity;
supported VPN applicability gates live in `VPN external ends`; §2.9.2 defines exact-contract
lower reuse rather than generic frameworks; §2.9.3 defines the production-language boundary.
Requirement semantic changes therefore require re-review of their indexed architecture
coverage before implementation proceeds. Release-model process obligations
`VPNG-D001-R3`, `.R1`, `.R2`, `.R3` and `.C1` are materialized by
`PROJECT-CONVENTIONS.md` §10; runtime observability for `VPNG-D001-R3.R1.R1` belongs to
A.008 and remains [`none`] until preparation of the first actual release permits and requires
that implementation.

**Evidence:** `EV-00010`.



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

Текущие Annexes A–G следуют карте Spaces один к одному. Каждый resident, являющийся
компонентом VPN-GATE, имеет Space-local spec; external residents остаются описаны только
контрактами соответствующего Space и не получают искусственных VPN-GATE component specs.



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
    @ProtectiveModeManager.request_active(source, ...) — установить source-scoped запрос защиты; success возвращается только после подтверждения полного protective postcondition.
    @ProtectiveModeManager.request_inactive(source, ...) — снять запрос только данного source; gate может быть снят лишь когда других active sources нет и normal release precondition подтвержден.
    @ProtectiveModeManager.current_state(∅) — вернуть текущий набор request sources и confirmed / problem protective state.
    @ConfigurationAdapter.normalize(...) — принять внешнее configuration representation и вернуть validated normalized domain intents.
    @RuntimeStatusAgent.<current snapshot publication> — предоставить текущую user-facing status projection.
    RuntimeStatusTextRenderer.render(snapshot) — получить обязательный compact human-readable Devices/Profiles report; delivery surface остаётся заменяемой.

Residents

1. `@ProductLifecycleControl` *Direct procedural Machinery product lifecycle; не является Engine и не вводит самостоятельную lifecycle policy/state machine.*
2. `@ConfigurationAdapter` *Direct boundary от external configuration representation к validated normalized domain intents.*
    1. `AvailabilityDescriptionResolver` *Pure Calculator, разрешающий Profile/Device availability description без runtime topology inference.*
3. `PayloadTrafficManager` *Manager текущей semantic payload-policy среды: structural intent, binding projection, availability confirmation и effective path order.*
    1. `PayloadPolicyCalculator` *Pure Calculator structural payload policy из normalized intent и уже подтвержденных внешних фактов.*
    2. `AvailabilityPriorityCalculator` *Pure Calculator effective path order из current membership, availability problem state, active path и reserve semantics.*
4. `@ProtectiveModeManager` *Manager явного защитного режима продукта: владеет запрошенным/подтвержденным состоянием режима, continuous confirmation и безопасным выходом.*
5. `AvailabilityProbeAgent` *Agent ongoing availability observation; планирует bounded checks и публикует normalized evidence, но не управляет наблюдаемой внешней доступностью.*
6. `@RuntimeStatusAgent` *Agent current-only status composition из authoritative owner snapshots; не актуирует наблюдаемые domains.*
    1. `RuntimeStatusTextRenderer` *Direct Calculator, чисто преобразующий RuntimeStatusSnapshot в нормативный compact Devices/Profiles text report.*

Artifacts

1. `accepted normalized intent` *(observed, managed)* — текущие validated Device/Profile/availability/helper intents, от которых разрешено строить dependent desired state. Это не глобальный mutable config object и не копия external file syntax.
2. `payload semantic state` *(observed, managed)* — текущая owner projection `PayloadTrafficManager`.
    1. `structural payload intent` *(observed, managed)*
    2. `Device binding projection` *(observed, managed)* — bounded current logical binding state, а не endpoint inventory.
    3. `availability confirmation state` *(observed, managed)*
    4. `effective path-order state` *(observed, managed)* — current active path/effective order; не per-flow affinity.
3. `availability observation context` *(observed, managed)* — current requested subjects, cadence, bounded in-flight identities/generation tokens и diagnostics `AvailabilityProbeAgent`.
4. `controller ownership/readiness session` *(observed, managed)* — bounded procedural lifecycle state, включая retained single-controller ownership и текущий READY/cleanup result. Его наличие не превращает lifecycle в Engine.
5. `protective mode state` *(observed, managed)* — current source-scoped request set и confirmed/problem projection public protective mode; подтвержденный active state требует exact `Private network.protective payload gate state`.
6. `runtime status snapshot` *(observed, managed)* — current-only composition authoritative snapshots; не event history и не system-of-record.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `Operator.OperatorClient` / deployment control | `start / stop / restart / optional reload` | `@ProductLifecycleControl` |
| `Operator.OperatorClient` / authorized automation | request protective active / inactive | `@ProtectiveModeManager` |
| `VPN-GATE-managed host state.@AggressiveHostRoutingManager` | add/remove its own protective request around unrecoverable aggressive-routing failure/recovery | `@ProtectiveModeManager` |
| `@ProductLifecycleControl` | acquire/release single-controller ownership and maintain bounded session | `controller ownership/readiness session` |
| `Ambient host and external world.@ExternalConfigurationSource` | candidate configuration representation | `@ConfigurationAdapter` |
| `@ConfigurationAdapter` | resolve normalized availability descriptions | `AvailabilityDescriptionResolver` |
| `@ConfigurationAdapter` | accepted normalized domain intents | `accepted normalized intent` |
| `@ProductLifecycleControl` | validate/load candidate intent before dependent mutation | `@ConfigurationAdapter` |
| `@ProductLifecycleControl` | preflight/ensure/destroy managed data-plane environment | `Private network.@ManagedNetworkEnvironmentLifecycle` |
| `@ProductLifecycleControl` | establish/remove ordinary-side managed boundary through the same current lifecycle transaction | `Ordinary-side transition.@ManagedNetworkEnvironmentLifecycle` |
| `@ProductLifecycleControl` | converge/cleanup enabled host-side contribution | `VPN-GATE-managed host state.@HostRoutingContribution` |
| `@ProductLifecycleControl` | activate/cleanup desired lower network policy | `Private network.@NetworkPolicyAdapter` |
| `accepted normalized intent` | current structural inputs | `PayloadTrafficManager` |
| `PayloadTrafficManager` | calculate structural semantic projection | `PayloadPolicyCalculator` |
| `PayloadTrafficManager` | calculate effective availability-dependent ordering | `AvailabilityPriorityCalculator` |
| `PayloadTrafficManager` | observe/verify current endpoint bindings | `Private network.@VPNPathAdapter` |
| `PayloadTrafficManager` | apply/reconcile current desired lower policy | `Private network.@NetworkPolicyAdapter` |
| `PayloadTrafficManager` | own/update current semantic state | `payload semantic state` |
| `payload semantic state` / `controller ownership/readiness session` | current normal-release precondition | `@ProtectiveModeManager` |
| `@ProtectiveModeManager` | converge/verify dedicated protective containment | `Private network.@ProtectivePayloadGate` |
| `@ProtectiveModeManager` | own/update requested and confirmed mode | `protective mode state` |
| `accepted normalized intent` / current bindings | synchronize requested observation subjects | `AvailabilityProbeAgent` |
| `AvailabilityProbeAgent` | own current check schedule/context | `availability observation context` |
| `AvailabilityProbeAgent` | execute one physical check | `Private network.@ActiveProbeDriver` |
| `AvailabilityProbeAgent` | `AvailabilityEvidence` InfoEvent | `PayloadTrafficManager` |
| `PayloadTrafficManager` | current payload projection InfoEvent | `@RuntimeStatusAgent` |
| `AvailabilityProbeAgent` | current observation/diagnostic InfoEvent | `@RuntimeStatusAgent` |
| `@ProductLifecycleControl` | lifecycle/readiness/cleanup projection | `@RuntimeStatusAgent` |
| `@RuntimeStatusAgent` | compose/update | `runtime status snapshot` |
| `@RuntimeStatusAgent` | current snapshot publication | `RuntimeStatusTextRenderer` / other presentation environment |
| `RuntimeStatusTextRenderer` | required compact human-readable Devices/Profiles text | `Operator.OperatorClient` / presentation environment |

Findings

1. `Status presentation boundary` — the compact Devices/Profiles text representation is
   now required by `VPNG-M001-R2.R2.*` and is owned by `RuntimeStatusTextRenderer`.
   The delivery mechanism remains replaceable: current alpha may publish `status.txt` beside
   `status.json`, but neither path is thereby a stable product API.
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
| @ProtectiveModeManager -------------------------+     |                   |
|       |                |               |        |    v                   |
|       |                |               |        | @RuntimeStatusAgent    |
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
        | @ProtectivePayloadGate <-----+             | physical probe        |
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

    @ManagedL3BoundaryLifecycle.preflight(...) — read-only классифицировать transition как absent / established / conflict относительно существующей Private-network environment.
    @ManagedL3BoundaryLifecycle.ensure(...) — материализовать absent managed-L3 door либо подтвердить exact existing realization.
    @ManagedL3BoundaryLifecycle.destroy(...) — удалить owned transition realization и fresh-confirm отсутствие boundary.
    @managed L3 boundary realization.<private-side IP handoff> — passive bidirectional handoff к Private network.
    @managed L3 boundary realization.<host-side IP handoff> — passive bidirectional handoff к ordinary host network.

Отдельного `open/closed` API сейчас нет. `established` означает transport-ready L3 door с
подтвержденными handoff endpoints; готовность Private network использовать ordinary side
требует также exact portal state. Aggressive host-routing protection принадлежит `VPN-GATE-managed host state` E.003/E.004
и не меняет API самого transition.

Residents

1. `@ManagedL3BoundaryLifecycle` *Direct lifecycle Machinery ordinary-side transition: наблюдает, материализует и удаляет exact managed-L3 boundary realization независимо от lifecycle Private-network environment и portal.*

Artifacts

1. `managed L3 boundary realization` *(observed, managed)* — целостная установленная ordinary-side L3 «дверь». Current exact postcondition включает обе стороны selected boundary backend, их operational/backend invariants и host-side reachability contribution, необходимую самой границе. Конкретные veth peer identities, Proxy ARP, `rp_filter` и другие backend-specific детали не поднимаются в самостоятельные Artifacts, пока ими не требуется независимо управлять.

Состояния Artifact на этом уровне:

```text
absent
established
conflict
```

`established` включает exact transport/backend invariants и наличие обоих handoff endpoints. Готовность Private network использовать ordinary side дополнительно требует exact `ordinary-side IP portal` state в соседнем Space.
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
| `STACK.@ProductLifecycleControl` | lifecycle `observe / establish / remove` | `@ManagedL3BoundaryLifecycle` |
| `@ManagedL3BoundaryLifecycle` | observe/materialize/remove exact boundary state | `managed L3 boundary realization` |
| `Private network.@ordinary-side IP portal.<IP handoff>` | bidirectional IP handoff | `@managed L3 boundary realization.<private-side IP handoff>` |
| `@managed L3 boundary realization.<host-side IP handoff>` | bidirectional IP handoff | `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` |
| `VPN-GATE-managed host state.@peaceful host routing contribution.<selected host traffic>` | routes selected host traffic toward the explicit managed host endpoint | `@managed L3 boundary realization.<host-side IP handoff>` |

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
| @ManagedL3BoundaryLifecycle                                  |
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
|   Private network   |    | Managed-host / ambient host     |
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

    @ManagedNetworkEnvironmentLifecycle.preflight(...) — read-only классифицировать namespace/loopback materialization как absent / exact / conflict under protective containment.
    @ManagedNetworkEnvironmentLifecycle.ensure(...) — создать absent namespace/loopback materialization либо подтвердить exact existing state.
    @ManagedNetworkEnvironmentLifecycle.destroy(...) — удалить environment materialization после cleanup зависимых artifacts и fresh-confirm namespace absence.
    @OrdinarySidePortalLifecycle.observe(...) — наблюдать stack-local identity и ordinary-side default на current private-facing transition endpoint.
    @OrdinarySidePortalLifecycle.ensure(...) — converge exact stack-local identity + ordinary-side default после established transition.
    @OrdinarySidePortalLifecycle.cleanup(...) — удалить owned portal address/default state и fresh-confirm absence.
    @NetworkPolicyAdapter.observe_owned_policy(...) — вернуть свежую owner-scoped проекцию управляемой network policy.
    @NetworkPolicyAdapter.apply(...) — применить semantic desired policy и подтвердить postcondition.
    @NetworkPolicyAdapter.cleanup(...) — удалить owned policy scope и подтвердить его отсутствие.
    @VPNPathAdapter.observe_device_endpoints(...) — наблюдать текущие candidate VPN endpoints в Private network.
    @VPNPathAdapter.verify_path_binding(...) — подтвердить однозначный current binding logical path к endpoint.
    @ActiveProbeDriver.execute(...) — выполнить один bounded probe через заранее подтвержденный current VPN-side execution context.
    @ForwardingGate.observe(∅) — вернуть свежий authoritative state корневого IPv4 forwarding gate.
    @ForwardingGate.converge(...) — установить требуемое состояние gate и подтвердить его свежим наблюдением.
    @ProtectivePayloadGate.observe(∅) — свежим наблюдением подтвердить exact dedicated protective containment state.
    @ProtectivePayloadGate.converge(...) — установить ENABLED/DISABLED protective postcondition и подтвердить его свежим наблюдением.
    @ordinary-side IP portal.<IP handoff> — passive bidirectional ordinary-side data-plane handoff.
    @VPN-side IP portal.<IP handoff> — passive bidirectional VPN-side data-plane handoff.

Residents

1. `@ManagedNetworkEnvironmentLifecycle` *Direct lifecycle Machinery базовой Private-network materialization: namespace + loopback; не владеет transition door или portal address/routing.*
2. `@OrdinarySidePortalLifecycle` *Direct lifecycle Machinery ordinary-side portal realization: stack-local identity и ordinary-side default на exact current private-facing transition endpoint.*
3. `@NetworkPolicyAdapter` *Semantic boundary между policy клиентов из STACK и lower realization/convergence внутри Private network.*
    1. `NetworkPolicyLayoutCalculator` *Детерминированно распределяет internal routing/RPDB/metric/nft resources между semantic owner scopes.*
    2. `NetworkPolicyEnforcer` *Достигает и подтверждает переданный Adapter'ом desired lower network-policy state.*
4. `@VPNPathAdapter` *Boundary fresh observation и verification concrete VPN endpoints уже присутствующих в Private network.*
5. `@ActiveProbeDriver` *Bounded lower execution одного активного probe через заранее подтвержденные probe-policy и endpoint facts.*
6. `@ForwardingGate` *Самостоятельный verified control корневого IPv4 forwarding barrier.*
    1. `ForwardingGateDriver` *Technical read/mutation boundary к managed-domain forwarding state.*
7. `@ProtectivePayloadGate` *Bounded Enforcer dedicated protective-mode containment: ordinary-boundary INPUT/OUTPUT и весь IPv4 FORWARD.*

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
8. `protective payload gate state` *(observed, managed)* — dedicated protective-mode containment state, отдельный от normal payload policy и structural `IPv4 forwarding state`.
9. `payload routing state` *(observed, managed)* — единый semantic lower state payload routing.
    1. `payload route state` *(observed, managed)*
    2. `payload RPDB state` *(observed, managed)*
10. `probe routing state` *(observed, managed)* — exact route+selector precondition path-specific probes.
    1. `probe route state` *(observed, managed)*
    2. `probe RPDB state` *(observed, managed)*
11. `nft policy scaffold` *(observed, managed)* — invariant owned nft table/base-chain structure, являющаяся prerequisite semantic policy owners, но не parent этих owners.
12. `Profile forwarding policy` *(observed, managed)*
13. `Device firewall policy` *(observed, managed)*
14. `payload NAT policy` *(observed, managed)*
15. `local publication policy` *(observed, managed)* — local INPUT/OUTPUT admission для Device publication внутри Private network.
16. `VPN integration local policy` *(observed, managed)* — bounded local transport admission, необходимая supported VPN integration.
17. `probe local admission policy` *(observed, managed)* — local policy, допускающая только exact probe execution/reply context.
18. `return-affinity state` *(observed, managed)* — общий postcondition association remote-initiated flow с исходным VPN routing domain.
    1. `return-affinity nft association/restore policy` *(observed, managed)*
    2. `return-affinity RPDB mark-dispatch state` *(observed, managed)*

`route-priority state` не является отдельным Artifact: priority machinery изменяет
свойства тех же `payload route state`. Аналогично readiness probe execution является
производным условием exact `probe routing state` + `probe local admission policy` +
current endpoint identity, а не самостоятельным `Probe IP transport` Artifact.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `STACK.@ProductLifecycleControl` | lifecycle preflight / ensure / destroy | `@ManagedNetworkEnvironmentLifecycle` |
| `@ManagedNetworkEnvironmentLifecycle` | observe/materialize/remove namespace + loopback | `managed network environment realization` |
| `STACK.@ProductLifecycleControl` | after transition establishment, observe/converge/cleanup portal realization | `@OrdinarySidePortalLifecycle` |
| `@OrdinarySidePortalLifecycle` | observe/converge/remove local service address | `stack-local IPv4 identity` |
| `@OrdinarySidePortalLifecycle` | observe/converge/remove ordinary-side default | `ordinary-side default routing state` |
| `@OrdinarySidePortalLifecycle` | requires exact current private-side transition endpoint | `Ordinary-side transition.@managed L3 boundary realization.<private-side IP handoff>` |
| `Ordinary-side transition.@managed L3 boundary realization.<private-side IP handoff>` | bidirectional IP handoff | `@ordinary-side IP portal.<IP handoff>` |
| `@ordinary-side IP portal.<IP handoff>` | ordinary→VPN payload is constrained by Profile forwarding, Device firewall, payload NAT and payload routing state | `@VPN-side IP portal.<IP handoff>` |
| `@VPN-side IP portal.<IP handoff>` | VPN→ordinary payload is constrained by Profile forwarding, Device firewall and payload routing; return-affinity preserves the selected routing domain where required | `@ordinary-side IP portal.<IP handoff>` |
| `VPN integration local policy` | bounds supported VPN underlay/control traffic using the ordinary-side handoff | `@ordinary-side IP portal.<IP handoff>` |
| `@ordinary-side IP portal.<IP handoff>` | DNAT-targeted local publication traffic is admitted only by exact local publication policy | `stack-local IPv4 identity` |
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
| `STACK.@ProtectiveModeManager` | observe/converge dedicated protective containment | `@ProtectivePayloadGate` |
| `@ProtectivePayloadGate` | own/verify | `protective payload gate state` |
| `@ForwardingGate` | technical read/mutation | `ForwardingGateDriver` |
| `ForwardingGateDriver` | read/write | `IPv4 forwarding state` |

Component diagram

```text
+----------------------------- STACK ------------------------------+
| lifecycle / policy / binding / probe clients                    |
+---------+--------------------+----------------------+------------+
          |                    |                      |
          v                    v                      v
+---------+--------------------------------------------------------+
|                         Private network                          |
|                                                                  |
| @ManagedNetworkEnvironmentLifecycle                             |
|      +--> [environment: namespace + loopback]                    |
| @OrdinarySidePortalLifecycle                                     |
|      +--> [stack-local identity] [ordinary default]              |
|                                                                  |
| @NetworkPolicyAdapter --> NetworkPolicyEnforcer                  |
|      |                    +--> [payload routing + nft policies]   |
|      +--> [probe routing]                                        |
|      +--> [nft scaffold]                                         |
|      +--> [return-affinity]                                      |
|                                                                  |
| @VPNPathAdapter -------> [VPN endpoint inventory]                |
| @ForwardingGate -------> ForwardingGateDriver -> [IPv4 forwarding]|
| @ProtectivePayloadGate -> [protective payload gate]               |
| @ActiveProbeDriver -------------------------------------+        |
|                                                        |        |
| @ordinary-side IP portal <==== managed payload =====> @VPN-side |
|          ^                    policy                    IP portal |
+----------|-----------------------------------------------|-------+
           |                                               |
           | IP                                            | IP
+----------+----------------+                   +----------+----------+
| Ordinary-side transition  |                   | VPN external ends   |
| @private-side IP handoff   |                   | @vpn-interface API  |
+----------------------------+                   +---------------------+
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
    @VPNChannel[].<path route realization> — integration-specific capability, которая для exact verified PathBinding дает допустимую current Linux route shape (endpoint/gateway/onlink) без generic inference.

Residents

1. `@VPNChannel[]` *Administrator-provisioned VPN integration instance. В Release 1 supported OpenVPN/systemd shape использует отдельный stack-specific service, policy-neutral VPN configuration и создает current VPN data-plane endpoint внутри managed network domain.*

Artifacts

1. `VPN-specific configuration` — administrator-owned protocol configuration; VPN-GATE не переписывает и не превращает ее в Device/Profile policy.
2. `VPN channel runtime/session state` — external VPN implementation state, включая process/cgroup/session lifecycle. Для supported Release-1 service им управляет systemd, а не VPN-GATE process supervisor.
3. `VPN endpoint generation` *(observed by VPN-GATE)* — current concrete interface generation, которую channel предоставляет в `Private network`; identity включает фактическую interface generation и не наследуется same-name replacement автоматически.
4. `remote path availability property` *(observed)* — внешнее сетевое свойство, которое активные checks пытаются наблюдать относительно configured normalized criterion/target; VPN-GATE его не актуирует.
5. `transport endpoint provenance` *(optional, observed)* — доказанный integration-specific transport fact exact current channel generation; не выводится из interface name/peer/ambient routes.
6. `path route-realization capability` — integration-specific available capability/contract, связывающая exact verified PathBinding с route next-hop semantics. Для доказанной direct-device integration результат имеет `gateway=none`, `onlink=false`, `dev=current endpoint`; эта форма не переносится автоматически на другие integrations.

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
| `Private network.@NetworkPolicyAdapter` | consume exact route realization for an already verified binding; never infer gateway/onlink generically | `@VPNChannel[].<path route realization>` |
| `@VPNChannel[].<vpn-interface endpoint>` | bidirectional tunneled IP handoff | `Private network.@VPN-side IP portal.<IP handoff>` |
| `@VPNChannel[]` | VPN underlay IP exits/enters ordinary side | `Private network.@ordinary-side IP portal.<IP handoff>` |
| `STACK.AvailabilityProbeAgent` via `Private network.@ActiveProbeDriver` | configured active observation | `remote path availability property` |
| `Ambient host and external world.@systemd` | supported deployment stop removes bound process/cgroup and endpoint before managed-domain teardown | `VPN channel runtime/session state` / `VPN endpoint generation` |

Release-1 support boundary: OpenVPN/systemd является текущим evidence-backed onboarding
mechanism. Дополнительная VPN technology не считается supported только из-за похожего
interface shape; ее integration contract требует отдельного applicability evidence либо
reviewed equivalence. Physical placement process/interface внутри managed netns при этом не
переносит VPN-specific configuration/session ownership в `Private network`.

Component diagram

```text
+---------------- Operator ----------------+   +------ Ambient host ------+
| VPN-specific provisioning               |   | @systemd lifecycle API  |
+----------------+-------------------------+   +------------+-------------+
                 |                                          |
                 v                                          v
+----------------+-------------------------------------------------------+
|                          VPN external ends                              |
|                                                                         |
| @VPNChannel[]                                                           |
|      +--> [VPN-specific configuration]                                  |
|      +--> [VPN runtime/session state]                                   |
|      +--> [remote availability property]                                |
|      |                                                                  |
|      +---- @<vpn-interface endpoint> ------------------+                 |
|      +---- @<transport provenance>                     |                 |
|      +---- @<path route realization>                   |                 |
+--------------------------------------------------------|----------------+
                                                         | tunneled IP
                                                         v
+--------------------------------------------------------+----------------+
| Private network  [ @VPN-side IP handoff / @VPNPathAdapter / probe API ]|
+-------------------------------------------------------------------------+
```

# VPN-GATE-managed host state

Явно owned часть ordinary-host network state. Этот Space существует потому, что VPN-GATE
имеет ограниченные host-side postconditions, которые нельзя ни прятать внутрь
`Private network`, ни смешивать с administrator-owned ambient host. В Release 1 здесь
сосуществуют два owner scope: обязательная при запрошенной server publication host mapping
и optional peaceful host-routing contribution. Отдельный явно включаемый aggressive owner
scope определен архитектурой, но ограничен из Release 1 требованием `VPNG-U001-R5.R2.C1`.

API

    @HostPublicationAdapter.observe(...) — fresh observation отдельного host-publication owner scope.
    @HostPublicationAdapter.apply(...) — converge desired host publication mappings и fresh verify.
    @HostPublicationAdapter.cleanup(...) — удалить только owned host-publication objects и подтвердить отсутствие.
    @HostRoutingContribution.converge(∅) — установить complete lifecycle-scoped peaceful host-routing contribution.
    @HostRoutingContribution.cleanup(∅) — удалить только still-identifiable owned contribution.
    @AggressiveHostRoutingManager.activate(...) — установить и подтвердить initial aggressive postcondition и начать continuous ownership.
    @AggressiveHostRoutingManager.deactivate(∅) — прекратить continuous ownership, безопасно снять routing capture и затем escape protection.
    @AggressiveHostRoutingManager.current_state(∅) — вернуть current confirmed / degraded / problem projection.
    @host publication mapping state.<selected publication traffic> — passive host-side mapping point для explicitly selected publication surface.
    @peaceful host routing contribution.<selected host traffic> — passive dispatch point optional helper scope.

Residents

1. `@HostPublicationAdapter` *Самостоятельный semantic Adapter host-side Device publication mapping; он потребляет тот же normalized publication intent, но не является occurrence `Private network.NetworkPolicyAdapter`.*
2. `@HostRoutingContribution` *Direct lifecycle Machinery optional peaceful helper. Current Release-1 realization — `LinuxPeacefulHostRoutingContribution`; continuous host-routing supervision отсутствует.*
3. `@AggressiveHostRoutingManager` *Manager continuous ownership явно включенной aggressive host-routing области.*
    1. `AggressiveHostRoutingEnforcer` *Bounded Enforcer составного postcondition: managed delivery подтверждена, non-managed escape запрещен.*

Artifacts

1. `host publication mapping state` *(observed, managed)* — отдельный ownership-marked host DNAT/publication scope, переводящий только явно выбранную local host publication surface в current stack-local publication target.
2. `peaceful host routing contribution` *(observed, managed)* — complete lifecycle-scoped host-routing state для выбранного helper traffic scope.
    1. `helper destination route state` *(observed, managed)* — remote Profile destinations и при необходимости Profile-SNAT identity routes в dedicated helper table.
    2. `helper dispatch RPDB state` *(observed, managed)* — selector-scoped preserve-main + helper lookup pairs и absolute managed-boundary bypass.
3. `aggressive host-routing state` *(observed, managed)* — current desired/confirmed/problem projection continuous aggressive owner.
    1. `aggressive routing state` *(observed, managed)* — owned route/RPDB realization требуемой managed delivery.
    2. `aggressive escape-protection state` *(observed, managed)* — independently verifiable fail-closed state, запрещающий managed scope уйти через non-managed egress.

Эти Artifacts не являются children общего «host networking» Artifact: у них разные semantic
owners, lifecycle и postconditions. Общая Linux namespace лишь physical container.

Не принадлежат этому Space:

- host-global IPv4 forwarding;
- foreign/admin routing, RPDB, nft firewall/NAT;
- ordinary host interface/address lifecycle;
- managed L3 door itself — `Ordinary-side transition`.

Interactions

| From | Interaction | To |
| --- | --- | --- |
| `STACK.@ProductLifecycleControl` / runtime policy assembly | after exact managed local admission, apply desired Device publication mapping | `@HostPublicationAdapter` |
| `@HostPublicationAdapter` | observe/converge/cleanup distinct owner scope | `host publication mapping state` |
| `@HostPublicationAdapter` | observe host forwarding/interface/address prerequisites without ownership | `Ambient host and external world.@OrdinaryHostNetwork.<host network observation>` |
| `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` | inbound traffic to selected local publication surface | `@host publication mapping state.<selected publication traffic>` |
| `host publication mapping state` | DNAT toward current stack-local service/publication identity through managed boundary | `Ordinary-side transition.@managed L3 boundary realization.<host-side IP handoff>` |
| `STACK.@ProductLifecycleControl` | build/converge enabled helper contribution | `@HostRoutingContribution` |
| `@HostRoutingContribution` | converge/cleanup | `peaceful host routing contribution` |
| `STACK.@ProductLifecycleControl` | activate/deactivate configured aggressive helper against current managed-boundary generation | `@AggressiveHostRoutingManager` |
| `@AggressiveHostRoutingManager` | bounded converge/verify current desired aggressive state | `AggressiveHostRoutingEnforcer` |
| `AggressiveHostRoutingEnforcer` | converge/verify owned routing + escape-protection state | `aggressive host-routing state` |
| `AggressiveHostRoutingEnforcer` | observe effective host routing facts without ownership | `Ambient host and external world.@OrdinaryHostNetwork.<host network observation>` |
| `@AggressiveHostRoutingManager` | request global protective mode after unrecoverable/unconfirmed local guarantee | `STACK.@ProtectiveModeManager` |
| `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` | selected host traffic enters helper-owned RPDB scope | `@peaceful host routing contribution.<selected host traffic>` |
| `peaceful host routing contribution` | route selected traffic to explicit managed host endpoint | `Ordinary-side transition.@managed L3 boundary realization.<host-side IP handoff>` |
| `Ordinary-side transition.@managed L3 boundary realization.<host-side IP handoff>` | traffic emitted from Private network bypasses helper recapture and resumes ordinary host routing | `Ambient host and external world.@OrdinaryHostNetwork.<IP handoff>` |

Publication machinery may observe host-global forwarding as an external prerequisite and
report publication unready, but current ownership does not authorize enabling it. Peaceful
host routing is lifecycle-scoped: Release 1 owns start/update/stop contribution only;
administrator changes between lifecycle operations are not helper drift and do not justify a
Manager.

Component diagram

```text
+---------------------------- STACK --------------------------------+
| runtime policy assembly              @ProductLifecycleControl     |
+-----------+-----------------------------------+--------------------+
            | publication mapping               | helper lifecycle
            v                                   v
+-----------+--------------------------------------------------------+
|                  VPN-GATE-managed host state                       |
|                                                                    |
| @HostPublicationAdapter      @HostRoutingContribution              |
| @AggressiveHostRoutingManager -> AggressiveHostRoutingEnforcer      |
|              |                                |                    |
|              v                                v                    |
| [host publication mapping]      [peaceful host routing contribution]|
|                                  [aggressive routing + escape state] |
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
| `VPN-GATE-managed host state.@HostPublicationAdapter` | observe forwarding/interface/address prerequisites only | `@OrdinaryHostNetwork` |
| `Operator.OperatorClient` | create/change external configuration representation | `@ExternalConfigurationSource` |
| `@ExternalConfigurationSource` | candidate representation | `STACK.@ConfigurationAdapter` |
| `Operator.OperatorClient` | start/stop/restart controller deployment | `@systemd` |
| `@systemd` | invoke/contain controller service lifecycle and wait for readiness semantics | `STACK.@ProductLifecycleControl` |
| `Operator.OperatorClient` | start/stop/restart supported stack-specific VPN service | `@systemd` |
| `@systemd` | supervise explicitly bound VPN process/cgroup | `VPN external ends.@VPNChannel[]` |
| `@systemd` | reverse dependency/order stops the bound VPN unit before controller final managed-domain teardown | `VPN external ends.@VPNChannel[]` / `STACK.@ProductLifecycleControl` |

Этот Space намеренно остается широким: ordinary host и внешний ordinary IP world не
разделяются только из-за количества Linux/network objects. Новая boundary потребуется лишь
при появлении самостоятельной VPN-GATE-visible/managed semantics, которой нужен собственный
контракт.

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
| `OperatorClient` / authorized automation | request protective active / inactive and inspect current mode result | `STACK.@ProtectiveModeManager` |
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
|    | config             | lifecycle/protective control | VPN onboarding |
|    |                    |                           |                |
|    +--------------------+---------------------------+------------+   |
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



# Annex A. STACK components

## [A.001] ProductLifecycleControl

Direct procedural Machinery, coordinating independent lifecycle operations and their dependency
order without merging their ownership or cleanup into one technical method. It does not
introduce a long-lived lifecycle Engine or independent lifecycle policy.

**Implements:**
- `VPNG-U004-R4.R4` — [`full`]
- `VPNG-U004-R4.R5` — [`full`]
- `VPNG-M001-R1` — [`full`]
- `VPNG-M001-R1.R1` — [`full`]
- `VPNG-M001-R1.R1.R1` — [`full`]
- `VPNG-M001-R1.R1.R3` — [`full`]
- `VPNG-M001-R1.R1.R4` — [`full`]
- `VPNG-M001-R1.R1.R5` — [`full`]
- `VPNG-M001-R1.R1.R6` — [`full`]
- `VPNG-M001-R1.R1.R6.R1` — [`full`]
- `VPNG-M001-R1.R1.R6.R2` — [`full`]
- `VPNG-M001-R1.R1.R6.R3` — [`full`]
- `VPNG-M001-R2.R1.R3` — [`full`]
- `VPNG-M001-R2.R1.R4` — [`full`]
- `VPNG-M001-R2.R1.R5` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]

**Constrained by:**
- `VPNG-M001-R1.R1.C1`

Implementation

    design/NG3/code/python/rou/controller_startup.py — current bounded ordering of stack/transition/policy startup operations.
    design/NG3/code/python/rou/controller_stop.py — current bounded ordering of independent cleanup operations.
    design/NG3/code/python/rou/controller_restart.py — stop-then-start composition without hidden resume state.
    design/NG3/code/python/rou/alpha_runtime.py — daemon/bootstrap composition, host helpers/publication and final systemd readiness/termination boundary.

**Evidence:** `EV-00000`

API

    @start(...) — выполнить product startup через независимые lifecycle operations с соблюдением dependency order.
    @stop(...) — выполнить product shutdown, пытаясь очистить независимые areas отдельно и удерживая основной процесс до teardown STACK.
    @restart(...) — stop + новый start из authoritative post-stop state.
    @reload(...) — optional management operation; если surface ее предоставляет, она не может молча означать restart.

Architectural decisions

1. `Procedural coordinator, not lifecycle monolith`
   *Product lifecycle задает partial order независимых операций, но не превращает bootstrap, STACK, ordinary-side transition и host helpers в один общий lifecycle object или один cleanup method.*

2. `Startup dependency order`
   *Bootstrap получает ownership/validated intent; базовая materialization STACK должна существовать до ordinary-side transition. Зависимые host-side exposure/helper operations выполняются только после их prerequisites.*

3. `Shutdown dependency order`
   *Ordinary-side transition и независимые host helpers/exposure могут быть погашены раньше STACK и не обязаны очищаться одним методом. Основной daemon process не завершается, пока teardown STACK не завершен либо не получен явный failure outcome: иначе живущие в STACK VPN-процессы могут остаться без управляющей среды.*

4. `Independent cleanup attempts`
   *Failure одной cleanup area не отменяет bounded attempts других independent owned domains. Success соответствующей операции требует свежего подтверждения ее собственного postcondition.*

5. `Intermediate statuses are local contracts`
   *Имена промежуточных состояний (`done`, `complete` и т.п.) не являются compatibility boundary alpha. Они могут меняться вместе с декомпозицией; сохраняться должны ordering, ownership, safety и final product-operation semantics.*

6. `Single-controller ownership`
   *Lifecycle удерживает один hardened lifetime ownership token/session. Startup, interrupted cleanup и stop не могут обходить этот ownership contract.*

7. `Restart adds no mechanism`
   *Restart не сохраняет скрытый cross-stop token, command journal или resume state; после подтвержденного stop обычный start заново получает ownership и строит state из fresh reality.*

8. `Replaceable control surface`
   *CLI/systemd/socket/API являются deployment mechanisms вне component semantics. Alpha вправе не иметь distinct reload, если changed configuration применяется поддержанным restart path.*

## [A.002] ConfigurationAdapter

Direct Adapter между внешним configuration representation и validated normalized domain
intents. Он является единственной границей, где human-facing grammar превращается в
semantic Device/Profile/binding/policy/availability contracts.

**Implements:**
- `VPNG-U001-R4.R1` — [`full`]
- `VPNG-U001-R4.R2` — [`full`]
- `VPNG-U001-R4.R3` — [`full`]
- `VPNG-U001-R4.R4` — [`full`]
- `VPNG-U001-R4.R5` — [`full`]
- `VPNG-U001-R4.R4.R6.R2.R1` — [`full`]
- `VPNG-U001-R4.R4.R6.R2.R5` — [`full`]
- `VPNG-U001-R4.R4.R6.R3` — [`full`]
- `VPNG-U001-R4.R4.R6.R4` — [`full`]
- `VPNG-U001-R1.R3.C1.R1` — [`full`]
- `VPNG-U002-R2.R1` — [`full`]
- `VPNG-U002-R2.R2` — [`full`]
- `VPNG-U002-R2.R3` — [`full`]
- `VPNG-U002-R2.R4` — [`full`]
- `VPNG-U002-R2.R5` — [`full`]
- `VPNG-U004-R4.R1` — [`full`]
- `VPNG-D001-R1.R1.R3.R1` — [`full`]
- `VPNG-D001-R1.R1.R3.R2` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

API

    @normalize(...) — строго распарсить/валидировать candidate representation и вернуть explicit normalized domain intents либо rejection без dependent network mutation.

Architectural decisions

1. `Declarative boundary`
   *Пользователь задает product intent, а не Linux operation recipe. Route metrics, tables, ifindex, RPDB priorities и другие lower realization values не являются input configuration.*

2. `No global mutable config object`
   *Adapter выпускает несколько explicit normalized contracts — Device, Profile, binding, policy, availability — вместо общего runtime configuration singleton.*

3. `Strict canonical parsing`
   *Unknown/ambiguous/contradictory active configuration отклоняется. Lower components не парсят повторно human strings и не repair'ят их молча.*

4. `Disabled placeholders are not active objects`
   *Known disabled Device/Profile может существовать без полной active semantic completeness; operational consumers работают только с normalized active demand.*

5. `Policy-owner separation`
   *Device transport policy, Profile payload policy, publication, VPN integration transport permission и availability selection остаются разными normalized owner classes, даже если исходно находятся рядом в TOML.*

6. `No topology guessing`
   *Concrete paths появляются только после accepted binding; availability target и integration realization не выводятся из случайных interface/route facts на configuration boundary.*

7. `Rule-local path selector`
   *Device firewall rule имеет ровно один из трёх scopes: без `via` — все current paths Device; `via if <exact-ifname>` — current path этого Device с указанным exact interface name; `via peer <IPv4>` — current P2P path этого Device с указанным verified private/inner peer. Два вида `via` взаимоисключающи и не создают отдельного user-facing path object; peer не означает external VPN transport endpoint или payload address.*


## [A.003] AvailabilityDescriptionResolver

Pure Calculator, превращающий Profile selection и соответствующий Device default в один
конкретный subject-scoped availability description до runtime observation.

**Implements:**
- `VPNG-U003-R3.R6.R1` — [`full`]
- `VPNG-U003-R3.R6.R3.R1` — [`full`]
- `VPNG-U003-R3.R6.R3.R1.R1` — [`full`]
- `VPNG-U003-R3.R6.R3.R1.R1.R1` — [`full`]
- `VPNG-U003-R3.R6.R3.R1.R1.R2` — [`full`]
- `VPNG-U003-R3.R6.R3.R1.R1.R3` — [`full`]
- `VPNG-U003-R3.R6.R3.R1.R1.R4` — [`full`]
- `VPNG-U003-R3.R6.R3.R2` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R3.R1` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

**Constrained by:**
- `VPNG-U003-R3.R6.R3.R1.C2`

API

    resolve_description(subject, profile_selection, device_default?) — вернуть concrete AvailabilityProbeDescription, disabled либо invalid.

Architectural decisions

1. `Subject scope`
   *Identity проверки — `(Profile, logical path)`. Использование Device default копирует description, но не создает Device-global availability state/evidence.*

2. `Concrete runtime input`
   *Release-1 runtime получает уже разрешенные `ICMP + exact IPv4 target`; выбор default/override не переносится в probe execution.*

3. `Pure semantic projection`
   *Calculator не наблюдает interfaces/peers/routes, не выполняет probe и не хранит runtime state.*

4. `Missing selected default is invalid`
   *Если Profile явно требует Device default, а соответствующего валидного description нет, candidate configuration отклоняется до runtime materialization.*


## [A.004] PayloadTrafficManager

Manager текущей semantic payload-policy projection. Он объединяет structural membership,
baseline preference и bounded availability adaptation в одного writer'а effective payload
policy.

**Implements:**
- `VPNG-U001-R1.R1` — [`full`]
- `VPNG-U002-R2.R1` — [`full`]
- `VPNG-U002-R2.R2` — [`full`]
- `VPNG-U002-R2.R3` — [`full`]
- `VPNG-U002-R2.R4` — [`full`]
- `VPNG-U002-R2.R5` — [`full`]
- `VPNG-U003-R3.R1` — [`full`]
- `VPNG-U003-R3.R2` — [`full`]
- `VPNG-U003-R3.R3` — [`full`]
- `VPNG-U003-R3.R4` — [`full`]
- `VPNG-U003-R3.R5` — [`full`]
- `VPNG-U003-R3.R7` — [`full`]
- `VPNG-U004-R4` — [`full`]
- `VPNG-U004-R4.R1` — [`full`]
- `VPNG-U004-R4.R2` — [`full`]
- `VPNG-M001-R1.R1.R2` — [`full`]
- `VPNG-M001-R1.R1.R3` — [`full`]
- `VPNG-M001-R2.R1.R2` — [`full`]
- `VPNG-M001-R2.R1.R4` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]
- `VPNG-D001-R1.R1.R6` — [`full`]

API

    <accepted-intent / binding / availability Events> — обновить current semantic inputs.
    <payload projection InfoEvent> — опубликовать текущую подтвержденную semantic projection для observers.
    <reconciliation trigger> — fresh-observe dependent lower domains и при необходимости converge через Adapters.

Architectural decisions

1. `One effective-policy writer`
   *Path membership и priority adaptation принадлежат одному Manager. Их разделение на независимых Managers создало бы двух writers одной routing semantics и потребовало бы дополнительный transaction protocol.*

2. `Profile survives zero-path state`
   *Structural Profile intent остается current даже при `ordered_paths=[]`; disappearance bindings не удаляет fail-closed Profile domain.*

3. `Bounded availability state`
   *Для каждого subject сохраняются только current problem flag и bounded degradation/recovery progress. Unbounded evidence history/replay journal отсутствуют.*

4. `Availability is a priority modifier`
   *Evidence не создает membership, direction или permission. Problem paths остаются structurally present и перемещаются ниже usable paths в effective order.*

5. `Sticky current active path is Profile state`
   *Current active path удерживается только для route-level failback semantics. Это не flow/session affinity и не conntrack ownership.*

6. `Fresh reconciliation`
   *Manager хранит accepted desired semantics и при audit/event заново наблюдает reality; failed lower command sequence не ставится в durable retry queue и не replay'ится вслепую.*

7. `Binding generation matters`
   *Logical path связывается с current concrete endpoint generation; same ifname/new ifindex означает новый binding context и инвалидирует зависимые current facts.*


## [A.005] PayloadPolicyCalculator

Pure Calculator structural payload semantics. Он строит allowed traffic/path policy из
normalized Profile/Device intent и уже подтвержденных current bindings, не наблюдая Linux.

**Implements:**
- `VPNG-U001-R1.R4.R2.R1` — [`full`]
- `VPNG-U001-R1.R4.R2.R1.R1` — [`full`]
- `VPNG-U002-R2.R1` — [`full`]
- `VPNG-U002-R2.R1.R1` — [`full`]
- `VPNG-U002-R2.R1.R2` — [`full`]
- `VPNG-U002-R2.R2` — [`full`]
- `VPNG-U002-R2.R2.R1` — [`full`]
- `VPNG-U002-R2.R3` — [`full`]
- `VPNG-U002-R2.R3.R3` — [`full`]
- `VPNG-U002-R2.R4` — [`full`]
- `VPNG-U002-R2.R5` — [`full`]
- `VPNG-U002-R2.R5.R1` — [`full`]
- `VPNG-D001-R1.R1.R3.R1` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

API

    calculate(normalized_intent, current_bindings) — вернуть complete structural payload policy без I/O и runtime history.

Architectural decisions

1. `Pure structural policy`
   *Calculator определяет membership/direction/permission, но не availability ordering, Linux resource IDs или convergence steps.*

2. `Profile independence`
   *Каждый enabled Profile сохраняет собственную policy domain и destination ownership даже при отсутствии usable paths.*

3. `Device policy can only narrow`
   *Device firewall/transport policy не расширяет destinations, directions или path eligibility, заданные Profile semantics.*

4. `First-release inbound capacity`
   *Для inbound/bidirectional Profile применяется принятый Release-1 path-capacity constraint; это semantic validation, а не свойство конкретной route implementation.*

5. `Flow stability is separate`
   *Established-flow return affinity и outbound no-unnecessary-failback не выводятся из случайной route affinity: Calculator предоставляет structural intent, а соответствующие runtime/lower mechanisms остаются отдельными owners.*

6. `Path-relative Device-rule applicability`
   *Ordered Device firewall intent может содержать не более одного rule-local path predicate. Rule без predicate применим ко всем current paths Device; `via if` применим только к current path с соответствующим exact ifname; `via peer` — только к current path с соответствующим verified private/inner peer fact. Это изменяет только область применимости rule и не создаёт Profile membership, destination или path eligibility.*


## [A.006] AvailabilityPriorityCalculator

Pure Calculator effective path order из current structural membership, baseline order,
Profile-local reserve roles, established availability problems и current active path.

**Implements:**
- `VPNG-U003-R3.R1` — [`full`]
- `VPNG-U003-R3.R2` — [`full`]
- `VPNG-U003-R3.R3` — [`full`]
- `VPNG-U003-R3.R4` — [`full`]
- `VPNG-U003-R3.R4.R1` — [`full`]
- `VPNG-U003-R3.R4.R1.R1` — [`full`]
- `VPNG-U003-R3.R7` — [`full`]
- `VPNG-U003-R3.R8` — [`full`]
- `VPNG-U003-R3.R8.R1` — [`full`]
- `VPNG-U003-R3.R8.C1` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

API

    calculate(current_membership, baseline_order, reserve_roles, problems, current_active_path) — вернуть deterministic effective order и next active-path projection.

Architectural decisions

1. `No membership authority`
   *Calculator только упорядочивает уже allowed current paths; он не создает/удаляет policy membership.*

2. `Negative adaptation`
   *Availability problem понижает path относительно usable paths, но сохраняет его structural presence.*

3. `No unnecessary failback`
   *Healthy ordinary active path остается первым после recovery другого path. Reserve active path является explicit exception: более высокий baseline usable path может его preempt.*

4. `Deterministic and pure`
   *Одинаковый current input дает один результат; timers, probes, Linux metrics и hidden history не входят в Calculator.*


## [A.007] AvailabilityProbeAgent

Agent ongoing availability observation. Он управляет расписанием/контекстом observation и
публикует normalized evidence, но не управляет наблюдаемым remote availability property.

**Implements:**
- `VPNG-U003-R3.R6` — [`full`]
- `VPNG-U003-R3.R6.R1` — [`full`]
- `VPNG-U003-R3.R6.R2` — [`full`]
- `VPNG-U003-R3.R6.R3` — [`full`]
- `VPNG-U003-R3.R6.R3.R1` — [`full`]
- `VPNG-M001-R2.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

API

    <intent/binding synchronization> — заменить current requested subjects/contexts.
    <timer or explicit observation trigger> — попытаться выполнить bounded current observation.
    <AvailabilityEvidence InfoEvent> — опубликовать positive / negative / no_evidence для exact current subject/context.

Architectural decisions

1. `Agent, not Manager`
   *Agent не может сделать remote path healthy/unhealthy; он только организует observation и публикует evidence.*

2. `Generation-scoped context`
   *Observation context включает exact current logical path/endpoint generation. Evidence от superseded context не влияет на current semantic state.*

3. `No local-failure fabrication`
   *Local execution/precondition failure возвращает `no_evidence`, если он сам не доказывает remote path failure.*

4. `Configured criterion only`
   *Mechanism/target приходят из concrete normalized description; Agent не выводит target из interface peer, routing или transport topology.*

5. `Bounded scheduling state`
   *Timers, current generation tokens и bounded in-flight diagnostics допустимы; unbounded observation history и durable retry journal не требуются.*


## [A.008] RuntimeStatusAgent

Agent, составляющий truthful current user-facing status из authoritative current projections
других owners. Он не актуирует представляемые domains и не становится system-of-record.

**Implements:**
- `VPNG-M001-R2.R1` — [`full`]
- `VPNG-M001-R2.R1.R1` — [`full`]
- `VPNG-M001-R2.R1.R2` — [`full`]
- `VPNG-M001-R2.R1.R3` — [`full`]
- `VPNG-M001-R2.R1.R4` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R3.R1` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]
- `VPNG-D001-R3.R1.R1` — [`full`]

**Пробел материализации:** версия в поддерживаемом представлении текущего состояния еще не материализована; до подготовки первого фактического выпуска это допускает `VPNG-D001-R3.C1`.

API

    <current owner-snapshot InfoEvents> — принять latest authoritative projection каждого owner.
    @<current snapshot publication> — опубликовать RuntimeStatusSnapshot для replaceable presentation surface.

Architectural decisions

1. `Truthful composition`
   *Desired/configured value не превращается в confirmed actual без authoritative confirmation. Missing/stale/conflicting input становится unknown/unconfirmed/problem.*

2. `Current-only state`
   *Agent хранит только latest relevant snapshot per source. Event history, transition reconstruction и durable status journal отсутствуют.*

3. `Owners retain semantic truth`
   *StatusAgent не знает kernel commands и не переопределяет verdict владельца domain; он только соединяет current projections.*

4. `Snapshot/presentation split`
   *Agent contract заканчивается на truthful RuntimeStatusSnapshot. Обязательный compact text является отдельным pure Calculator contract, а конкретный CLI/file/API transport остаётся presentation machinery.*

5. `Change-driven publication`
   *Periodic observation/reconciliation может повторно получить семантически тот же RuntimeStatusSnapshot, но presentation publication boundary не создает новый publication event и не переписывает current surfaces, пока snapshot равен последнему успешно опубликованному. После semantic change новый snapshot публикуется; failed publication не считается принятым baseline для дедупликации.*

6. `No hidden Profile verdict model`
   *Более сильный aggregated ProfileState не вводится без отдельного requirement; current status достаточно truthful composition существующих owner projections.*

## [A.009] RuntimeStatusTextRenderer

Direct Calculator, преобразующий один authoritative `RuntimeStatusSnapshot` в compact
human-readable current-state report. Он не наблюдает kernel state, не хранит историю, не
изменяет status semantics и не является configuration serializer.

**Implements:**
- `VPNG-M001-R2.R2` — [`full`]
- `VPNG-M001-R2.R2.R1` — [`full`]
- `VPNG-M001-R2.R2.R2` — [`full`]
- `VPNG-M001-R2.R2.R3` — [`full`]
- `VPNG-M001-R2.R2.R4` — [`full`]

API

    render(snapshot) -> text

Architectural decisions

1. `One authoritative snapshot`
   *Renderer использует только RuntimeStatusSnapshot и не реконструирует состояние из kernel/logs.*

2. `Stable human shape, replaceable delivery`
   *Нормативны две секции Devices/Profiles, four-space nesting, Device rows, truthful `unknown` при неподтверждённом current state, numbered effective-order path rows и availability wording. CLI/file/API path не входит в этот semantic contract.*

3. `Not configuration`
   *Report не обязан round-trip в configuration parser и не представляет effective configuration dump.*

4. `No diagnostic overloading`
   *Compact rows показывают operator-level current state. Детальные lower diagnostics остаются в blocking diagnostics/logging surfaces и не расширяют row grammar автоматически.*

Implementation

    design/NG3/code/python/rou/runtime_status.py — pure text rendering from RuntimeStatusSnapshot plus atomic text publication.

## [A.010] OperationalLogAdapter

Direct Adapter, переводящий semantic operational records компонентов VPN-GATE в logging
facility текущего deployment. Он не является current-state owner, не заменяет
`RuntimeStatusAgent` и не является developer execution trace.

**Implements:**
- `VPNG-M001-R2.R3` — [`full`]
- `VPNG-M001-R2.R3.R1` — [`full`]
- `VPNG-M001-R2.R3.R2` — [`full`]
- `VPNG-M001-R2.R3.R2.R1` — [`full`]
- `VPNG-M001-R2.R3.R2.R2` — [`full`]
- `VPNG-M001-R2.R3.R2.R3` — [`full`]
- `VPNG-M001-R2.R3.R2.R4` — [`full`]
- `VPNG-M001-R2.R3.R3` — [`full`]
- `VPNG-M001-R2.R3.R4` — [`full`]
- `VPNG-M001-R2.R3.R5` — [`full`]
- `VPNG-M001-R2.R3.R6` — [`full`]
- `VPNG-M001-R2.R3.R6.C1` — [`full`]

API

    emit(level, component_tag, message, safe_context) -> emitted | suppressed

Architectural decisions

1. `Severity is product semantics`
   *Threshold ordering is DEBUG < INFO < WARNING < ERROR. Components classify records by the
   requirement semantics rather than by implementation convenience; the Adapter only filters
   records below the configured minimum.*

2. `Event/reaction split`
   *INFO describes material environment/lifecycle transitions; DEBUG describes component-level
   reaction or changed semantic desired/effective state. A periodic audit that observes no
   semantic transition emits neither an INFO copy nor a DEBUG reaction copy.*

3. `Component log identity`
   *Every component that emits attributed records owns one explicit implementation constant
   named `LOG_TAG`. All its attributed records use that value. The value is log-oriented and
   is not derived automatically from class/module/architecture names. Requirement constraint
   `VPNG-M001-R2.R3.R6.C1` limits the tag to six characters.*

4. `Safe context boundary`
   *Callers pass only diagnostic context already safe for operational disclosure. Credentials,
   key material and equivalent secret-bearing values are not valid operational-log context.
   The Adapter must not obtain secrets merely in order to redact them.*

5. `Human log, not stable machine protocol`
   *Release 1 requires operator-readable level/tag/context semantics, but exact punctuation,
   field ordering and journal transport metadata are replaceable presentation details unless a
   later requirement promotes them to a machine-consumed API.*

6. `Deployment boundary`
   *Current systemd alpha emits to its standard process stream captured by journald and prefixes
   the stream with the corresponding syslog priority so journal metadata preserves
   DEBUG/INFO/WARNING/ERROR filtering. That transport is alpha deployment machinery, not a
   requirement that all future deployments use systemd/journald.*

Implementation

    design/NG3/code/python/rou/operational_log.py — threshold/filter/format Direct Adapter.

Integration note

    Existing architecture-owned component modules declare their local LOG_TAG constants, and
    A.001 alpha composition emits semantic transitions/reactions through A.010. Those files
    retain their existing single architecture ownership in implementation-traceability; A.010
    does not claim them as duplicate implementation owners.


## [A.011] ProtectiveModeManager


Manager явного административного защитного режима. Он владеет source-scoped request set и
confirmed/problem состоянием public protective mode и непрерывно поддерживает gate, пока хотя
бы один авторизованный source сохраняет запрос защиты.

**Implements / supports:**
- `VPNG-U004-R5` — [`partial`]
- `VPNG-U004-R5.R1` — [`partial`]
- `VPNG-U004-R5.R2` — [`full`]
- `VPNG-U004-R5.R3` — [`full`]
- `VPNG-U004-R5.R4` — [`partial`]

**Пробелы материализации:**
- `VPNG-U004-R5` и `VPNG-U004-R5.R1`: отсутствует поддерживаемое подключение операторского/управляющего интерфейса к публичным операциям Manager;
- `VPNG-U004-R5.R4`: реализована однократная сверка и безопасный выход, но отсутствует периодический запуск сверки с требуемым конечным интервалом.

**Evidence:** EXP-083 lower containment evidence.

API

    @request_active(source, ...) — добавить/обновить запрос данного source и вернуть success только после fresh confirmation полного protective postcondition.
    @request_inactive(source, ...) — снять только запрос данного source; если другие sources остаются active, gate сохраняется; иначе подтвердить normal release precondition, снять gate и вернуть success только после final verification.
    @current_state(∅) — вернуть current request-source set и confirmed / problem projection.

Architectural decisions

1. `Independent public owner`
   *Protective mode не является побочным режимом aggressive helper или C.003 structural transition. Operator/automation и E.003 являются независимыми request sources, но gate и агрегированное состояние режима принадлежат этому Manager. Один source не может снять запрос другого.*

2. `Confirmed entry`
   *Принятие команды не означает active. Manager считает режим подтвержденным только после fresh exact C.010 protective-gate postcondition.*

3. `Continuous confirmation`
   *Пока requested intent active, Manager с конечной cadence начинает каждый audit из нового observation и восстанавливает C.010 state, если exact safe recovery возможно. Wakeup events могут ускорять audit, но не являются source of truth.*

4. `Safe leave`
   *C.010 gate может сниматься только когда source-scoped request set пуст. После этого Manager заново подтверждает применимое normal desired/binding/policy readiness по authoritative owner projections STACK. Failed validation или failed gate removal оставляют gate active и публикуют problem result. Optional aggressive recovery снимает только свой request source; его local escape protection остается ответственностью E.003/E.004 и не создает обратного synchronous вызова A.011 -> E.003.*

5. `State preservation`
   *Protective mode меняет отдельный containment Artifact и не использует teardown namespace/routes/interfaces/configuration intent как штатный способ остановки трафика.*

Implementation

    design/NG3/code/python/rou/protective_mode_manager.py — source-scoped Manager core, bounded C.010 composition, blocked-leave handling and safety re-containment attempt.

# Annex B. Ordinary-side transition components

## [B.001] ManagedL3BoundaryLifecycle

Direct lifecycle Machinery ordinary-side transition. Она материализует и проверяет exact
managed-L3 door между Private network и ordinary host, не принимая ownership
Private-network service identity/default route или traffic-selection policy соседних Spaces.

**Implements / supports:**
- `VPNG-U001-R1.R3.R2` — [`full`]
- `VPNG-U004-R4.R6` — [`full`]
- `VPNG-M001-R1.R1.R1` — [`full`]
- `VPNG-M001-R1.R1.R2` — [`full`]
- `VPNG-M001-R1.R1.R4` — [`full`]
- `VPNG-M001-R1.R1.R5` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R3.R3` — [`full`]
- `VPNG-D001-R1.R1.R7` — [`full`]

**Evidence:** `EV-00000`

API

    @preflight(...) — fresh-classify absent / established / conflict without creating transition.
    @ensure(...) — create absent transition, repair provable owned drift, or confirm exact existing realization.
    @destroy(...) — remove owned transition and fresh-confirm endpoint absence.

Architectural decisions

1. `Independent transition lifecycle`
   *Component owns only managed-L3 boundary realization. Namespace/loopback belong to `C.007`; local identity/default route belong to `C.009`.*

2. `Recoverable absent transition and owned drift`
   *Exact Private-network environment with no boundary is valid and may be completed by ensure. If transition identity/ownership is proven, divergent properties owned by this realization should be repaired and re-verified where repair is safely expressible. Host-side endpoint with no environment remains conflict because name alone is insufficient ownership evidence.*

3. `Transport-ready, not portal-ready`
   *Established confirms reciprocal endpoint/backend invariants and handoff endpoints. Private ordinary-side readiness additionally requires `OrdinarySidePortalLifecycle`.*

4. `Realization-specific door`
   *Release 1 uses routed veth + Proxy ARP; reciprocal identity, UP state, Proxy ARP/rp_filter and host-side service reachability belong to this realization. Property drift is repairable only after reciprocal identity/ownership is proven; ambiguous or foreign structure is not adopted. Alternate netkit L3 remains behind the same contract.*

5. `Physical placement does not move ownership`
   *Concrete endpoints may reside in host and managed namespaces; that does not transfer host routing policy or Private service/default ownership into transition.*

Implementation

    design/NG3/code/python/rou/managed_network_domain.py — decomposed boundary lifecycle functions and current routed-veth realization.
    design/NG3/code/python/rou/controller_startup.py — ProductLifecycleControl startup composition.
    design/NG3/code/python/rou/controller_stop.py — ProductLifecycleControl cleanup composition.

# Annex C. Private network components

## [C.001] NetworkPolicyAdapter

Adapter является shared boundary от owner-scoped semantic network policy клиентов STACK к
lower network-policy domain Private network. Общая physical realization не сливает
различные semantic owners.

**Implements:**
- `VPNG-U001-R1.R1` — [`full`]
- `VPNG-U001-R1.R3.R6.R2` — [`full`]
- `VPNG-U001-R1.R4.R2.R1` — [`full`]
- `VPNG-U001-R1.R4.R2.R1.R1` — [`full`]
- `VPNG-U001-R4.R4.R6.R2.R1` — [`full`]
- `VPNG-U001-R4.R4.R6.R2.R5` — [`full`]
- `VPNG-U004-R4.R2` — [`full`]
- `VPNG-U004-R4.R3` — [`full`]
- `VPNG-U004-R4.R5` — [`full`]
- `VPNG-M001-R1.R1.R2` — [`full`]
- `VPNG-M001-R1.R1.R3` — [`full`]
- `VPNG-M001-R1.R1.R4` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R3.R2` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

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
   *Один normalized Device publication intent требует двух independently verified postconditions: managed-domain local admission в `Private network` и host publication mapping в `VPN-GATE-managed host state`. Host-side occurrence того же semantic Adapter показывается в соседнем Space как отдельный `HostPublicationAdapter`; физическое размещение host nft state не расширяет ownership этого Private-network occurrence.*

8. `Path-scoped Device firewall lowering`
   *Для каждого current exact path Adapter сохраняет исходный порядок Device firewall rules и исключает только rules, чей optional selector не относится к этому path. Rule без selector остаётся Device-wide; `via if` сравнивается с уже текущим exact interface name path binding; `via peer` — с verified private-peer fact C.004. Explicit firewall остаётся одной ordered policy с terminal no-match DROP даже если после path filtering не осталось explicit rules; отдельный path-policy gate или второй user policy object не вводится.*

9. `Selector evidence is minimal and Device-scoped`
   *Exact-if selector использует только уже подтверждённый current PathBinding и не добавляет observation dependency. Peer selector разрешается только из verified current path facts C.004. Если `via peer` отсутствует во всех rules, peer observation вообще не является prerequisite policy realization. Если peer selector запрошен, confirmed absence другого peer является обычным non-match; observation failure либо неоднозначное совпадение requested peer не трактуется как отсутствие restriction и не разрешает allowing structural policy для затронутого Device.*

## [C.002] NetworkPolicyLayoutCalculator

Pure Calculator внутреннего resource layout.

**Implements:**
- `VPNG-U001-R1.R1` — [`full`]
- `VPNG-U003-R3.R6` — [`full`]
- `VPNG-U004-R4` — [`full`]
- `VPNG-U004-R4.R1` — [`full`]
- `VPNG-U004-R4.R2` — [`full`]
- `VPNG-U004-R4.R5` — [`full`]
- `VPNG-U004-R4.R6` — [`full`]
- `VPNG-M001-R1.R1.R2` — [`full`]
- `VPNG-M001-R1.R1.R4` — [`full`]
- `VPNG-M001-R1.R1.R5` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R3.R1` — [`full`]
- `VPNG-D001-R1.R1.R3.R2` — [`full`]
 Он получает semantic owner demand и injected
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

## [C.003] NetworkPolicyEnforcer

Enforcer отвечает только за достижение и подтверждение переданного desired state.
Он не является Space API: в дереве `Residents` его parent — `NetworkPolicyAdapter`,
а independently demanded safety/lifecycle API вынесен в sibling `@ForwardingGate`.

**Implements:**
- `VPNG-U004-R4.R2` — [`full`]
- `VPNG-U004-R4.R3` — [`full`]
- `VPNG-U003-R3.R9` — [`full`]
- `VPNG-U004-R4.R3.R2` — [`full`]
- `VPNG-U004-R4.R5` — [`full`]
- `VPNG-M001-R1.R1.R2` — [`full`]
- `VPNG-M001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

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


## [C.004] VPNPathAdapter

Adapter является boundary между logical VPN-path semantics и уже provisioned concrete VPN
endpoint внутри Private network. Он наблюдает/проверяет lower-domain facts, но не создает и
не управляет VPN session как таковой.

**Implements:**
- `VPNG-U001-R1.R3.R1` — [`full`]
- `VPNG-U001-R1.R4.R2.R1.R1` — [`full`]
- `VPNG-U001-R4.R4.R6.R2.R5` — [`full`]
- `VPNG-U001-R1.R3.R2` — [`full`]
- `VPNG-U001-R1.R3.R3` — [`full`]
- `VPNG-U001-R1.R3.R4` — [`full`]
- `VPNG-U001-R1.R3.R4.R1` — [`full`]
- `VPNG-U001-R1.R3.R4.R2` — [`full`]
- `VPNG-U001-R1.R3.R4.R3` — [`full`]
- `VPNG-U001-R1.R3.R4.R3.R1` — [`full`]
- `VPNG-U001-R1.R3.R4.R4` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

API

    @observe_device_endpoints(require_private_peer=false) — получить свежие candidate endpoints из Private network; при `require_private_peer=true` дополнительно получить confirmed private/inner P2P peer fact либо confirmed absence такого fact для exact endpoint generation.
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

7. `Exact-if selector consumes existing binding identity`
   *Rule-local `via if <exact-ifname>` не требует нового observation contract: applicability проверяется только после обычного Device binding по current exact `InterfaceIdentity(ifname, ifindex)`. Совпадение имени вне current paths этого Device не имеет значения.*

8. `Private P2P peer is a demand-scoped endpoint fact, not path identity`
   *Для current Linux point-to-point endpoint Adapter может fresh-observe inner/private peer IPv4 из interface address state и привязать его только к exact `(ifname, ifindex)` generation. Эта дополнительная observation требуется только когда accepted Device policy содержит `via peer`; конфигурация без такого selector сохраняет прежний link-only endpoint-observation contract. При запрошенной peer observation link/address snapshots должны быть взаимно совместимы; race/mismatch является observation failure. Peer fact не создаёт Device ownership: selector resolution выполняется только после обычного Device binding.*

9. `Inner peer is not transport provenance`
   *Private/inner point-to-point peer принципиально отличен от external VPN transport/server endpoint. EXP-039 подтверждает, что inner peer виден generic TUN address observation, тогда как userspace transport endpoint из него не выводится. Если supported integration отдельно доказывает transport provenance, он по-прежнему привязывается к exact current `PathBinding` и не подменяется inner peer.*

10. `Binding is not route realization`
   *`VPNPathAdapter` доказывает current concrete endpoint, но не угадывает Linux `gateway/onlink`. Exact route realization предоставляет отдельная capability supported integration contract в `VPN external ends`; generic `NetworkPolicyAdapter` только потребляет этот уже доказанный lower fact. Direct-device realization является одной explicit integration capability, а не универсальным свойством bound interface.*

## [C.005] ForwardingGate

Самостоятельный bounded Enforcer корневого IPv4 forwarding state Private network.

**Implements:**
- `VPNG-U004-R4.R2` — [`full`]
- `VPNG-U004-R4.R3.R2` — [`full`]
- `VPNG-U004-R4.R4` — [`full`]
- `VPNG-U004-R4.R5` — [`full`]
- `VPNG-U004-R4.R6` — [`full`]
 Его
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

## [C.006] ForwardingGateDriver

Технический Driver к managed-domain forwarding state.

**Supports implementation of:**
- `VPNG-U004-R4.R2` — [`full`]
- `VPNG-U004-R4.R3.R2` — [`full`]
- `VPNG-U004-R4.R4` — [`full`]
- `VPNG-U004-R4.R5` — [`full`]
- `VPNG-U004-R4.R6` — [`full`]

Сам по себе Driver не реализует semantic requirement postcondition: он предоставляет
technical read/write primitive для `ForwardingGate`, который выполняет fresh
observe/mutate/re-observe verification.
 В дереве `Residents` он является
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


## [C.007] ManagedNetworkEnvironmentLifecycle

Direct lifecycle Machinery базовой Linux-materialization Private network: named network
namespace + loopback. Она не материализует ordinary-side transition и не конфигурирует
stack-local address/default route.

**Implements / supports:**
- `VPNG-U004-R4.R6` — [`full`]
- `VPNG-M001-R1.R1.R1` — [`full`]
- `VPNG-M001-R1.R1.R2` — [`full`]
- `VPNG-M001-R1.R1.R4` — [`full`]
- `VPNG-M001-R1.R1.R5` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R7` — [`full`]

**Evidence:** `EV-00000`

API

    @preflight(...) — fresh-read namespace/loopback under protective containment; absent environment is valid.
    @ensure(...) — create absent namespace + loopback, repair provable owned drift, or confirm exact existing state.
    @destroy(...) — remove environment after dependent cleanup and fresh-confirm namespace absence.

Architectural decisions

1. `Space is not namespace`
   *Owned artifacts are namespace instance + loopback state. Absence of materialization does not remove the architectural Space.*

2. `Containment before trust`
   *Existing namespace is inspected only after fresh confirmed ForwardingGate=DISABLED. Once namespace ownership/identity is proven, owned environment properties such as loopback state should be repaired rather than rejected merely for drift.*

3. `Environment without door is valid`
   *Exact namespace/loopback with absent ordinary-side transition is a normal recoverable intermediate state.*

4. `No transition/portal ownership`
   *This component neither creates host-side boundary endpoints nor manages stack-local address/default routing.*

5. `Destroy is dependency-last`
   *Normal cleanup destroys environment only after portal/transition cleanup attempts. Namespace absence is a stronger final postcondition for all contained Private-network artifacts.*

Implementation

    design/NG3/code/python/rou/managed_network_domain.py — decomposed environment lifecycle functions.
    design/NG3/code/python/rou/controller_startup.py — ProductLifecycleControl startup composition.
    design/NG3/code/python/rou/controller_stop.py — ProductLifecycleControl cleanup composition.


## [C.008] ActiveProbeDriver

Technical Driver одного bounded physical availability attempt через exact current VPN path.
Он скрывает mechanism-specific execution от Agent и не владеет scheduling, confirmation или
remote availability semantics.

**Implements:**
- `VPNG-U003-R3.R6` — [`full`]
- `VPNG-U003-R3.R6.R1` — [`full`]
- `VPNG-U003-R3.R6.R3` — [`full`]
- `VPNG-U003-R3.R6.R3.R1` — [`full`]
- `VPNG-U003-R3.R6.R3.R1.R1` — [`full`]
- `VPNG-D001-R1.R1.R3.R2` — [`full`]
- `VPNG-D001-R1.R1.R5` — [`full`]

API

    @execute(current_path, mechanism, target, deadline) — выполнить один bounded attempt и вернуть reply / no_reply / local_error с bounded diagnostic.

Architectural decisions

1. `One attempt only`
   *Driver не планирует cadence, не повторяет попытку и не меняет availability state. Release-1 implementation выполняет один ICMP echo attempt.*

2. `Exact path execution`
   *Physical attempt привязан к current endpoint (`ping -I <current-ifname>` для Release 1) и запускается только после подтвержденного caller'ом probe execution precondition.*

3. `Technical result is not semantic evidence`
   *`reply/no_reply/local_error` — lower facts. Mapping в positive/negative/no_evidence и stale-context rejection принадлежат AvailabilityProbeAgent/execution gate.*

4. `Bounded failure`
   *Reply deadline и outer process grace являются finite lower runtime parameters. Spawn/timeout/other execution error не может оставить attempt indefinitely in flight.*

5. `Probe isolation, not conntrack freshness for its own sake`
   *Release 1 требует, чтобы probe-local state не выбирал/мигрировал payload routing и не восстанавливался как payload packet mark. Отдельный conntrack cleanup лишь ради новой technical identity каждой probe generation не является correctness prerequisite.*

6. `Portal boundary`
   *Driver отправляет/принимает probe IP через VPN-side IP portal; remote target и VPN endpoint остаются предметностью соседнего VPN external ends / local endpoint inventory, а не становятся child artifacts Driver.*


## [C.009] OrdinarySidePortalLifecycle

Direct lifecycle Machinery Private-network ordinary-side portal realization. Работает после
established `ManagedL3BoundaryLifecycle` и владеет exact stack-local IPv4 identity +
ordinary-side default routing state на current private-facing endpoint.

**Implements / supports:**
- `VPNG-U004-R4.R6` — [`full`]
- `VPNG-M001-R1.R1.R1` — [`full`]
- `VPNG-M001-R1.R1.R2` — [`full`]
- `VPNG-M001-R1.R1.R4` — [`full`]
- `VPNG-M001-R1.R1.R5` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R7` — [`full`]

**Evidence:** `EV-00000`

API

    @observe(...) — fresh-observe owned address/default-route state on exact current private-facing endpoint.
    @ensure(...) — converge exact owned portal state and fresh-verify it.
    @cleanup(...) — remove owned portal state and fresh-confirm absence when endpoint exists.

Architectural decisions

1. `Transition dependency, not ownership`
   *Lifecycle requires an exact current private-facing transition endpoint but does not create/delete that transition.*

2. `Authoritative exclusive portal convergence`
   *Dedicated private-facing endpoint is an exclusive realization of this portal, not a shared architectural object. Its IPv4/default-route contents are therefore exact owned state: extra or missing state is repairable drift, and whole-scope flush/rebuild is permitted for this endpoint.*

3. `Cleanup before door removal`
   *Normal stop removes portal state before destroying transition. If later transition removal proves endpoint absence, that stronger postcondition proves portal artifacts cannot remain active.*

4. `No generic routing role`
   *Payload/Profile routes remain NetworkPolicyAdapter artifacts; this lifecycle owns only stack-local identity and ordinary-side default.*

Implementation

    design/NG3/code/python/rou/managed_network_domain.py — decomposed portal lifecycle functions/current Linux realization.
    design/NG3/code/python/rou/controller_startup.py — ProductLifecycleControl startup composition.
    design/NG3/code/python/rou/controller_stop.py — ProductLifecycleControl cleanup composition.


## [C.010] ProtectivePayloadGate

Bounded Enforcer dedicated protective-mode containment state Private network.

**Implements / supports:**
- `VPNG-U004-R5` — [`full`]
- `VPNG-U004-R5.R2` — [`full`]
- `VPNG-U004-R5.R3` — [`full`]
- `VPNG-U004-R5.R4` — [`full`]

**Evidence:** EXP-083.

API

    @observe(∅) — fresh-observe exact dedicated protective containment state.
    @converge(ENABLED|DISABLED) — достичь и fresh-verify requested protective postcondition либо вернуть failure.

Architectural decisions

1. `One owned gate`
   *Protective containment является одним independently owned Artifact, а не композицией C.005 с отдельным host-side gate. EXP-082 остается feasibility evidence, но не selected architecture.*

2. `Complete IPv4 containment`
   *ENABLED запрещает ordinary-boundary IPv4 INPUT, ordinary-boundary IPv4 OUTPUT и весь IPv4 FORWARD внутри Private network. Поэтому ordinary->VPN, VPN->ordinary и VPN->VPN не требуют разных public gates.*

3. `Preserve runtime state`
   *Gate не уничтожает namespace, interfaces, routes, bindings или normal policy state. Linux candidate EXP-083 реализует gate отдельной owned nft table.*

4. `Bounded verification`
   *Один converge-вызов выполняет fresh observation -> optional bounded mutation -> fresh observation. Continuous retry/recovery принадлежит A.011.*

5. `Independent from structural ForwardingGate`
   *C.005 остается structural-transition barrier. Protective mode не переопределяет его API/ownership и не зависит от изменения `ip_forward`.*

Implementation

    design/NG3/code/python/rou/protective_payload_gate.py — C.010 bounded convergence contract and explicit observation/result states.
    design/NG3/code/python/rou/linux_protective_payload_gate.py — strict Linux nft observation and one-transaction owned mutation realization.

# Annex D. VPN external ends components

Этот Space содержит только external residents/capability providers. `VPNChannel[]` не является
компонентом VPN-GATE, поэтому отдельные VPN-GATE component specs в Annex D не требуются.



# Annex E. VPN-GATE-managed host state components

## [E.001] HostPublicationAdapter

Independent Adapter Device server publication в host-side owned scope. Один normalized
publication intent здесь materializes as a separate host mapping postcondition; managed-domain
local admission remains `Private network.NetworkPolicyAdapter` responsibility.

**Implements / supports:**
- `VPNG-U001-R1.R3.R6.R1` — [`full`]
- `VPNG-U001-R4.R4.R6.R3` — [`full`]
- `VPNG-U004-R4.R6` — [`full`]
- `VPNG-M001-R1.R1.R1` — [`full`]
- `VPNG-M001-R1.R1.R4` — [`full`]
- `VPNG-M001-R1.R1.R5` — [`full`]
- `VPNG-D001-R1.R1.R3` — [`full`]
- `VPNG-D001-R1.R1.R3.R3` — [`full`]
- `VPNG-D001-R1.R1.R7` — [`full`]

**Evidence:** `EV-00000`

API

    @observe(...) — fresh-observe exact owned host publication scope and conflicts.
    @apply(...) — converge complete desired mapping set and fresh-verify exact postcondition.
    @cleanup(...) — remove only owned mappings and fresh-confirm absence.

Architectural decisions

1. `Independent owner/API`
   *Host publication is not Profile routing and not Private-network nft state. Shared Device intent does not justify shared Adapter identity.*

2. `Two-postcondition publication`
   *Requested Device publication is READY only after managed local admission is exact and host mapping is exact. Addition orders local admission before host exposure; cleanup removes host exposure first.*

3. `Exact external claim`
   *Physical mapping identity includes protocol, host selector/port, current stack-local target and internal port. Conflicting targets for the same effective external claim fail rather than use rule order.*

4. `Local-destination ownership gate`
   *Linux DNAT first proves local destination ownership; broad interface/port matches do not capture unrelated transit.*

5. `No host-global forwarding ownership`
   *Adapter may observe host-forwarding prerequisite and report unready but does not enable it.*

Implementation

    design/NG3/code/python/rou/host_publication_adapter.py — semantic Adapter wrapper.
    design/NG3/code/python/rou/host_publication_policy.py — pure desired projection.
    design/NG3/code/python/rou/linux_host_publication.py — concrete Linux Driver for host nft/link/address/sysctl interaction.
    design/NG3/code/python/rou/alpha_runtime.py — current Release-1 runtime composition of host publication after managed local admission.


## [E.002] HostRoutingContribution

Direct lifecycle Machinery optional peaceful host-routing helper. Она устанавливает и удаляет
только complete identifiable contribution выбранного helper scope и не является host-routing
Manager/supervisor.

**Implements:**
- `VPNG-U001-R2` — [`full`]
- `VPNG-U001-R5.R1` — [`full`]
- `VPNG-U001-R5.R1.R1` — [`full`]

**Constrained by:**
- `VPNG-D001-R1.R1.R8`
- `VPNG-D001-R1.R1.R8.C1`
- `VPNG-D001-R1.R1.R8.C2`
- `VPNG-D001-R1.R1.R8.C3`
- `VPNG-D001-R1.R1.R8.R3`

API

    @converge(∅) — converge complete current peaceful helper contribution or fail.
    @cleanup(∅) — remove only still-identifiable owned contribution; tolerate foreign replacement rather than deleting it.

Architectural decisions

1. `Lifecycle scoped`
   *Contribution существует только по explicit helper configuration и обслуживается start/supported update/stop. Между lifecycle operations administrator changes не считаются helper drift; periodic repair отсутствует.*

2. `Scoped dispatch`
   *Release 1 поддерживает `:none`, `:local`, `:external`, `:any` и exact ingress selectors. Scope определяет, какие host routing decisions могут войти в helper table, но не меняет Profile destination semantics.*

3. `Per-selector main-first`
   *Каждый effective selector получает собственную preserve-main + helper-dispatch pair. Это сохраняет explicit administrator main routes внутри выбранного scope, не переупорядочивая unrelated RPDB policy вне scope.*

4. `Absolute no-recapture`
   *Traffic, уже пришедший из managed boundary, имеет higher-priority goto за helper range; failed ordinary lookup не может случайно вернуть его в helper capture.*

5. `Dedicated owned table`
   *Helper не переписывает host main. Его table содержит только derived remote Profile destinations и при необходимости effective Profile-SNAT identity routes.*

6. `No host forwarding authority`
   *External-ingress helper scope может требовать administrator-provided host IPv4 forwarding; helper только диагностирует prerequisite и не включает global sysctl.*

7. `Peaceful is not aggressive`
   *Authoritative aggressive routing и continuous repair принадлежат E.003/E.004; administrative containment принадлежит A.011/C.010. Существующая peaceful Machinery не получает эти semantics.*



## [E.003] AggressiveHostRoutingManager

Manager continuous ownership отдельно включенной authoritative host-routing области. Он
выбирает desired aggressive state из принятого intent/current boundary context, периодически
подтверждает effective postcondition и инициирует recovery или protective escalation.

**Implements / supports:**
- `VPNG-U001-R5.R2` — [`full`]
- `VPNG-U001-R5.R2.R2` — [`full`]
- `VPNG-U001-R5.R2.R3` — [`full`]
- `VPNG-U001-R5.R2.R3.R2` — [`full`]

**Constrained by:** `VPNG-U001-R5.R2.C1`

**Evidence:** EXP-081, EXP-084.

API

    @activate(...) — выполнить initial E.004 convergence и начать continuous ownership только после confirmed composite postcondition.
    @deactivate(∅) — прекратить continuous ownership и через E.004 подтвердить safe inactive state.
    @current_state(∅) — вернуть current confirmed / degraded / problem projection.

Architectural decisions

1. `Continuous semantic owner`
   *Manager, а не peaceful E.002 и не lower Driver, владеет обязанностью поддерживать aggressive guarantee между lifecycle operations.*

2. `Observe the guarantee`
   *Periodic audit подтверждает effective aggressive postcondition, а не пытается перечислить все виды foreign routing policy. Linux lower verification обязана учитывать факты, способные опровергнуть actual delivery.*

3. `Fresh reconciliation`
   *Каждый audit/recovery начинается с нового authoritative observation. Rtnetlink notifications допустимы как wakeup, но не заменяют finite-cadence resynchronization.*

4. `Fail-closed escalation`
   *Если E.004 не может восстановить/подтвердить delivery, local escape protection остается активной, а Manager устанавливает собственный source-scoped request в A.011. После подтвержденного recovery либо явного отключения aggressive mode E.003 снимает только свой request source. Failure подтвердить local/global containment остается explicit problem state.*

Implementation

    design/NG3/code/python/rou/aggressive_host_routing_manager.py — initial E.004 confirmation, finite-cadence continuous audit/recovery thread, current projection and source-scoped A.011 escalation/release composition.



## [E.004] AggressiveHostRoutingEnforcer

Bounded Enforcer одного composite aggressive postcondition. Он не выбирает continuous policy
и не является отдельным Manager.

**Implements / supports:**
- `VPNG-U001-R5.R2` — [`full`]
- `VPNG-U001-R5.R2.R1` — [`full`]
- `VPNG-U001-R5.R2.R3` — [`full`]
- `VPNG-U001-R5.R2.R3.R1` — [`full`]

**Evidence:** EXP-074 (narrow routing mechanics), EXP-081 (rejected narrow-only authority),
EXP-084 (prefix-scoped escape protection), EXP-085 (full-tunnel escape-protection exemptions).

API

    converge(active_desired) — fresh-observe, установить escape protection до routing capture, converge routing, затем fresh-verify complete composite postcondition.
    converge(inactive_desired) — снять и fresh-verify routing capture до release escape protection, затем подтвердить inactive postcondition.

Architectural decisions

1. `Composite postcondition`
   *Active success требует одновременно exact current managed-boundary generation, подтвержденную effective delivery managed scope и невозможность non-managed escape.*

2. `Escape protection is state, not component`
   *Aggressive escape-protection state independently observable/owned, но не имеет самостоятельного product client или lifecycle. Поэтому это lower Artifact внутри одного Enforcer contract, а не отдельный component boundary.*

3. `Fail-closed ordering`
   *Activation materializes/verifies escape protection before enabling routing capture. Deactivation removes/verifies routing capture before releasing escape protection. Partial transition может deny traffic, но не должен открыть ordinary-path leak.*

4. `Effective verification`
   *EXP-081 запрещает считать точность только VPN-GATE-owned table/rule objects доказательством authority. Linux realization может проверять RPDB/effective lookup или эквивалентные факты, но такая taxonomy остается lower implementation detail.*

5. `Bounded ownership`
   *Enforcer завершает каждый вызов success/failure после fresh verification и не содержит hidden continuous retry; следующий recovery attempt принадлежит E.003.*

6. `Full-tunnel non-recapture`
   *При managed scope `0.0.0.0/0` escape protection не трактует весь non-boundary traffic как утечку. EXP-085 требует сохранять host-local delivery и трафик, уже пришедший через exact managed boundary в ordinary network, одновременно запрещая local/forwarded managed outbound через non-managed egress.*

Implementation

    design/NG3/code/python/rou/aggressive_host_routing_enforcer.py — bounded E.004 activation/deactivation ordering and composite result.
    design/NG3/code/python/rou/linux_aggressive_escape_guard.py — independently owned nft escape-protection state with full-tunnel exemptions.
    design/NG3/code/python/rou/linux_aggressive_routing_authority.py — fresh RPDB authority verification that rejects any non-owned rule able to execute before aggressive dispatch.


# Annex F. Ambient host and external world components

Все residents этого Space являются external systems/capability providers
(`OrdinaryHostNetwork`, `systemd`, `ExternalConfigurationSource`), а не компонентами
VPN-GATE. Отдельные VPN-GATE component specs в Annex F не требуются.


# Annex G. Operator components

`OperatorClient` является external actor, а не компонентом VPN-GATE. Его interaction
contracts описаны в Space `Operator`; отдельный VPN-GATE component spec не требуется.
