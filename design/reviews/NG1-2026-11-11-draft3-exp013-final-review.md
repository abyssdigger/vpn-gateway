# NG1 Draft 3 + EXP-013 — финальное ревью

## A. B1–B5 закрыты корректно

Проверил все пять замечаний из предыдущего ревью:

**B1 (Device→host filter-first)** — §5.4 явно: *«first restrict the candidate set to enabled Profiles that reference the Device owning the packet's bound ingress interface, then perform longest-prefix matching of the packet source within that filtered set»*, плюс example с *«more-specific prefix belonging only to another Device must not shadow a less-specific valid Profile»*. Инвариант 30. ✔

**B2 (FORWARD default-DROP)** — §5.4: *«the ROU-owned FORWARD policy is `DROP`; canonical owned-chain order begins with `INVALID` rejection, then `ESTABLISHED,RELATED` acceptance for admitted flows, then policy for `NEW`»*. Инвариант 32. ✔

**B3 (IPv6 disable)** — §4.2: *«`disable_ipv6=1` where supported/required; merely disabling IPv6 forwarding is not sufficient»*. Инвариант 59. ✔

**B4 (envelope DROP precedes direction ACCEPT)** — §5.4: *«Device-envelope DROP/reject rules precede generated Profile-direction ACCEPT rules for the same transit path»*. Инвариант 34. ✔

**B5 (local table bypass)** — §5.3: *«This bypass is intentional: traffic from `host0` addressed to a ROU-owned local address ... must remain eligible for INPUT/local delivery and must not be captured by the forwarded-payload terminal action»*. Инвариант 60. ✔

Все пять закрыты точными формулировками, не декоративно.

## B. EXP-013 PASS — модель shadow fallback корректна

Проверил всё:
- **A1**: direct-dev multipath с двумя nexthops на одном metric принимается kernel. ✔
- **A2/B6**: ordering `normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC` работает, включая `/0`. ✔
- **A3**: multipath route **не** shринкается до survivors при исчезновении member interface — kernel удаляет весь multipath. Правильно, что TrafficEngine rebuild'ит из fresh binding set. ✔
- **A4**: same-name/new-ifindex — новая identity, kernel не восстанавливает прежний membership. ✔
- **B4**: ECMP — hash selection, **не** sequential failover. Confirmed с real OC payload. Явно зафиксировано: *«must not be described as ordered failover»*. ✔

Interpretation A3 в exp result честный: *«temporary blackhole-only state is fail-closed»*, никакого per-member retry. Persistent shadow модель сформулирована корректно. Инвариант 48 обновлён. §12 работает.

Один operational observation: **любой VPN client disconnect** (member disappearance) триггерит rebuild всего multipath для профиля через barrier. Это fail-closed по дизайну, но означает, что даже при healthy backup B, короткое окно во время rebuild'а — весь профиль fail-closed. Стоит одной строкой в §3.4 или §22: *«Multipath rebuild on member disappearance is a full-profile barrier; traffic fails closed during the transition even if surviving members are healthy»*. Не gap, но оператору полезно знать заранее.

## C. Новый finding (materialization detail)

### C1. Explicit DROP rules required for non-allowing direction

§5.4 говорит: *«NEW is accepted only from the side(s) allowed by the Profile direction»*.

Это читается двояко:
- **omission interpretation**: не создавать ACCEPT rule для не-allowing direction (fall through to terminal DROP);
- **explicit DROP interpretation**: создать NEW DROP rule для не-allowing direction.

Для большинства случаев оба варианта эквивалентны. Но **не для overlapping prefixes на shared Device с mixed directions**.

Контрпример (Device→host, оба Profile на oc-main):
```
P: 10.20.0.0/16   OUTBOUND     oc-main
Q: 10.0.0.0/8     BIDIRECTIONAL oc-main
```

Packet `10.20.5.5 → host` на `vpns00`:

Классификация (правильная):
- Filter by device: {P, Q} (оба ссылаются на oc-main)
- Longest-prefix: 10.20.0.0/16 (P)
- Direction: OUTBOUND → Device→host NEW не разрешён → **должен быть DROP**

FORWARD rules, **omission interpretation**:
```
-i vpns00 -o host0 -s 10.0.0.0/8 NEW ACCEPT     # Q BIDIR
terminal DROP
```

Packet `10.20.5.5` matches `-s 10.0.0.0/8` → **ACCEPT**.

**Это bug**: packet должен был классифицироваться как P (more-specific) → DROP. Классификация через RPDB и через FORWARD prefix-match дают разные ответы, потому что FORWARD использует omission.

**Explicit DROP interpretation**:
```
-i vpns00 -o host0 -s 10.20.0.0/16 NEW DROP     # P OUTBOUND, more-specific
-i vpns00 -o host0 -s 10.0.0.0/8   NEW ACCEPT   # Q BIDIR
terminal DROP
```

Packet `10.20.5.5` matches P's DROP first → **DROP** ✓
Packet `10.30.5.5` falls to Q's ACCEPT → **ACCEPT** ✓

