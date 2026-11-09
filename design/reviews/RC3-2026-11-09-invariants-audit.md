# Аудит §26 (инварианты 1–99)

Прошёл каждый инвариант против конкретных разделов RC3. Ниже — три категории: (A) реальные проблемы, которые стоит закрыть до code-refactor; (B) пробелы (не хватает инварианта); (C) дублирование и косметика. В конце — краткая сводка и приоритеты.

## A. Проблемы (реальные несоответствия или imprecise формулировки)

### A1. Invariant 17 технически неверен про «kernel operand»

```
17. Prefix selector никогда не попадает в RouteSpec/iptables ACCEPT/NAT kernel operand;
    эти ресурсы используют только resolved concrete exact ifname.
```

`-i vpns+ -j REJECT` (§4.4, §9.2, EXP-005) — это **именно iptables kernel operand**, и prefix там как раз присутствует. Invariant 17 буквально утверждает, что prefix selector «никогда не попадает в kernel operand», что противоречит §9.2.

Invariant 27 спасает ситуацию:

```
27. Family wildcard/prefix match допустим только как deny-only guard после target
    validation; wildcard ACCEPT/NAT запрещён.
```

Но читатель, дойдя до 17 раньше 27, получит неверную картину. Правка: переформулировать 17 как «prefix selector не попадает в RouteSpec, iptables ACCEPT operand или NAT interface operand» — перечислить конкретные запрещённые операции, а не обобщать до «kernel operand». Либо добавить «никогда не попадает в **разрешающий** kernel operand».

### A2. Invariant 11 смешивает два разных свойства

```
11. Exclusive ownership ip_forward means terminal verdict for each IPv4 FORWARD packet.
```

«Exclusive ownership» — это про sysctl (кто пишет `net.ipv4.ip_forward`). «Terminal verdict» — это про firewall prefix (VPNG-FORWARD-DENY на конце). Это **два разных** свойства. По §2.3 они связаны решением архитектуры (владелец sysctl обязан владеть и terminal verdict), но invariant сформулирован так, будто первое логически влечёт второе.

Правка: разделить. «Exclusive ownership of ip_forward is accompanied by exclusive ownership of the terminal FORWARD verdict via VPNG-FORWARD-DENY at the end of daemon-owned prefix.» Или в §2.3 добавить, что это — ассоциированное обязательство, а не следствие.

### A3. Invariant 12 требует уточнения «physically after prefix»

```
12. Foreign FORWARD rules физически сохраняются, но недостижимы при ip_forward=1 из-за
    VPNG-FORWARD-DENY.
```

Точнее: недостижимы **только если физически находятся после daemon-owned prefix**. Если внешний admin вставил правило на позицию 1 во время RUN, оно сейчас исполняется первым (§4.4, residual window). Оно будет обнаружено как UNSAFE на следующем pass и сдвинуто за `VPNG-FORWARD-DENY` deny-first repair'ом, но в самом окне — оно имеет decision authority.

Правка: «Foreign FORWARD rules **physically positioned after daemon-owned prefix** are unreachable with ip_forward=1. Foreign rules inserted before the daemon prefix are detected as drift and corrected by deny-first repair at the next reconciliation pass.» Это и есть фактическая семантика §4.4 и §8.6, но invariant 12 её сейчас не отражает.

### A4. Invariant 57 «resolution failure» — двусмысленность уровня

```
57. Interface inventory/read/parse/resolution failure -> ISOLATED, not ordinary DEGRADED.
```

«resolution failure» можно прочитать двумя способами:

- **pass-level**: снапшот не собрался целиком (KernelError на inventory, парсере, или на резолве одного селектора по неизвестной причине);
- **per-profile**: селектор вернул AMBIGUOUS.

Второе — это `profile FAIL`, а не `ISOLATED` (§4.3, §8.5, invariant 62). Первое — `ISOLATED` (§8.4). Invariant должен явно это разделить:

Правка: «Interface inventory/read/parse failure, or the pass-level resolution step cannot complete, is an isolation-class failure -> ISOLATED. Per-profile AMBIGUOUS is a profile FAIL (invariant 62), not ISOLATED.»

### A5. Invariants 88 и 89 ссылаются на механизмы, которых нет в RC3 §23

```
88. Programming exceptions не маскируются как expected UNKNOWN/DEGRADED.
89. Machine reason identity задаётся stable enum codes, не free-form exception text.
```

В RC2.x §23 был `RuntimeReasonCode` + `DiagnosticFact`, и эти инварианты были прямым следствием. В **RC3 §23 больше нет** `RuntimeReasonCode` / `DiagnosticFact`: их нет ни в §23.1–§23.7, ни в §24. Есть `ISOLATED / DEGRADED / UNKNOWN / SAFE / UNSAFE`, но нет описания модели machine reasons.

Два варианта:

