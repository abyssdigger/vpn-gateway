# Ревью RC3

Прочитал полностью (архитектура RC3, terms-and-definitions, journal с EXP-001..005). Это действительно крупный пересмотр. Изменения в основном следуют из EXP-004/005, а не «доработали на всякий случай». Ниже — что подтверждено и закрыто, что реально проблемно, и что стоит уточнить до начала code-refactor.

## Что закрыто относительно RC2.4.1 / прошлого ревью

- **Полное владение FORWARD decision** (§2.3, §9.3, invariant 11/12/28/29): после `ip_forward=1` любой forwarded пакет обязан получить терминальный вердикт в daemon-owned prefix, foreign FORWARD rules физически остаются, но недостижимы. Это закрывает EXP-004.1 явно.

- **Selector → binding → readiness** (§4.1–§4.4, §15, invariants 14–22): exact/prefix family selectors, `ABSENT/BOUND/AMBIGUOUS`, ifindex для обнаружения reuse. `+` наследует нативно проверенную EXP-005 семантику iptables interface prefix, а не shell glob. `vpns%` / numeric family из EXP-004.3 явно отменён в пользу `vpns+`.

- **Deny-first repair** (§8.6, §23.5, invariants 55–59, 95–98): isolation filter является полным daemon-owned filter desired state, verify изоляции — отдельный barrier result, full-policy `SAFE` требует NAT + full filter, verify'd на том же snapshot. Порядок обязателен даже при неудачном `set_ip_forward(False)`.

- **Runtime reconciliation binding-transition** (§8.4, §8.5, §11.1): binding transition идёт через отключение forwarding → deny-first barrier → восстановление, AMBIGUOUS на runtime = profile FAIL/DEGRADED с сохранением blackhole/deny.

- **Cleanup selective inventory** (§6.2, invariant 8, 9, 94): `proto 201/202` filtered queries для cleanup, полный strict inventory сохранён для normal reconciliation. EXP-004.5 показал, что это не понижает строгость на нужной семантике.

- **Runtime directory bootstrap** (§5.2, invariants 70–73): daemon сам ensure/validate `/run/vpn-gateway` (non-symlink, `0700`, owner = service identity, не «чинит» чужое владение через chmod/chown).

- **Runtime lifecycle state** (§8.9, invariant 63): `ACTIVE = policy SAFE + все profile SUCCESS + ip_forward=1`, при этом ABSENT не FAIL (если blackhole/deny verified), AMBIGUOUS = FAIL. `ACTIVE` явно отделён от «VPN connectivity доказана».

- **Package structure** (§23): multi-file Python package допустим; будущий Rust — один binary; entry point один.

Отдельно отмечу: **предложенный в прошлый раз `_commit_owned` перед `set_ip_forward(True)` теперь зафиксирован** (§8.8 «Commit после forwarding запрещён») с правильным обоснованием. Это то, что раньше в RC2.5.1 я предлагал сделать наоборот — RC3 выбрал более безопасную сторону.

## Реальные риски и вопросы

### 1. Profile FORWARD ACCEPT без `-i` — потенциальная дыра в окне реакции

§9.3 profile FORWARD ACCEPT:

```text
-s source -d route -o concrete → ACCEPT
```

Нет `-i`. Логика такая: LAN-трафик приходит с любого LAN-интерфейса, уходит на конкретный VPN `-o concrete`. Но в окне реакции (§4.4) ситуация: профиль BOUND к `vpns0`, только что появился `vpns1` (в том же prefix space `vpns+`). Профиль ещё AMBIGUOUS не объявлен (daemon не успел согласовать). Пакет приходит с `-i vpns1`, source = LAN source (спуф), dst = protected, `-o vpns0` (маршрут kernel выбирает по dest, не по `-i`):

- `VPNG-INGRESS` — `-i vpns0` не матчит `vpns1`, RETURN.
- `VPNG-RESERVED` — нет совпадения по dest.
- `VPNG-OC-FORWARD` — `-s source -d route -o vpns0` матчит → ACCEPT.

То есть спуфленный пакет из свежепоявившегося интерфейса в prefix space проходит через "правильный" bound-интерфейс. VPNG-FORWARD-DENY этот пакет не увидит — он ACCEPT'нут в profile chain.

Это **в пределах объявленной threat model** (invariant 91, §4.4), потому что:

- untrusted процессы не имеют `CAP_NET_ADMIN` и не создают интерфейсы;
- создаёт интерфейс доверенное VPN software.

