# RC3 — внешний review после EXP-009, проход 2

**Дата:** 2026-11-10  
**Роль рецензента:** внешний эксперт по сетевым и информационным технологиям без знания истории проекта.  
**Проверяемая версия:** после ответа аналитика на review pass 1.  
**Код не анализировался.**

## Итог прохода

**Вердикт: CHANGES REQUIRED.**

Замечания pass 1 по partial multi-binding success, point-to-point association boundary,
guard namespace и старой терминологии закрыты. Модель стала существенно однозначнее.

Остались три несогласованности.

## R2.1 — startup lifecycle противоречит сам себе

**Серьезность:** блокирующая нормативная коллизия.

§2.1 по-прежнему содержит:

> «Режим `DEGRADED` при запуске не используется».

Но §8.2 теперь корректно разрешает безопасно завершить startup и войти в
`RUN/DEGRADED`, когда peers недоступны, desired fail-closed state применено и проверено,
а profile result = `FAIL` только из-за отсутствия UNICAST path.

Обе нормы одновременно истинными быть не могут.

Нужно уточнить §2.1:

- startup **ошибка** никогда не маскируется как `DEGRADED`;
- transport availability failure не является startup error;
- после успешного APPLY daemon может впервые войти в `RUN` как `ACTIVE` или
  `DEGRADED` в зависимости от ProfileResult.

## R2.2 — квантор критерия SUCCESS не везде одинаков

**Серьезность:** существенная.

§8.9 правильно определяет `SUCCESS` как:

> для **каждого** protected destination существует минимум один verified desired UNICAST RouteSpec.

Но далее встречается более слабая формулировка «нет ни одного path для protected
destinations», а инвариант 61 говорит «ноль UNICAST paths = FAIL».

При частичном route-application failure теоретически возможна ситуация, когда один
protected destination имеет path, другой — нет. По основному определению это `FAIL`,
по слабой формулировке читатель может решить иначе.

Норму нужно унифицировать:

> если **хотя бы для одного** protected destination нет verified desired UNICAST path,
> profile = FAIL.

## R2.3 — `peers=[]` валиден синтаксически, но его runtime consequence не локализован

**Серьезность:** средняя, полнота документа.

§14/§16 допускают `peers=[]` и `--check-config` выдает только NOTE. После новой
status-модели такой managed profile гарантированно не может иметь verified UNICAST path и
поэтому имеет `ProfileResult=FAIL`; daemon не может быть `ACTIVE`, пока такой профиль
managed.

Это допустимое решение для staged/fail-closed конфигурации, но его нужно написать рядом с
правилом `peers=[]`, а не оставлять читателю собирать следствие из §23.9.

## Что проверено и замечаний не вызывает

- 99 инвариантов нумеруются последовательно.
- Все ссылки `§N.M` разрешаются к существующим разделам.
- Нормативных остатков «жесткая привязка» и readiness-model не найдено.
- Binding cardinality и selector form разведены.
- Partial multi-binding failover с secondary path = `SUCCESS`.
- Все peers absent = безопасный availability failure, а не `ISOLATED`.
- Single-binding `SUCCESS` не объявлен доказательством handshake/reachability.
- Multi-binding без point-to-point evidence не использует эвристики.
- IPv6 prerequisite привязан к guard namespace.
- EXP-009 остается первичной доказательной записью, а архитектура выводит из нее общий контракт.

После R2.1–R2.3 требуется еще один полный review.
