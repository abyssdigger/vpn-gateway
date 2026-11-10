# RC3 — prefix metric allocator review 1

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** Linux routing / state-machine reviewer  
**Область:** dynamic metric allocation for `prefix+`  
**Вердикт:** **CHANGES REQUIRED**

## Общая оценка

Отказ от ASCII-derived route priority для `prefix+` архитектурно оправдан.

Разделение теперь корректное:

- explicit list — administrator-defined stable priority;
- prefix — set semantics без обещанного interface priority;
- metric у prefix — технический идентификатор нескольких одновременных routes;
- любой daemon-owned UNICAST имеет metric строго меньше BLACKHOLE.

Циклический allocator с process-local mapping достаточен. Persistence между restart не
нужна, потому что startup cleanup удаляет proto 202 routes.

## Finding 1 — allocator state не полностью включен в verified commit boundary

§4.4 и §23.3 правильно говорят, что provisional mapping/cursor commit-ятся только после
successful verification.

Но несколько других нормативных мест все еще фиксируют только OWNED + active bindings:

- §8.2 шаг 12;
- §8.8 текст и схема commit ordering;
- invariant 41 описывает snapshot без allocator state;
- §24.1 говорит, что committed transition state хранит только verified active bindings.

Это создает два возможных прочтения implementation:

1. allocator state является частью verified state и commit-ится атомарно с routes/bindings;
2. allocator cursor можно изменить раньше route verification.

Допустим только вариант 1.

**Required:** везде явно включить allocator mapping/cursor в тот же verified commit
boundary. При failed apply/verification ни mapping, ни cursor не меняются.

**Severity:** HIGH.

## Finding 2 — wording “new ifindex does not inherit metric” too strong

§4.4 говорит:

> новая binding с тем же именем, но новым ifindex, не наследует прежнюю metric.

Правильная семантика: новая `(name, ifindex)` считается новой binding и проходит обычное
allocation. Она **не имеет гарантии** получить старую metric, но allocator может случайно
выдать то же свободное число.

Запрещать совпадение численного значения не требуется и только усложнит allocator.

**Required:** заменить на “не имеет права/гарантии наследования; same numeric metric is
allowed as an ordinary fresh allocation”.

**Severity:** MEDIUM.

## Finding 3 — route preference wording around EXP-009 must distinguish selector forms

§4.4 после allocator rules все еще содержит общий тезис:

> metric выбирает предпочтительный существующий interface path

Для explicit list это контракт VPN-GATE. Для prefix kernel действительно предпочтет
меньшую metric, но **архитектура не обещает, какой interface ее получит**.

Нужно сформулировать:

- Linux metric участвует в выборе маршрута;
- explicit list использует это как гарантированный configured priority;
- prefix allocator только обеспечивает уникальность и `metric < BLACKHOLE_METRIC`;
  относительный preference prefix interfaces не является контрактом.

**Severity:** MEDIUM.

## Проверенные свойства

- 10..65530 дает 6553 допустимых slots при 65536/10/10.
- wrap-around не требует немедленного заполнения holes.
- occupied slot scan предотвращает collision.
- exhausted allocator fail-closed behavior определен.
- explicit-list slots не renumber.
- continuous prefix binding сохраняет metric.
- restart safely resets allocator after route cleanup.
- mapping keyed by `name+ifindex` соответствует concrete binding identity.

## Итог

Модель allocator принимается после устранения Findings 1–3.