- если архитектура **сознательно** сохраняет механизм RC2 — нужно вернуть его описание в §23 (например, §23.8 «Machine reason model»);
- если архитектура **сознательно** отказывается от него — invariant 89 надо переформулировать как «machine reason identity is stable across passes; do not base drift detection on mutable human text», без ссылки на enum codes.

Invariant 88 (не маскировать programming errors) остаётся полезным общим принципом, но должен явно сказать, **как именно** отличить programming error от expected failure, если `RuntimeReasonCode` больше нет в модели.

### A6. Invariant 93 «invalid kernel inventory» не говорит, что это KernelError

```
93. Interface inventory duplicate name with conflicting ifindex is invalid kernel inventory.
```

§23.1 говорит: «adapter не merge'ит их молча и возвращает `KernelError`.» Invariant 93 это имплицирует, но не формулирует. Правка: «... is a KernelError from the adapter, not a merge or a silent drop.» Иначе в реализации может появиться соблазн «взять первый/наименьший».

## B. Пробелы (нет инварианта, хотя поведение обязательное)

### B1. Readiness transition (BOUND с IP → BOUND без IP) не покрыт invariant 36

```
36. Binding transition detected -> best-effort ip_forward=0 before binding-sensitive
    policy mutation.
```

Binding transition (по §8.4) — это name/ifindex change или вход/выход из AMBIGUOUS. **Readiness transition без изменения binding** (IP пропал с существующего интерфейса, or added) — это **policy transition**, но invariant 36 её не включает.

Функционально §8.4 закрывает это через UNSAFE detection → deny-first repair (шаг 1 которого — `ip_forward=0`). Но это другой путь (через drift detection), не через «binding transition detected». В окне между UNSAFE detection и стартом deny-first repair `ip_forward=1`, старые binding-specific ACCEPT и MASQUERADE ещё в ядре, но они **inert** (нет IP на интерфейсе, поэтому `-d local_address` и `-o concrete` с отсутствующим IP не привлекают traffic). Fail-closed сохраняется через VPNG-FORWARD-DENY.

Правка: либо расширить 36 — «binding transition **or readiness transition without binding change**», либо добавить invariant: «Readiness transition is a policy transition; old binding-specific ACCEPT/MASQUERADE become stale and are replaced by deny-first repair on next pass; fail-closed during the window is provided by terminal daemon-owned guards (VPNG-FORWARD-DENY, VPNG-INPUT-GUARD), not by the stale binding-specific rules».

### B2. Output chain untouched — нет инварианта

§9 описывает INPUT, FORWARD, POSTROUTING. OUTPUT не упоминается нигде в invariants. Никто не говорит «daemon не создаёт правил в OUTPUT». Правка: «Daemon does not create, modify, or delete rules in the OUTPUT chain; OUTPUT policy belongs to host administrator.» Это важно для non-exclusive host scenarios, где admin может захотеть свои OUTPUT-правила.

### B3. Единая policy model для full + isolation filter — не инвариант

§23.5 говорит: «Обе формы выводятся из одной модели policy, чтобы compare/restore не имели независимых источников истины.» Invariant 53 говорит «single desired policy builder» — но неявно про один билдер, а не два derived form из одного билдера.

Правка: добавить «`desired_full_policy` and `desired_isolation_filter` are two derived forms of a single policy model; compare and restore never diverge into independent policy sources.»

### B4. Foreign NAT/OUTPUT rules preservation — не инвариант

Invariant 12 покрывает FORWARD, invariant 13 — INPUT. NAT/POSTROUTING не покрыт: VPNG-NAT chains RETURN after non-match, и foreign POSTROUTING rules физически сохраняются и **достижимы** для non-VPN egress. Это отличается от FORWARD (unreachable) и INPUT (retains value) — это третье поведение. Стоит добавить invariant: «Foreign POSTROUTING rules are preserved and reached for non-VPN egress because each VPNG-<PROFILE>-NAT returns on non-match. Daemon does not create rules that pre-empt arbitrary foreign NAT for non-managed egress.»

### B5. `OWNED` не переживает restart — не инвариант

Invariant 50 «OWNED changes only after verify» и 52 «kernel actual-state alone is not ownership» подразумевают, что OWNED — это process-local. Но нигде нет явного «OWNED and committed binding snapshot are process-local; they do not survive restart». §22 говорит «Неперсистентный runtime inventory (OWNED) не относится к persistent runtime-state», но это в §22, а не в invariants. Правка: добавить invariant или явно сослаться на §22.

### B6. `reconcile_interval` range — не инвариант

Invariant 40 говорит «cannot be disabled with 0». §13 говорит range `[1.0, 60.0]`. Инвариант range не фиксирует. Мелочь, но для консистентности стоит.

## C. Дублирование и косметика

### C1. Invariant 44 — частный случай 45

