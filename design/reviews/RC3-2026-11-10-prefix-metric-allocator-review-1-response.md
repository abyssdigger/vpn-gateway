# Ответ проекта на RC3 prefix metric allocator review 1

**Дата:** 2026-11-10  
**Review:** `RC3-2026-11-10-prefix-metric-allocator-review-1-routing.md`

## Finding 1 — verified allocator commit boundary

**ACCEPTED.**

§8.2, §8.8, §24.1 и invariants 41/50/51 синхронизированы. Prefix allocator mapping и
cursor являются частью того же verified process-local state, что OWNED routes и active
binding state.

При failed apply/verification provisional allocator state не commit-ится.

## Finding 2 — new ifindex and same numeric metric

**ACCEPTED.**

Новая `ConcreteBinding(name, ifindex)` проходит обычное allocation и не имеет гарантии
получить прежнюю metric. При этом совпадение численного значения с metric прежней binding
не запрещено, если это значение свободно.

## Finding 3 — route preference wording

**ACCEPTED.**

Разделено:

- Linux route metric участвует в выборе route;
- explicit list использует ее как гарантированный configured priority;
- prefix allocator гарантирует uniqueness и `metric < BLACKHOLE_METRIC`, но не
  interface priority.

## Result

Routing/state semantics allocator согласованы. Следующий независимый проход проверяет
lifecycle, fail-closed behavior и implementability.
