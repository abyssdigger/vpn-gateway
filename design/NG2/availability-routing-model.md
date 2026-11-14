# VPN-GATE NG2 — минимальная модель availability и приоритета маршрутов

**Status:** active NG2 baseline candidate  
**Date:** 2026-11-14  
**Scope:** active probing as a routing-priority input

## 1. Задача

Active probing не является механизмом допуска или отключения VPN path.

Его единственная управляющая цель — помочь выбрать более предпочтительный path среди уже
допустимых и materialized paths одного Profile.

Следовательно:

- probe result не меняет binding membership;
- probe result сам по себе не удаляет последний payload path;
- недоступный или непроверяемый path остается допустимым fallback;
- если существует подтвержденно живой альтернативный path, он должен подняться выше
  неподтвержденных paths;
- если подтвержденно живой альтернативы нет, probing не должен ухудшать существующую
  маршрутизацию.

Это fail-safe свойство:

```text
probing may improve path preference
probing must not create an outage by removing the last eligible path
```

## 2. Два независимых вопроса

Для каждого path существуют две независимые характеристики.

### 2.1. Eligibility

Определяется не probing:

- path существует как concrete interface generation;
- path выбран/допущен конфигурацией и binding policy;
- административно не отключен;
- удовлетворяет другим обязательным условиям Profile.

Только eligibility определяет membership в payload route set.

### 2.2. Probe evidence

Probe subsystem сообщает только качество текущего знания о достижимости через eligible
path.

Для routing priority достаточно различать:

```text
CONFIRMED_LIVE
NOT_CONFIRMED_LIVE
```

Диагностика вправе дополнительно различать отсутствие ответа, локальную ошибку probe
machinery и отсутствие еще достаточного наблюдения. Эти причины не должны превращаться в
разные правила удаления payload path.

### 2.3. Configured enable/disable

Logical probe configuration survives disable/re-enable.

```text
enabled = false
```

означает:

- autonomous probing не выполняется;
- накопленное current evidence этого logical probe не используется;
- target/path/timing configuration сохраняется;
- повторное включение не требует заново конструировать logical probe configuration.

Physical ProbeRules materialized только для enabled consumers. Если несколько logical
probes разделяют один physical `(mechanism, InterfaceIdentity, target)` plane, отключение
одного consumer не закрывает plane. Отключение последнего enabled consumer закрывает его.

Disable не означает удаление payload path: eligibility payload path и probe lifecycle
остаются независимыми.

## 3. Положительное evidence

Любой валидный reply через нужный concrete path является хорошей новостью.

Не требуется знать:

- какой send породил reply;
- attempt id;
- sequence попытки на semantic уровне;
- завершились ли предыдущие sends;
- какой именно in-flight send следует считать успешным.

Для routing policy достаточно события:

```text
good_news(path)
```

Любая good news:

- немедленно подтверждает path как живой;
- сбрасывает накопленное отсутствие good news;
- прекращает UNKNOWN в диагностической state-модели, если оно было.

## 4. Отрицательное evidence и hysteresis

Отрицательное evidence образуется не результатом отдельной попытки, а последовательностью
evaluation intervals, в которых для path не было good news.

Минимальное состояние:

```text
missed_intervals
```

На границе interval:

```text
if good_news_since_previous_boundary:
    missed_intervals = 0
    path = CONFIRMED_LIVE
else:
    missed_intervals += 1
```

После настроенного порога отсутствия good news path перестает считаться
`CONFIRMED_LIVE`.

Положительное evidence асимметрично отрицательному: один валидный reply уже доказывает
работоспособность канала, тогда как отсутствие reply требует hysteresis.

## 5. Ошибка probe machinery

Локальная ошибка probing не доказывает недоступность удаленного канала и не является
отдельным routing transition.

Для routing preference ERROR означает только:

```text
в этом observation window не получено good news
```

Поэтому уже подтвержденный живой path **не** теряет `CONFIRMED_LIVE` от единичного ERROR.
Ошибка участвует в том же integral времени без good news:

```text
ERROR in one window
    -> missed_intervals += 1 at window boundary
    -> retain CONFIRMED_LIVE while below failure_intervals

continued windows without good news
    -> threshold reached
    -> NOT_CONFIRMED_LIVE
```

Если другой path тем временем имеет подтвержденную живость, после достижения общего
negative threshold он может подняться выше. Если подтвержденной альтернативы нет,
probing не создает новый outage и текущий payload order сохраняется.

ERROR никогда не означает:

```text
remove path
disable binding
prohibit payload
```