```
44. Missing BLACKHOLE adds выполняются раньше destructive route operations.
45. Route executor: blackhole adds -> exact deletes -> replaces -> remaining adds.
```

44 — это про первую фазу 45. Не вредно (44 подчёркивает safety-critical property), но если хочется компактности — 44 можно убрать, добавив в 45 подчёркивание «blackhole first is safety-critical, not just ordering».

### C2. Invariant 43 — следствие 42

```
42. Desired BLACKHOLE RouteSpec config-only; desired UNICAST RouteSpec config + concrete binding.
43. UNICAST RouteSpec.interface всегда exact concrete ifname.
```

43 — прямое следствие 42 (если UNICAST «config + concrete binding», то interface — это concrete binding). Дублирование безвредное, но можно свернуть 43 в 42.

### C3. Invariant 11/12 overlap

Уже разобрано в A2 (11 conflates) и A3 (12 scope). После правки A2 и A3 станут чёткими, но всё ещё дополняющими.

### C4. Invariant 30 — «after dynamic ACCEPT always exists unconditional REJECT» — верно per-destination

Формулировка точная, но не подчёркивает, что она **per-destination block**, а не «в конце chain один REJECT». §9.3 говорит: для каждого route — INVALID DROP, source ACCEPT, затем REJECT. Invariant 30 это подразумевает. Не проблема, но при желании можно уточнить «per protected destination block».

### C5. Invariant 63/64 — комплементарные, оставить

```
63. ACTIVE = policy SAFE + all profile results SUCCESS + ip_forward=1.
64. SAFE with profile FAIL -> DEGRADED; non-SAFE or insufficient policy observability -> ISOLATED.
```

Не дубли, 63 — определение ACTIVE, 64 — остальные состояния. Оставить.

### C6. Invariant 26 не упоминает INPUT-GUARD chain в перечислении

```
26. Profile INPUT exact chain завершает managed ready-interface traffic; unconsumed
    selector traffic закрывает deny-only VPNG-INPUT-GUARD.
```

Формулировка корректна, но нет отдельного invariant «VPNG-INPUT-GUARD существует как structural chain». §9.2 описывает, §9.1 называет в порядке jump'ов. Invariant 68 покрывает namespace. Не критично, но можно добавить явный list из structural chains (см. B7 ниже).

### C7. Structural chain enumeration — нет отдельного invariant

§9.1 перечисляет VPNG-INGRESS, VPNG-RESERVED, VPNG-INPUT-GUARD, VPNG-FORWARD-DENY, VPNG-<PROFILE>-{INPUT,FORWARD,NAT}. Invariant 68 говорит «namespace reserved», не перечисляя. Правка: добавить invariant «Daemon-owned structural chains: VPNG-INGRESS, VPNG-RESERVED, VPNG-INPUT-GUARD, VPNG-FORWARD-DENY, plus per-profile VPNG-<PROFILE>-INPUT, VPNG-<PROFILE>-FORWARD, VPNG-<PROFILE>-NAT». Это поможет реализатору и читателю.

## Сводка и приоритеты

**Стоит закрыть до code-refactor (A, реальные проблемы):**

| # | Проблема | Действие |
|---|---|---|
| A1 | Invariant 17: «kernel operand» противоречит guard в §9.2 | переформулировать как перечень запрещённых операций |
| A2 | Invariant 11: смешаны exclusive ownership и terminal verdict | разделить или явно связать в §2.3 |
| A3 | Invariant 12: нет scope «physically after prefix» | добавить scope + residual window |
| A4 | Invariant 57: «resolution failure» двусмысленна | разделить pass-level и per-profile |
| A5 | Invariants 88/89 ссылаются на отсутствующий в §23 механизм | вернуть в §23 или переформулировать |
| A6 | Invariant 93: не сказано, что это KernelError | одна фраза |

**Стоит добавить инварианты (B, пробелы):**

| # | Пробел | Важность |
|---|---|---|
| B1 | Readiness transition как policy transition | средняя — влияет на понимание при ревью |
| B2 | OUTPUT chain untouched | низкая, но полезная для non-exclusive сценариев |
| B3 | Full + isolation filter из одной модели | средняя — важно для будущей реализации repair |
| B4 | Foreign POSTROUTING preservation | низкая, но полезная |
| B5 | OWNED/binding snapshot process-local | средняя — важно для правильного понимания restart |
| B6 | reconcile_interval range `[1.0, 60.0]` | низкая |
| C7 | Structural chain enumeration | средняя — упрощает чтение |

**Косметика (C, дубли):**

- 44/45, 42/43 можно объединить, но не обязательно.
- 11/12 после правок A2/A3 станут нормально.

Из всего этого **A1–A6** — единственные пункты, которые я бы не советовал оставлять как есть до начала code-refactor: они либо imprecise, либо (A5) ссылаются на отсутствующую в RC3 модель. Остальное — «проговорить», не блокеры.