Но: (a) сценарий специфичный — «malicious VPN peer в другом туннеле того же профиля спуфит LAN source» — в §4.4 **не назван** явно, хотя общая формулировка «residual trusted-host race» его покрывает; (b) добавление `-i` guard'а (или `! -i <все-selector-семейства>`) в profile FORWARD ACCEPT закрыло бы это без существенной потери — но это уже design change.

Как минимум стоит добавить одну строку в §4.4 или в invariant 91: явно назвать этот сценарий в списке residual window scenarios, чтобы имплементатор не подумал, что после `VPNG-FORWARD-DENY` всё под контролем.

### 2. Foreign FORWARD rule на позиции 1 — verification консистентен, но не задокументирован

Если внешний менеджер вставит правило в `FORWARD` на позицию 1, наш `VPNG-INGRESS` сдвинется на 2, profile chains на 3+, `VPNG-FORWARD-DENY` на last+1, foreign rules — после. Prefix verification (§9.1, §23.5) это поймает и объявит UNSAFE, а deny-first repair переставит. **Good.**

Но деталь: во время reordering prefix verification выполняется на текущем state. Если текущий state содержит foreign rule на позиции 1, `actual[:len(expected_prefix)] != expected_prefix` → UNSAFE. Repair применяет desired (которое тоже не знает про foreign rule на позиции 1 и просто строит prefix с 1 по last+1). После repair foreign rule окажется на позиции last+2, не на 1. Verification проходит. Это правильно.

Однако §5.4 говорит «unsupported», а invariant 12 «foreign rules недостижимы» — это подразумевает, что **после repair** они уходят после `VPNG-FORWARD-DENY`. Стоит одной строкой в §9.1 или §8.6 подтвердить: «если foreign rule физически находится перед daemon-owned prefix, verification это видит как UNSAFE, и deny-first repair переставляет prefix на позицию 1, отправляя foreign rules после `VPNG-FORWARD-DENY`». Иначе можно прочитать как «daemon каким-то образом находит foreign rules среди своих и удаляет», что неверно — они именно физически сдвигаются.

### 3. Тотальный краткий outage во время deny-first repair

§8.6: изолирующий фильтр удаляет все binding-specific ACCEPT rules **всех** профилей, не только того, чей binding меняется. Значит во время repair-окна (шаги 2–7) **все** managed VPN connections теряют forwarding.

Это **правильный fail-closed**, но:

- §8.6 явно говорит только про «stale ACCEPT rules, зависящие от binding, должны быть удалены» — это технически правильно, но оператор, читающий документ, может не сразу увидеть, что все профили затронуты;
- в §4.4 «reaction window» про это нет ни слова — там только про окно до первого reconciliation;
- в §24 «Binding-sensitive repair использует deny-first barrier» — тоже нет упоминания, что repair вызывает краткий outage всех профилей.

Стоит одной-двумя строками в §8.6 или §24 явно проговорить: «isolation filter is applied as complete daemon-owned filter state, therefore all binding-specific ACCEPT rules for all profiles are temporarily removed, and all managed forwarding is briefly denied even for profiles whose binding did not change». Это важно для оператора (understand what happens during repair) и для имплементатора (не пытаться «оптимизировать», оставив другие профили доступными — это нарушит barrier semantics).

### 4. `desired_isolation_filter` — конфликт с INPUT semantics для non-prefix selectors?

§23.5: "Изолирующий фильтр ... не содержит ACCEPT, зависящих от binding; сохраняет защитные правила INPUT селекторов, rejects транспортных сетей VPN, rejects защищаемых назначений и окончательный FORWARD deny."

Момент: "защитные правила INPUT селекторов". Для exact selector'ов (`wg0`) INPUT guard — это `-i wg0 -j REJECT`. Для prefix — `-i vpns+ -j REJECT`. В обоих случаях **deny-only**, что ок.

Но что происходит с profile INPUT chains в isolation filter? Они содержат binding-specific ACCEPT (INVALID DROP, ESTABLISHED ACCEPT, NEW ACCEPT из network к local_address). В isolation filter эти правила должны быть удалены. Значит profile INPUT chain в isolation state содержит только `RETURN`.

Стоит явно проговорить: **«В isolation filter profile INPUT chains содержат только RETURN (структурный placeholder), и всё входящее с managed interface'ов обрабатывается VPNG-INPUT-GUARD»**. Иначе неоднозначно: то ли profile chain очищается полностью, то ли остаётся частично.