Диагностический state/reason для локальной ошибки остается отдельным от remote
unreachability; routing policy использует только накопленное отсутствие good news.

## 6. Базовый configured order

Каждый Profile имеет исходный deterministic path order:

```text
A B C D
```

Он задает административный приоритет paths и не меняется из-за истории probing.

Probe policy строит только текущий effective order.

При startup текущий effective order начинается с configured order.

Структурное изменение eligible path set либо административное изменение configured
priority является новой базой: effective order сначала rebased на новый configured
eligible order, после чего к нему применяется актуальное positive evidence. История
старой probe-перестановки не имеет права отменять новое административное намерение.

## 7. Bubble promotion

Routing policy не сортирует все paths заново при каждом наблюдении.

Она выполняет только продвижение подтвержденно живых paths через paths без подтвержденной
живости.

Эквивалентная формулировка:

1. подтвержденно живые paths образуют верхний prefix effective order;
2. внутри этого prefix сохраняется configured priority;
3. остальные paths не удаляются;
4. среди остальных сохраняется их текущий относительный порядок;
5. если подтвержденно живых paths нет, effective order не меняется.

Пример:

```text
configured/current:  A B C D
probe:               - + + -
effective:            B C A D
live-prefix length:   2
```

Если после этого все paths теряют подтвержденную живость, относительный порядок не
возвращается самопроизвольно к `A B C D`: без доказанно лучшего path probing не создает
новую сортировку. Меняется только граница live-prefix.

Если затем `A` получает good news, configured priority снова имеет силу среди
подтвержденно живых paths и `A` может всплыть вверх.

Live-prefix length является частью semantic payload routing intent. Это не отдельный path и
не Linux metric: значение нужно, чтобы lower domain мог однозначно представить границу
между confirmed-live prefix и остальным effective order, включая restart/reconciliation.

## 8. Payload intent

Availability evidence не должен поступать в `BindingCalculator` как условие membership.

Вместо этого:

```text
eligible/bound paths
        +
configured priority
        +
availability evidence
        +
current effective order
        |
        v
PayloadTrafficIntentCalculator
        |
        v
PayloadProfileRequest:
    ordered_paths
    priority_prefix_length
```

`ordered_paths` содержит полный eligible set в effective order.
`priority_prefix_length` указывает длину confirmed-live prefix.

Если Profile пока не управляется availability evidence, payload projection сохраняет
старую deterministic priority semantics: prefix считается равным полному `ordered_paths`,
то есть технический EMPTY slot находится после последнего path.

Новая отдельная Calculator abstraction для этого пока не требуется. Если логика
effective order перестанет быть малой частью PayloadTrafficIntentCalculator, граница может
быть пересмотрена позже.

## 9. Linux route-slot projection

Для Profile с `N` eligible paths Linux projection резервирует `N+1` обычных metric
slots ниже terminal blackhole.

Steady-state invariant:

```text
N eligible paths
N + 1 ordinary metric slots
exactly one EMPTY slot
exactly one route for every eligible path
```

EMPTY находится сразу после confirmed-live prefix.

При `FIRST_PATH_METRIC=10` и `PATH_METRIC_STEP=10`:

```text
A B G D . V E J
10 20 30 40 50 60 70 80
            ^
          EMPTY
```

То есть точка является не route и не availability state. Это зарезервированный свободный
metric slot.

Terminal blackhole остается отдельным:

```text
terminal blackhole -> metric 65536
```

Все обычные slots, включая EMPTY, обязаны оставаться ниже terminal metric.

Generic `RoutingDomainSpec`, не использующий priority-prefix semantics, может не иметь
EMPTY slot. Persistent EMPTY является свойством payload priority projection, а не
универсальным требованием для ProbeRules и прочих routing domains.

## 10. Route-priority transition

При чистом изменении effective priority path membership не меняется. Поэтому transition
рассматривается как перестановка:

```text
eligible paths + EMPTY
```

между двумя steady states.

### 10.1. Единственный primitive

Пусть текущий EMPTY имеет metric `Mempty`, а path `X` сейчас находится на `Mold`.

Один элементарный move:

```text
1. add X at Mempty
2. delete X at Mold
```

После первого шага:

- присутствуют все `N` eligible paths;
- routes стало `N+1`;
- ровно один path, `X`, имеет две копии;
- EMPTY временно отсутствует.

После второго шага:

- снова ровно `N` routes;
- каждый eligible path имеет ровно одну копию;
- `Mold` становится новым EMPTY.

Ни live, ни non-confirmed path не удаляется из FIB как промежуточный прием перестановки.

