# RC3 — ответ аналитика на внешний review после EXP-009, проход 1

**Дата:** 2026-11-10  
**Исходный review:** `RC3-2026-11-10-post-EXP009-external-review-1.md`

## Решения

| Пункт | Решение | Изменение |
|---|---|---|
| R1 | ACCEPT | `SUCCESS` теперь требует хотя бы один verified desired UNICAST path для каждого protected destination. Ноль paths = `FAIL`; при `SAFE` policy daemon остается fail-closed в `DEGRADED`. |
| R2 | ACCEPT | Явно разведены status semantics single-binding и multi-binding. `SUCCESS` не трактуется как end-to-end health-check. |
| R3 | ACCEPT | Зафиксирована граница RC3: multi-binding association поддерживается только по однозначному point-to-point `(local_address, peer)` evidence; эвристики запрещены. |
| R4 | ACCEPT | Нормативный текст очищен от старой модели «жесткой привязки/готовности» там, где она конфликтовала с binding set/cardinality. Pre-EXP-009 readiness оставлен только как описание текущего кода в README. |
| R5 | ACCEPT | IPv6 prerequisite унифицирован: проверяется весь guard namespace, а не только discovery candidates. |
| R6 | ACCEPT | Операционный status обязан показывать ProfileResult/reason, form/cardinality, candidates, active bindings, peer bindings и desired/verified UNICAST paths. |

## Уточненная status-модель

```text
SAFE policy + >=1 verified UNICAST path per protected destination
    -> profile SUCCESS

SAFE policy + 0 verified UNICAST paths
    -> profile FAIL
    -> daemon DEGRADED

AMBIGUOUS
    -> profile FAIL

unknown/unsafe policy or insufficient observability
    -> daemon ISOLATED
```

Для multi-binding отсутствие primary при наличии secondary route — штатный `SUCCESS`.
Для single-binding transport handshake не является частью binding truth; поэтому
`SUCCESS` подтверждает kernel desired state, но не фактическую reachability peer.

Startup при нуле доступных peers не является фатальным: если fail-closed desired state
успешно применено и проверено, daemon входит в `RUN/DEGRADED`.

После этих изменений требуется независимый повторный review без опоры на это обоснование.
