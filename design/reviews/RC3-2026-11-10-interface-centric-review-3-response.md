# Ответ проекта на RC3 interface-centric review 3

**Дата:** 2026-11-10  
**Review:** `RC3-2026-11-10-interface-centric-review-3-config-domain.md`

## Finding 1 — metric range validation

**ACCEPTED.**

Контракт разделен:

- exact / explicit list — range проверяется config validator;
- `prefix+` — число active interfaces известно только во время исполнения, поэтому
  range проверяется при desired-route derivation каждого snapshot;
- overflow является reconciliation/domain error; wrap/saturation/truncation запрещены.

## Finding 2 — deterministic ASCII comparator

**ACCEPTED.**

Закреплен case-sensitive bytewise ASCII order, независимый от locale и natural numeric
sorting. Пример `vpns10 < vpns9` прямо указан как intentional consequence.

## Result

Config/domain semantics теперь полностью определяют metric derivation как pure function от
config + current snapshot, без истории событий и без implementation-specific sorting.