Аналогично для profile FORWARD: **«В isolation filter profile FORWARD chains содержат только `-d route REJECT; RETURN` — unconditional REJECT для защищаемых назначений, без binding-specific ACCEPT»**.

Иначе имплементатор может решить, что в isolation filter profile chain остаётся INVALID DROP + ESTABLISHED ACCEPT (они не зависят от binding в смысле `-i`/`-o`, но зависят от того, что profile "has bound interface"). Стоит явно уточнить семантику.

### 5. Документация: EXP-001 ссылается на несуществующие invariant'ы

EXP-001 в журнале ссылается на «Invariant 134», «Invariant 148», «Invariant 153». В RC3 invariants переписаны и перенумерованы в 1–99. Этих номеров больше нет.

Формально эксперимент — исторический документ, и ссылки были валидны на момент его проведения (RC2.x). Но чтобы избежать путаницы при чтении RC3-современным читателем, стоит либо:

- добавить в шапку EXP-001 фразу «architecture references were valid at RC2 time; RC3 has renumbered invariants»;
- либо в разделе «Architecture references» привести актуальные номера из RC3 (или указать, что они были перенумерованы).

Мелочь, но при последующем чтении журнала и архитектуры рядом это сбивает.

### 6. `KernelInterface` signature — breaking change

§23.4 меняет `list_interface_ipv4() -> Mapping[str, frozenset[IPv4Address]]` на `list_interfaces() -> interface records including name/ifindex/IPv4`. Это правильное изменение (нужен ifindex), но:

- код RC2.5.1 всё ещё использует старую сигнатуру;
- тесты `test-vpn-gatewayd-kernel-rc2.wip.py` проверяют старую сигнатуру;
- любой другой клиент `KernelInterface` (mocks в других тестах) тоже.

Это TODO для code-refactor, не архитектурная проблема. Просто стоит в явном списке «breaking changes для следующего шага кода».

### 7. Специфичность `--check-config` для selector overlap

§15.3 говорит: «Управляемые селекторы должны быть попарно непересекающимися». Примеры:

```text
vpns+ + vpns0
vpns+ + vpns1+
vpns+ + vpns+
```

Всё верно. Но есть пограничный случай: `vpns0` (exact) + `vpns0+` (prefix). `vpns0+` матчит `vpns0`, `vpns00`, `vpns0abc`, ... Exact `vpns0` тоже матчит `vpns0`. Overlap. Это должно быть fatal. Проверка «пересечение множеств» это ловит. Good.

Другой пограничный: `a` (exact, 1 символ) + `ab+`. `ab+` матчит `ab`, `aba`, `abb`, ... Exact `a` матчит `a`. Пересечение пусто (ни одно имя не начинается одновременно с `a` и с `ab` — ну, `a` начинается с `a`, но не с `ab`). Значит disjoint. Формально OK.

Но интуитивно `a` — очень короткий exact selector. Если `ab+` зарезервирует `ab`, `aba`, ... то `a` остаётся. Не пересекаются. OK.

Так что overlap проверка через пересечение текстовых пространств имён корректна. Хорошо.

### 8. `--check-config` и `interface` spec validation

§15.1 говорит: «Regex: `[A-Za-z][A-Za-z0-9_.-]{0,14}`». Для exact selector.

§15.2 говорит: «Префикс соответствует тем же допустимым символам точного имени, начинается с ASCII-буквы и имеет длину 1..14».

Заметьте: prefix length 1..14, not 1..15. Это потому что `+` завершает selector и не входит в prefix. Значит total selector length `prefix + "+"` = 2..15. И exact selector length 1..15. Consistent.

Но всё же: для prefix `vpns` (4 chars) + `+` = 5 chars. Valid. Для prefix длиной 14 + `+` = 15 chars. Valid. Для prefix длиной 15 (не valid). Good.

`--check-config` должен валидировать это. Architecture says it does. Good.

### 9. `binding transition` и периодический reconcile timer

§8.4: «Binding transition ... считается policy transition».

§8.1 (implicitly): reconciliation triggered by Netlink event, periodic tick, full resync, administrative trigger.

Что происходит, если binding transition detected только на **периодическом** reconcile tick (Netlink event потерян, или Netlink ещё не пришёл)? Тогда до tick'а state не обновлён, работает со старым binding. Это соответствует §4.4 «reaction window». Периодический tick (10s default) — это `reconcile_interval`. То есть окно реакции может быть до ~10s.

