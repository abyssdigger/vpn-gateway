# RC3 — prefix metric allocator review 2

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** lifecycle / fail-closed / implementability reviewer  
**Область:** allocator integration with startup, reconciliation and validation  
**Вердикт:** **CHANGES REQUIRED**

## Общая оценка

После response к review 1 allocator state правильно включен в общий verified-state
contract. Сама модель остается простой и реализуемой.

Найдены три интеграционных хвоста.

## Finding 1 — explicit-list config bound still uses uint32 instead of BLACKHOLE

§14 все еще говорит:

> максимальная `(index+1)*10` route metric помещается в unsigned 32-bit priority.

Но новый общий invariant §4.4/§18:

```text
0 < UNICAST metric < BLACKHOLE_METRIC
```

Следовательно, explicit list должен отвергаться намного раньше uint32 overflow: первый
slot с metric `>= BLACKHOLE_METRIC` уже нарушает failover-to-blackhole semantics.

**Required:** §14 и validator contract должны ограничивать explicit list через
`BLACKHOLE_METRIC`, не через uint32.

**Severity:** HIGH.

## Finding 2 — runtime §8.4 commit step omits allocator state

§8.8 и invariants 50/51 уже исправлены, но ordinary runtime cycle в §8.4 шаг 12 все еще
говорит:

> зафиксировать OWNED и active binding state

Там также обязан быть prefix allocator mapping/cursor. Иначе startup и runtime описывают
разные commit boundaries.

**Severity:** HIGH.

## Finding 3 — allocator exhaustion happens before complete snapshot exists

§18 правильно определяет runtime exhaustion как fail-closed/isolation error.

Но §8.4 обычный цикл говорит сначала “построить ReconciliationSnapshot”, а дальнейшие
failure paths предполагают существование этого snapshot.

Allocator является частью snapshot construction. При exhaustion complete snapshot
построить невозможно.

**Required:** явно определить:

- snapshot/domain projection error, включая exhausted prefix allocator, не допускает
  partial desired state;
- daemon best-effort выключает forwarding;
- допускается config-derived isolation filter;
- runtime state -> ISOLATED;
- provisional allocation/cursor не commit-ятся.

Startup аналогичный failure остается hard startup failure.

**Severity:** HIGH.

## Дополнительная редакционная находка

В §8.4 нумерация шагов содержит `3 -> 5 -> 4`. Это не меняет семантику, но для
нормативного алгоритма следует исправить одновременно с Finding 2.

## Проверенные свойства

- active-set transition по-прежнему проходит protective barrier;
- новая prefix binding не требует renumber существующих routes;
- cursor-only state не является kernel truth;
- released metric не обязана использоваться немедленно;
- failed verification сохраняет предыдущий verified allocator state;
- restart reset согласован с cleanup proto 202;
- all-prefix-slots-exhausted не может привести к partial allowing state.

## Итог

После устранения Findings 1–3 lifecycle/fail-closed semantics allocator готовы к
реализации.