То же самое для host→Device:
```
P: 10.20.0.0/16   INBOUND   oc-main
Q: 10.0.0.0/8     BIDIRECTIONAL oc-main
```

Host→`10.20.5.5`:
- RPDB: 10.20.0.0/16 → table_P → route oc-main
- Классификация: P, direction INBOUND → host→Device NEW не разрешён → DROP
- FORWARD omission: `-i host0 -o oc-main -d 10.0.0.0/8 NEW ACCEPT` (Q BIDIR) matches → **ACCEPT** ✗
- FORWARD explicit: `-i host0 -o oc-main -d 10.20.0.0/16 NEW DROP` matches → **DROP** ✓

**Требование**: явно зафиксировать в §5.4 (или §14), что materialization:

- Для каждого `(Profile, device)` pair, где prefix идёт от Profile, FORWARD rule **всегда** существует для NEW с verdict ACCEPT **или** DROP в зависимости от направления;
- Rules сортируются по длине prefix descending (совпадает с RPDB dispatch ordering §10);
- Omission of ACCEPT не считается достаточным для non-allowing direction при possible overlap.

Пример в §5.4 с corp (10/8) и support (192.168.50/24) — **не** overlapping, поэтому не показывает этот кейс. Стоит добавить overlapping-пример.

Severity: **medium**. Модель реализуема, но без явной формулировки реализация может дать fail-open на overlap+shared-Device кейсе. Не блокер имплементации (config validator ещё не запрещает такой конфиг), но must-fix перед первым production case с overlapping destinations.

## D. Minor

### D1. CHANGELOG entry for EXP-013 completion missing

Самый новый CHANGELOG entry — «NG1 Architecture Draft 3: direction/envelope/routing clarification» — говорит *«EXP-013 remains the implementation gate for unavailable common-metric projection»*. Но EXP-013 в experiments и в architecture уже `PASS`. Нужна запись в CHANGELOG (newest-first convention).

Не блокер (PROJECT-CONVENTIONS §8 говорит CHANGELOG not normative, architecture + experiments записали факт), но hygiene.

### D2. Persistent shadow fallback — clarifying example

Было бы полезно добавить в §12 один пример: для Profile с тремя bound interfaces (все UNKNOWN) в одной table одновременно:
- 3 normal routes (metric 1, 2, 3)
- 1 shadow fallback multipath (metric 65535, 3 members)
- 1 blackhole default (metric 65536)

Total 5 routes per destination. Это делает модель очевидной для операторов.

## E. Общая проверка

- Invariants 1–60 последовательны, нумерация без дыр. ✔
- Ссылки `§N.M` разрешаются. ✔
- `prefix%` отсутствует (только `prefix+` / `*/N`). ✔
- `peers` отсутствует. ✔
- `local_address` отсутствует. ✔
- `AMBIGUOUS` отсутствует. ✔
- Device-envelope capability surface зафиксирован (§6, §7.4). ✔
- Over-quota interface isolation (§5.5). ✔
- Bootstrap addressing stable (§4.1). ✔
- Device lifecycle sequence (§3.1.1). ✔
- Publication supervision (§3.4). ✔
- Return path без conntrack mark (§5.4, §8.2 concept). ✔
- BIDIRECTIONAL семантика через remote-prefix destination/source match. ✔
- v0→production migration boundary (§21.1). ✔
- Production testing layers (§21.2). ✔
- Representability model (§21.3). ✔
- Host-VPN coexistence (§21.4). ✔

## F. Verdict

**Draft 3 + EXP-013 — принимается с одной materialization clarification.**

Единственный реальный предмет для правки — **C1** (explicit DROP для non-allowing direction). Это не блокирует первый production slice (config validator пока не создаёт problematic case: для overlap+shared-Device+mixed-direction нужно специально сконфигурировать), но должно быть закрыто до первого deployment с overlapping destinations на общем Device.

Остальное — minor (CHANGELOG entry, clarifying example).

После C1 — architecture baseline NG1 Draft 4 является стабильной точкой для начала broader production implementation. Текущий `design/NG1/code/python/rou/` (27/27 tests) уже соответствует §21.2 layer 1 и может расширяться.

## G. Процесс

Ответ на мой предыдущий review (`NG1-2026-11-11-concept-architecture-review-response.md`) — эталонный:
- *«Two reviewer proposals are intentionally refined rather than copied literally»* — честно про B1 и B2/B3;
- мой ошибочный ASCII-sort для quota promotion отклонён с обоснованием (реинтродукция ordering churn), вы правы;
- моё предложение «global catch-all blackhole» заменено на `iif host0`-scoped — правильнее, я бы сломал return path;
- CHANGELOG says review archived verbatim в `design/reviews/NG1-2026-11-11-concept-architecture-review.md` — соблюдено PROJECT-CONVENTIONS §2.

Хороший цикл. Один малый gap остался (C1), но это именно то, что видно только при попытке применить модель к нетривиальному конфигу — модель в основном работает.