### 10.2. Planner

Planner сравнивает current и desired mapping одного и того же набора:

```text
metric slot -> path | EMPTY
```

и повторяет primitive до полного совпадения.

На каждом шаге:

1. определяется текущий EMPTY;
2. если desired state требует в этом slot конкретный path, этот path переносится в EMPTY;
3. если desired state тоже требует здесь EMPTY, но остается отдельный цикл перестановки,
   deterministic mismatched occupant временно переносится в EMPTY, разрывая цикл;
4. после add/delete old location перенесенного path становится новым EMPTY.

Отдельных алгоритмов для death, recovery, failback или admin reorder не требуется.

### 10.3. Пример recovery

```text
current: A B G D . V E J
target:  A B V G D . E J
```

Завершенные elementary moves:

```text
A B G D . V E J
A B G . D V E J    D: 40 -> 50
A B . G D V E J    G: 30 -> 40
A B V G D . E J    V: 60 -> 30
```

Внутри каждого перехода между строками сначала существует duplicate переносимого path,
и только затем удаляется его старая копия.

### 10.4. Пример с recovered path в крайнем правом slot

```text
current: A B G D E J . V
target:  A B V G D E J .
```

```text
A B G D E J . V
A B G D E . J V    J: 60 -> 70
A B G D . E J V    E: 50 -> 60
A B G . D E J V    D: 40 -> 50
A B . G D E J V    G: 30 -> 40
A B V G D E J .    V: 80 -> 30
```

Крайний правый path не является special case. Persistent EMPTY уже предоставляет
необходимый scratch slot.

### 10.5. Executor boundary

Route-priority fast path допустим только если неизменны:

- path membership;
- destination/domain allocation;
- RPDB selectors;
- terminal routes;
- nft filter/NAT;
- prerequisites;
- forwarding requirement;
- обычный metric-slot universe.

Executor:

1. свежо проверяет current full projection;
2. строит deterministic EMPTY-slot move plan;
3. выполняет каждый move как add duplicate -> delete old;
4. свежо проверяет конечную full projection;
5. при любой ошибке переходит в существующий structural fail-closed rebuild.

Caller не выбирает transition kind.

Availability failover намеренно не реализует per-flow pinning к demoted path. Если policy
признала path достаточно плохим для понижения приоритета, последующие routing lookups не
должны искусственно удерживаться на нем. Seamless migration established transport session
между произвольными VPN paths не является обещанием этой функции.

## 11. Kernel evidence — EXP-027 PASS

EXP-027 повторно закрывает route-slot gate уже для persistent-EMPTY production strategy.

В privileged Linux CI, отдельно для ordinary prefix и `default`, подтверждено:

1. один interface/path может одновременно иметь две owned unicast routes к одному
   destination на разных metrics;
2. `ip route add` в EMPTY metric создает duplicate, не удаляя старую копию;
3. exact `ip route del ... dev X metric Mold` удаляет только старую копию, после чего
   `Mold` становится новым EMPTY;
4. на каждом проверенном add phase присутствует полный eligible path set и ровно один
   duplicate;
5. после каждого delete phase присутствует полный eligible path set, по одной копии каждого
   path и ровно один EMPTY;
6. terminal blackhole protocol 201 / metric 65536 сохраняется на каждом шаге;
7. те же свойства проходят для:
   - recovery `A B G D . V E J -> A B V G D . E J`;
   - обратной demotion;
   - recovery `A B G D E J . V -> A B V G D E J .`.

Ранний результат EXP-027 с `ip route replace` остается полезным kernel evidence того, что
один path допускает одновременные routes на разных metrics, но production transition
strategy им superseded: eligible path больше не вытесняется из FIB даже временно.

Staging routing table для обычной priority permutation не требуется.

## 12. Что новая модель делает лишним

На уровне availability/routing policy не требуются:

- удаление binding по `UNREACHABLE`;
- per-attempt semantic correlation;
- attempt identity как input routing policy;
- recovery threshold для положительного reply;
- retry cadence, отдельный от evaluation interval;
- per-attempt timeout как verdict policy;
- shadow fallback route tier;
- `UNAVAILABLE_METRIC`;
- ECMP fallback как механизм availability failover;
- staging routing table только ради обычной перестановки path priority.

Нижние verified safety mechanisms — concrete interface generation, ProbeRules readiness,
selective LOCAL_PROCESS network plane и generation-sensitive evidence invalidation — этим
решением не отменяются. Они должны быть пересмотрены отдельно только на предмет
неиспользуемых деталей, а не удалены автоматически.
