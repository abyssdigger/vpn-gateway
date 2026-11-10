# Ревью кода на артефакты прежних архитектурных решений

Источник: внешний code review после EXP-009, 2026-11-10.

## A. Содержательная находка: артефакт pre-EXP-009 в `daemon.py` и `models.py`

### A1. `_query_forwarding_state` — мёртвый метод

Метод никогда не вызывается. Это рудимент старой модели, где route verification failure оставлял daemon в `DEGRADED` и отдельно запрашивал `ip_forward`. После перехода к `INIT/PANIC` при structural route failure метод больше не нужен.

### A2. `RuntimeReasonCode.FORWARDING_QUERY_FAILED` — мёртвый enum

Единственная ссылка находится внутри мёртвого `_query_forwarding_state`.

### A3. Рекомендация

Удалить `_query_forwarding_state`, `FORWARDING_QUERY_FAILED` и соответствующий `RUNTIME_REASON_TEXT`.

## B. Мелкие находки

### B1. Annotation-only imports

`IPv4Network` и аналогичные импорты используются только в аннотациях при `from __future__ import annotations`. Это единообразный паттерн и не является артефактом.

### B2. `_build_reconciliation_snapshot` — неодинаковая диагностическая обёртка исключений

`ValueError` получает wrapper `reconciliation snapshot projection failed`, а собственный `ReconciliationError` allocator/route projection проходит напрямую. Поведение одинаково fail-closed, но сообщения неоднородны.

### B3. `_commit_owned` не атомарен по профилям

Последовательный вызов `profile.commit_verified_state()` может частично изменить process-local committed state, если поздний профиль неожиданно не проходит внутреннюю validation. Рекомендация: pre-validation/two-phase commit.

### B4. Route verification failure: code/spec discrepancy

Архитектура требует `INIT/PANIC`, если ordinary route repair/apply/structural verification не завершился успешно. Текущий код может оставить structural verification failure в `DEGRADED`.

При этом functional zero-path `ProfileResult=FAIL` не является structural verification failure и должен оставаться валидным verified fail-closed state.

Рекомендация: синхронизировать реализацию со spec либо явно изменить spec.

## C. Подтверждение удаления старых артефактов

Review подтвердил отсутствие `peers/PeerBinding`, `local_address`, `prefix%`, `AMBIGUOUS`, старой ASCII prefix-metric derivation и остальных ранее удалённых слоёв. ADD/REMOVE/INIT-PANIC, IPv6 latch, process-local active_order и cyclic prefix allocator структурно соответствуют текущей архитектуре.

## Итог

Содержательный stale artifact: `_query_forwarding_state` + `FORWARDING_QUERY_FAILED`.

Дополнительные findings: snapshot diagnostic wrapping, atomic commit boundary и structural route-verification failure path.
