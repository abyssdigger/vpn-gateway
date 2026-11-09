# RC3 — ответ аналитика на внешний review после EXP-009, проход 2

**Дата:** 2026-11-10  
**Исходный review:** `RC3-2026-11-10-post-EXP009-external-review-2.md`

## Решения

| Пункт | Решение | Изменение |
|---|---|---|
| R2.1 | ACCEPT | §2.1 теперь различает startup error и transport availability. Startup error всегда hard fail; безопасный startup без UNICAST path может успешно войти в `RUN/DEGRADED`. |
| R2.2 | ACCEPT | Во всех нормативных формулировках используется один квантор: `SUCCESS` требует ≥1 verified desired UNICAST path **для каждого** protected destination; отсутствие path хотя бы у одного destination = `FAIL`. |
| R2.3 | ACCEPT | Рядом с `peers=[]` явно записано операционное следствие: конфигурация валидна, но managed profile имеет `FAIL`, а daemon после безопасного startup работает в `DEGRADED`. |

После изменений требуется третий независимый review полного контракта.
