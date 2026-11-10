# Ответ проекта на RC3 prefix metric allocator review 2

**Дата:** 2026-11-10  
**Review:** `RC3-2026-11-10-prefix-metric-allocator-review-2-lifecycle.md`

## Finding 1 — explicit-list bound

**ACCEPTED.**

§14 и invariant 79 теперь используют общий контракт `UNICAST metric < BLACKHOLE_METRIC`.
Unsigned-32 bound больше не является достаточным validator condition.

## Finding 2 — runtime commit boundary

**ACCEPTED.**

§8.4 step 12 теперь фиксирует OWNED routes, active binding state и prefix allocator
mapping/cursor одной verified-state boundary.

## Finding 3 — snapshot construction failure

**ACCEPTED.**

Добавлен отдельный failure path до ordinary reconciliation:

- incomplete snapshot/domain projection не используется частично;
- exhausted prefix allocator входит в этот класс;
- runtime -> forwarding-off/isolation -> `ISOLATED`;
- provisional allocator state не commit-ится;
- startup -> hard failure.

Также startup step 4 теперь явно строит provisional prefix allocation.

## Editorial finding — §8.4 numbering

**ACCEPTED.**

Нумерация восстановлена в последовательность 1..14 без изменения порядка операций.

## Result

Lifecycle/fail-closed integration allocator согласована.
