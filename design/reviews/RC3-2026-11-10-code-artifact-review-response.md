# RC3 — ответ на code review артефактов прежних архитектурных решений

**Дата:** 2026-11-10

## Решения

| Пункт | Решение | Действие |
|---|---|---|
| A1 | ACCEPT | Удалить мёртвый `_query_forwarding_state`. |
| A2 | ACCEPT | Удалить `RuntimeReasonCode.FORWARDING_QUERY_FAILED` и текст причины. |
| B1 | NO CHANGE | Annotation-only imports являются осознанным единообразным паттерном и полезны type checker'ам. |
| B2 | ACCEPT FOR REWRITE | Не делать отдельную косметическую правку старой projection path. При следующей переработке config/domain сохранить единую diagnostic boundary для snapshot projection. |
| B3 | ACCEPT | Process-local verified-state commit должен быть two-phase: вся validation/preparation завершается до первой мутации committed state. |
| B4 | ACCEPT — SPEC WINS | Structural route verification failure переводит pass в `INIT/PANIC`. Functional zero-path `ProfileResult=FAIL` при exact structural verification остаётся verified state и даёт `DEGRADED`, не PANIC. |

## Уточнение B4

Граница определяется не самим `ProfileResult`, а structural verification set:

- профиль входит в `verified_profiles` — desired exact route state подтверждён; его availability может быть `SUCCESS` либо `FAIL`;
- профиль отсутствует в `verified_profiles` — route state не verified; ordinary route pass считается failed и должен эскалировать в `INIT/PANIC`.

Таким образом сохраняется архитектурное разделение verification success и functional availability.

## Требование к следующей переработке

Новая config/domain projection должна сохранить:

1. единую fail-closed snapshot diagnostic boundary;
2. двухфазный non-partial commit verified process-local state;
3. PANIC после failed structural route repair/apply/verification;
4. отсутствие PANIC только из-за verified zero-path availability `FAIL`.
