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
```

Если после этого все paths теряют подтвержденную живость, порядок не возвращается
самопроизвольно к `A B C D`: без доказанно лучшего path probing не создает новую
перестановку.

Если затем `A` получает good news, configured priority снова имеет силу среди
подтвержденно живых paths и `A` может всплыть вверх.

Availability-driven demotion не подразумевает per-flow pinning к пониженному path. Если
policy признала path достаточно плохим, чтобы понизить его приоритет, последующие routing
lookups должны иметь возможность использовать более предпочтительный path. Бесшовное
сохранение established transport session при смене произвольного VPN path является другой
функцией с другой policy.

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
PayloadProfileRequest.ordered_paths
```

`ordered_paths` остается полным eligible set. Никакой EMPTY/gap не является path,
binding или частью пользовательской конфигурации.

Граница между `CONFIRMED_LIVE` prefix и остальным effective order является runtime
availability state. Linux transition planner получает эту границу как производное
операционное знание, а не как сохраняемое поле Profile/NetworkRules.

Новая отдельная Calculator abstraction для этого пока не требуется. Если логика
effective order перестанет быть малой частью PayloadTrafficIntentCalculator, граница может
быть пересмотрена позже.

## 9. Route-slot projection

Для `N` eligible paths transition planner рассматривает рабочий диапазон из `N+1`
обычных metric positions ниже terminal blackhole.

Это не означает наличие `N+1` routes. В steady state всегда присутствует ровно `N`
unicast routes — по одному на каждый eligible path.

Если подтверждено живыми `K < N` paths, единственный незанятый metric находится
непосредственно перед первым неподтвержденным path:

```text
A B G D . V E J
10 20 30 40 50 60 70 80
```

Точка здесь — только отсутствие route на metric 50.

Крайние случаи:

```text
all live:
A B C D
10 20 30 40
```

Отдельной steady-state дырки нет. Metric 50 просто является следующим свободным рабочим
position и может быть использован первым transition move.

```text
all non-confirmed:
. A B C D
10 20 30 40 50
```

То есть все routes начинаются со второй позиции рабочего диапазона.

Положение свободного metric не фиксируется в конфигурации и не materialized отдельным
объектом. Оно однозначно выводится из текущего effective order и runtime live-prefix.

Terminal blackhole остается отдельным:

```text
terminal blackhole -> metric 65536
```

Все рабочие metrics обязаны оставаться ниже него.

## 10. Route-priority transition

Чистая priority transition не меняет eligible path membership, nft filter/NAT,
RPDB selectors, table ownership или forwarding requirement.

Единственный primitive:

```text
X находится на Mold
Mfree свободен

1. add X at Mfree
2. del X at Mold
```

После шага 1:

- полный eligible path set по-прежнему присутствует;
- только `X` имеет две route copies;
- свободного metric временно нет.

После шага 2:

- снова ровно одна route на каждый eligible path;
- `Mold` автоматически становится новым свободным metric.

Следовательно, ни живой, ни неподтвержденный path не используется как временная жертва
перестановки.

### 10.1. Death

Если path становится неподтвержденным, он сначала перемещается в текущий свободный
position справа от live-prefix. Затем живые paths, которые стояли после него, по одному
переезжают к меньшим metrics. В результате свободный metric оказывается непосредственно
перед свежепониженным path.

Например:

```text
A B V G D . E J
    V dies

V -> free:
A B . G D V E J

G -> free:
A B G . D V E J

D -> free:
A B G D . V E J
```

Если до события все paths были live, steady-state gap отсутствует. Первый move использует
просто следующий свободный metric после последнего path:

```text
A B V G D E J
V dies

V -> next free metric:
A B . G D E J V

G,D,E,J move toward lower metrics:
A B G D E J . V
```

### 10.2. Recovery

При recovery живые paths справа от новой позиции recovered path сначала по одному
перемещаются к большим metrics, начиная с самого правого. Когда нужный metric освобожден,
recovered path переезжает туда. Если после него остались неподтвержденные paths левее
нового положения свободного metric, они аналогично сдвигаются вправо до восстановления
границы.

Пример:

```text
A B G D . V E J
    V recovers

D -> free:
A B G . D V E J

G -> free:
A B . G D V E J

V -> free:
A B V G D . E J
```

Для:

```text
A B G D E J . V
```

тот же primitive сначала сдвигает `J,E,D,G` вправо, затем переносит `V` на его
configured-priority position. После этого все paths live, поэтому свободный рабочий metric
остается только за последним path и не является steady-state gap.

### 10.3. Generic planner

Чистый planner оперирует рабочим представлением:

```text
(path | free) * (N + 1)
```

и повторяет один primitive до совпадения с target layout.

Если свободный metric уже находится на своей target position, но остается отдельный цикл
перестановки, planner детерминированно копирует один mismatched path в свободный position,
тем самым разрывает цикл, а затем продолжает обычное перемещение свободного slot.

Это покрывает death, recovery, failback и административную permutation одним алгоритмом.

### 10.4. Executor safety

Linux Executor:

1. свежо проверяет current projection;
2. строит deterministic move plan;
3. каждый move выполняет как `add duplicate -> delete old copy`;
4. свежо проверяет конечную projection;
5. при любой ошибке переходит в structural fail-closed rebuild.

Caller не выбирает transition kind.

## 11. Kernel evidence — EXP-027 PASS

EXP-027 повторно проверяет route-slot primitive в privileged Linux CI для обычного prefix
и `default`.

Подтверждено:

1. один interface/path может одновременно иметь две owned unicast routes к одному
   destination на разных metrics;
2. `ip route add` в свободный metric создает duplicate и сохраняет старую copy;
3. exact `ip route del ... dev X metric Mold` удаляет только старую copy;
4. после add phase присутствует полный eligible set и ровно один duplicate;
5. после delete phase присутствует полный eligible set и по одной copy каждого path;
6. terminal blackhole protocol 201 / metric 65536 сохраняется;
7. проходят как ordinary prefix, так и `default`;
8. отдельно проверены:
   - recovery `A B G D . V E J -> A B V G D . E J`;
   - обратная demotion;
   - recovery `A B G D E J . V -> A B V G D E J`;
   - death из all-live `A B V G D E J -> A B G D E J . V`.

Ранний вариант EXP-027 с `ip route replace` остается историческим доказательством того,
что duplicate path на разных metrics допустим, но production transition primitive теперь
строже: ни один eligible path не вытесняется из FIB даже временно.

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
