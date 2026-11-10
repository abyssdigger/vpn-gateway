# Ответ проекта на RC3 interface-centric review 4

**Дата:** 2026-11-10  
**Review:** `RC3-2026-11-10-interface-centric-review-4-implementation-operability.md`

## Finding 1 — deterministic active-resource ordering

**ACCEPTED.**

Введен единый нормативный `active_order`:

- exact — single active;
- prefix — case-sensitive bytewise ASCII;
- explicit list — config order filtered to active.

Тот же order обязателен для routes, INPUT/FORWARD exact blocks, VPNG-INGRESS, NAT и status.

## Finding 2 — verified state vs ProfileResult

**ACCEPTED.**

Architecture теперь явно разделяет:

- successful verification desired fail-closed state;
- functional `ProfileResult`.

Verified zero-path state commit-ит current candidate/active binding state даже при
`ProfileResult=FAIL`. Actual apply/verification error state не commit-ит.

## Finding 3 — startup zero-path wording

**ACCEPTED.**

§8.2 прямо запрещает трактовать verified zero-path FAIL как route verification failure.
Successful startup может войти в RUN/DEGRADED после verified BLACKHOLE-only state.

## Result

Implementation mapping теперь детерминирован как по resource ordering, так и по моменту
commit process-local state.