Это документированный residual race. But the timer period 10s is a config; admin could set to 60s (max per §13), увеличив окно до 60s. Worth noting in §4.4: "residual window limits to reconcile_interval (default 10s, max 60s)". Не блокер, но полезно.

## Что стоит подтвердить / уточнить перед рефакторингом кода

1. **Явный список breaking changes** для `KernelInterface`, `VpnProfile`, `ReconciliationPlan`, `DaemonState`:

   - `list_interface_ipv4` → `list_interfaces` (с ifindex);
   - `CONFIGURED routes` как полный набор больше не корректно (инвариант §23.1);
   - `ReconciliationSnapshot` как pass-level immutable;
   - `desired_isolation_filter` как отдельный builder;
   - `RouteSpec.interface` всегда exact, никогда selector.
   - Все существующие тесты (`test-vpn-gatewayd-kernel-rc2.wip.py`, `test-vpn-gatewayd-config-rc2.wip.py`, `test-vpn-gatewayd-routes-rc2.wip.py`, `test-vpn-gatewayd-values-rc2.wip.py`, `test-vpn-gatewayd-bootstrap-rc2.wip.py`) будут ломаться.

2. **Изоляционный фильтр: точная структура для profile chains.** Стоит добавить в §23.5 или §9 одну-две фразы: «в isolation filter profile INPUT chains содержат только RETURN; profile FORWARD chains содержат только `-d route REJECT; RETURN`; profile NAT chains содержат только RETURN».

3. **Порядок ordering при binding transition.** §8.4 говорит «при binding transition best-effort привести `ip_forward=0`», затем «deny-first repair sequence». Но что именно считать «binding transition»? Если BOUND(vpns0) → ABSENT, это binding transition. Если BOUND(vpns0) → BOUND(vpns0) с тем же ifindex, но local_address исчез → это тоже binding transition? По §4.3 readiness требует local_address. Значит переход "BOUND с local_address → BOUND без local_address" — это readiness transition, а не binding transition. Но desired policy меняется (binding-specific ACCEPT/MASQUERADE исчезают). Считается ли это «policy transition» (требует deny-first repair) или это normal pass? §8.4 последний абзац: "Binding transition, включая BOUND -> ABSENT, ABSENT -> BOUND, BOUND(name/ifindex A) -> BOUND(name/ifindex B) и переход в/из AMBIGUOUS, считается policy transition." — readiness transition (BOUND with addr → BOUND without addr) не перечислен. Стоит явно: «readiness transition (BOUND with correct local_address → BOUND without) также требует deny-first repair, потому что desired binding-specific policy меняется».

4. **`--check-config` для selector overlap** — я вижу, что архитектура это проверяет, но стоит убедиться, что `--check-config` действительно это делает и что сообщение об ошибке явное (какие два селектора конфликтуют).

5. **`proto kernel` exact collision** — §23.6 упоминает, что "Exact protected prefix, совпавший с connected kernel route, fatal на startup." Хорошо. Но что при **runtime**? Если admin вручную добавит `proto kernel route` на exact protected prefix (что технически означает: подключён host-адрес с этим prefix), то:

   - binding snapshot не меняется;
   - policy может стать UNSAFE (если роут конфликтует с нашими desired routes);
   - next reconcile detect fail route pass;
   - apply не сможет добавить наш route (конфликт metric? или EEXIST?).

   Стоит подтвердить, что это fail-closed: reconcile pass с `_validate_plan` считает `proto kernel` в route_deletes → `PlanValidationError` → DEGRADED. Good.

## Итог

RC3 — сильная, хорошо обоснованная эволюция. Каждое крупное изменение следует из EXP-004/005. Инварианты консолидированы (99 вместо 174) и стали читаемее.

**Реальные риски:**

- явная дыра в окне реакции для FORWARD (в пределах threat model, но не названа явно);
- deny-first repair даёт полный краткий outage всех профилей (не задокументирован явно);
- неоднозначность структуры profile chains в isolation filter;
- EXP-001 ссылается на устаревшие номера инвариантов;
- readiness transition не входит в явный список «policy transitions».

**Не блокеры, но стоит закрыть до code-refactor:** список breaking changes для `KernelInterface` и других контрактов; явные фразы о том, что isolation filter — это полная замена, и что profile chains в нём содержат только structural part.
