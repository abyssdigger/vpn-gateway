# RC3 — ответ аналитика на внешний review после EXP-009, проход 3

**Дата:** 2026-11-10  
**Исходный review:** `RC3-2026-11-10-post-EXP009-external-review-3.md`

## Решение R3.1

**ACCEPT.**

State machine и runtime reconciliation уточнены:

```text
SAFE + all profiles SUCCESS + ip_forward=1
    -> ACTIVE

SAFE + completed checks + (any profile FAIL OR confirmed ip_forward=0)
    -> DEGRADED

unknown/unreadable policy or ip_forward
    -> ISOLATED
```

Для завершенного не-`ISOLATED` цикла в `RUN` desired `ip_forward=1`. Если включение
не удалось, но повторное чтение подтверждает `0`, это безопасная потеря доступности и
`DEGRADED`. Если значение нельзя подтвердить, это insufficient observability и
`ISOLATED`.

Startup contract не изменен: обязательное финальное включение `ip_forward=1` при startup
должно успешно завершиться и подтвердиться; иначе startup hard-fails до входа в `RUN`.

После изменения требуется итоговый независимый review всего комплекта документов.
