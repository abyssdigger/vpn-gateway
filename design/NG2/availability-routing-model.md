# VPN-GATE NG2 — availability и приоритет маршрутов

**Status:** normative NG2 design  
**Date:** 2026-11-15  
**Scope:** availability as an optional routing-priority modifier

## 1. Core invariant

Availability probing does not define whether a payload path exists or may carry traffic.

Only binding/eligibility controls payload route membership.

Availability may change **priority only**:

```text
probing may reorder eligible paths
probing never adds or removes an eligible payload path
```

The routing-relevant fact per logical channel is:

```text
availability_problems: bool
```

Initial state is `false`. Disabled probing also means `false` by definition.

Therefore probing is an additional negative signal, not the backbone of runtime state.

## 2. Configured order is the baseline

Each Profile has deterministic configured path order:

```text
A B C D
```

Startup begins exactly in that order. Enabling probing does not delay or demote any path.

A structural path-set or configured-priority change rebases the current order to the new
configured order before current availability-problem flags are applied.

## 3. Problem aggregation

The per-channel hysteresis and input aggregation are normative in
`design/NG2/availability-collector-materializer.md`.

For one Profile/path:

- channels with probing disabled contribute no problem;
- if one path has several enabled assigned probe channels, the path is considered to have
  availability problems only when **all** those channels currently have
  `availability_problems=true`;
- one channel without problems is therefore sufficient to keep that path in the
  no-problem class.

This preserves the previous "one valid positive path observation is enough" behavior
without requiring a separate separate positive-health state model.

## 4. Effective order

The effective order is calculated from:

```text
configured order
current verified effective order
set of paths with availability problems
```

Rules:

1. paths without availability problems form the leading prefix;
2. that prefix is ordered by configured priority;
3. paths with availability problems remain present;
4. problem paths preserve their current relative order;
5. if every path has problems, there is no better path to promote and current relative
   order is retained;
6. if no path has problems, effective order is exactly configured order.

Example:

```text
configured/current: A B C D
B has problems

effective:           A C D B
```

If B recovers and no path has problems:

```text
effective:           A B C D
```

## 5. Materialized boundary

The transient runtime routing intent carries:

```text
preferred_prefix_length
```

For N paths:

- no problem paths: `preferred_prefix_length=None`; no availability-derived boundary or
  steady metric gap exists;
- `K`, where `0 < K < N`: the emergent free metric slot is immediately before the
  first problem path;
- `0`: all paths currently have problems; current order is retained and the first
  ordinary metric slot is free.

This is runtime materialization state, not user configuration and not a persistent gap
object.

## 6. Disable semantics

Disabling a logical probe:

- stops autonomous probe execution for that channel;
- clears its `availability_problems` contribution immediately;
- does not remove its payload path;
- does not imply UNKNOWN or unhealthy routing state.

If disabling the last problematic channel for a path clears the path-level problem, the
path can return to configured priority through the ordinary route sorter.

## 7. Route transition ownership

Availability-driven reorder uses the same sole transactional route executor as every
other payload route mutation.

There is no separate availability route queue or concurrent reorder executor.

A running lower transaction is immutable. New ping/tick facts can accumulate, but another
route materialization begins only after the current one returns.

## 8. Session behavior

Availability-driven demotion does not imply per-flow pinning to the previous path.
Subsequent routing lookups use the new priority order.

Preserving arbitrary established transport sessions across VPN-path changes would be a
separate feature with separate policy.

## 9. Route-slot projection

Для `N` eligible paths transition planner рассматривает рабочий диапазон из `N+1`
обычных metric positions ниже terminal blackhole.

Это не означает наличие `N+1` routes. В steady state всегда присутствует ровно `N`
unicast routes — по одному на каждый eligible path.

Если без availability-проблем `K < N` paths, единственный незанятый metric находится
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
all problem-marked:
. A B C D
10 20 30 40 50
```

То есть все routes начинаются со второй позиции рабочего диапазона.

Положение свободного metric не фиксируется в конфигурации и не materialized отдельным
объектом. Оно однозначно выводится из текущего effective order и transient
`preferred_prefix_length`.

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
position справа от preferred-prefix. Затем preferred paths, которые стояли после него, по одному
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

При recovery preferred paths справа от новой позиции recovered path сначала по одному
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
3. фиксирует plan как immutable для текущей transaction;
4. каждый move выполняет как `add duplicate -> delete old copy`;
5. свежо проверяет конечную projection;
6. при любой ошибке переходит в structural fail-closed rebuild.

Для одного Profile/routing-domain одновременно выполняется не более одной
route-priority transaction. Новое availability state, пришедшее во время materialization,
может только заменить pending/latest desired state; текущий plan не пересчитывается и не
interleave'ится. Следующая transaction начинается только от freshly verified результата
предыдущей.

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
