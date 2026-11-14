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
5. если подтвержденно живых paths нет, effective order вообще не меняется.

Пример:

```text
configured/current:  A B C D
probe:               - + + -
effective:            B C A D
```

Переход концептуально является bubble promotion:

```text
A B C D
B B C D
B C A D
```

Промежуточный duplicate означает техническую route materialization, а не два логических
bindings.

Если после этого все paths теряют подтвержденную живость, порядок не возвращается
самопроизвольно к `A B C D`: без доказанно лучшего path probing не создает новую
перестановку.

Если затем `A` получает good news, configured priority снова имеет силу среди
подтвержденно живых paths и `A` может всплыть вверх.

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

Новая отдельная Calculator abstraction для этого пока не требуется. Если логика
effective order перестанет быть малой частью PayloadTrafficIntentCalculator, граница может
быть пересмотрена позже.

## 9. Уже существующая route semantics

Текущий NG2 `PayloadProfileRequest.ordered_paths` уже является семантическим порядком
приоритета.

Linux projection уже отображает позиции в metrics:

```text
position 0 -> metric 10
position 1 -> metric 20
position 2 -> metric 30
...
terminal blackhole -> metric 65536
```

Поэтому новая availability policy не требует нового route tier, shadow routes или
`UNAVAILABLE_METRIC`.

## 10. Route-priority transition

EXP-027 подтвердил в privileged Linux CI для обычного prefix и `default`, что fixed
metric positions можно использовать как route slots: `ip route replace` меняет один
slot, не удаляя тот же interface из другого metric, а terminal blackhole сохраняется.

Текущая Linux реализация имеет узкий verified fast path только для чистой permutation
существующих unicast paths. Он свежо проверяет старую projection, выполняет top-down
slot replacements, затем свежо проверяет конечную projection. Любой более широкий diff
или ошибка fast path переводит operation в существующий structural fail-closed rebuild.


При изменении только `ordered_paths` desired operation должна быть узкой route-priority
transaction:

- payload nft filtering не меняется;
- NAT policy не меняется;
- RPDB selectors/table ownership не меняются;
- `ip_forward` не закрывается только из-за permutation;
- меняются только owned unicast route slots соответствующего routing domain;
- после transition выполняется fresh verification конечного order.

Предпочтительный materialization pattern — замена route slots сверху вниз с допустимыми
временными duplicates.

Для перехода:

```text
A B C D
    ->
B C A D
```

концептуальная последовательность:

```text
A B C D
B B C D
B C C D
B C A D
```

Вытесняемый неподтвержденный path может кратковременно остаться без собственного route.
Это допустимо: safety requirement состоит в сохранении/появлении лучшего подтвержденного
payload path, а не в непрерывном представлении каждого degraded path во время transition.

## 11. Kernel evidence gate

Перед production route-only materialization нужно подтвердить узким Linux experiment:

1. один path может одновременно иметь routes к одному prefix через один interface с
   разными metrics;
2. route slot с заданным metric можно однозначно заменить path другого interface без
   затрагивания соседних metrics;
3. последовательность slot replacements не создает route gap для нового preferred path;
4. конечная FIB projection точно соответствует desired `ordered_paths`;
5. те же свойства выполняются для `default` и обычных prefixes;
6. owned protocol и terminal blackhole не меняют эти свойства.

До этого gate semantic bubble model считается принятой, а конкретная оптимизированная
Linux command sequence остается implementation hypothesis.

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
