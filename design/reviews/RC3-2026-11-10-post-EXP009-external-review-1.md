# RC3 — внешний review после EXP-009, проход 1

**Дата:** 2026-11-10  
**Роль рецензента:** внешний эксперт по сетевым и информационным технологиям, знакомый с Linux routing, Netfilter, VPN и эксплуатационной безопасностью, но не знакомый с историей проекта.  
**Объект review:** `design/RC3/vpn-gateway-architecture-rc3.md`, `design/RC3/terms-and-definitions.md`, EXP-009 и implementation-status README. Код не анализировался.

## Итог прохода

**Вердикт: CHANGES REQUIRED.**

Модель multi-binding после EXP-009 в целом последовательна: разделение selector form и binding cardinality, association по point-to-point evidence, точные allowing rules/NAT/routes и fail-closed guards не противоречат друг другу. EXP-009 достаточен как доказательство наблюдаемого interface/route lifecycle.

Остаются замечания, которые необходимо закрыть до признания документа непротиворечивым и полным.

## R1 — критерий ProfileResult SUCCESS сформулирован слишком широко

**Серьезность:** существенная.

§8.9, §23.9 и инвариант 61 допускают `SUCCESS` даже при отсутствии **всех** configured peers селектора multi-binding, если fail-closed state корректен.

Это смешивает два независимых свойства:

1. безопасность — отсутствие обходного пути и корректный fail closed;
2. доступность сервиса — наличие хотя бы одного materialized UNICAST path.

Корректное fail-closed состояние без рабочего route path является безопасным, но не успешным профилем.

Рекомендуемый контракт:

- частичная доступность multi-binding (`peer[0]` отсутствует, `peer[1]` bound) — `SUCCESS`, если полный desired state применен и проверен;
- ни одного materializable UNICAST path — `FAIL`, но не `ISOLATED`, если политика `SAFE`;
- такой `FAIL` переводит daemon в `DEGRADED`;
- отсутствие всех peers не должно быть фатальной ошибкой startup: безопасный startup может успешно завершиться в `DEGRADED`.

Важно не называть такой path доказанно «рабочим»: daemon сознательно не выполняет ping/handshake health-check. Строгий критерий должен быть сформулирован через наличие verified desired `UNICAST RouteSpec`.

## R2 — нужно явно развести single-binding и multi-binding в status semantics

**Серьезность:** существенная для эксплуатационной интерпретации.

Для селектора single-binding наличие active concrete binding достаточно для materialization routes всех configured peers; transport-level handshake не является источником истины. Поэтому `wg0` может оставаться profile `SUCCESS`, даже если фактическая удаленная сторона недоступна, пока daemon не наблюдает исчезновения binding.

Для селектора multi-binding наличие route конкретного peer связано с наблюдаемой `PeerBinding`.

Это уже следует из route model, но в status model должно быть сказано явно, иначе оператор может ошибочно считать `SUCCESS` end-to-end health-check.

## R3 — не описана граница применимости multi-binding association

**Серьезность:** средняя.

RC3 строит `PeerBinding` только по point-to-point `(local_address, peer)` evidence. Следовательно, multi-binding transport, который не публикует remote peer в interface address inventory, не может получить peer-specific routes по текущему контракту.

Это безопасно, но должно быть нормативно записано:

- RC3 multi-binding требует наблюдаемого однозначного point-to-point peer evidence;
- отсутствие такого evidence означает отсутствие `PeerBinding`, а не эвристическое сопоставление;
- для иных transport models потребуется отдельный будущий association mechanism.

## R4 — остаточная терминология старой single-binding модели

**Серьезность:** редакционная, но системная.

После перехода на binding cardinality в нормативном тексте остаются формулировки:

- «жесткая привязка»;
- «готовность/готовый профиль» как будто существует единый readiness state;
- «смена привязки или готовности».

Они конфликтуют с текущими `ConcreteBinding`, `PeerBinding`, binding set и cardinality. Термины `structural policy` и `binding-specific` в glossary также определены через «текущую жесткую привязку».

Нужно привести нормативный текст к binding state / active concrete bindings. Упоминания readiness допустимы только как описание pre-EXP-009 implementation baseline.

## R5 — IPv6 per-interface prerequisite должен ссылаться на guard namespace

**Серьезность:** средняя.

Основной §2.6 уже требует `disable_ipv6=1` для всего защитного пространства имен, что правильно для `prefix%`: guard `vpns+` шире numeric discovery.

Однако инвариант 10 и часть итоговых implementation notes используют старую формулировку «интерфейсы, совпадающие с управляемыми селекторами». Для `prefix%` это может быть прочитано как только numeric candidate set.

Нужно унифицировать формулировку: **все существующие interfaces в защитном пространстве имен управляемых селекторов**.

## R6 — операционный статус недостаточно определен

**Серьезность:** средняя.

§8.9 перечисляет поля status, но не фиксирует минимально необходимую интерпретацию результата.

Для диагностики partial failover статус должен позволять отличить:

- profile `SUCCESS` при частичной multi-binding доступности;
- profile `FAIL` при нуле materialized UNICAST paths;
- `AMBIGUOUS`;
- selector single-binding, где peer handshake не наблюдается.

Минимально достаточно публиковать profile result/reason, selector form/cardinality, candidates, active concrete bindings, peer bindings и количество/список desired/verified UNICAST paths.

## Проверки структуры

На момент review:

- EXP-009 имеет `COMPLETE — PASS` и содержит первичные наблюдения failover/failback;
- архитектура отделяет Netlink wakeup от snapshot-derived decisions;
- `prefix%` discovery и широкий guard namespace не смешаны;
- route metric остается стабильной функцией configured peer index;
- allowing firewall/NAT/routes используют exact interface names;
- специальной OpenConnect-ветки в нормативной модели нет.

После исправления R1–R6 требуется повторный независимый review всего затронутого контракта и проверка инвариантов/терминологии.
