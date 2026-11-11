# Ревью NG1 — концепт и архитектура

Сначала главное: **это не «выкинули неделю». Это использовали неделю правильным образом.** RC2/RC3 сгенерировали экспериментальную библиотеку (EXP-001..009), которая напрямую информирует NG1: fail-closed поведение, Netlink wakeup, ifindex identity, direct-dev routes, EXP-009 (никакой peer abstraction), IPv6 prerequisites. Это и записано в §21. Пайплайн «сложное → простое» — это нормальное инженерное движение, а не перепроектирование с нуля из-за бессонницы.

И, если честно, **смена топологии — это главная находка недели**, а не побочный эффект. Почти вся сложность RC3 (VPNG-* reserved namespace, position-1 invariants, INPUT-only vs transit drift classification, isolation barrier protocol, foreign rules classification, Fail2ban interop) была **прямым следствием выбора «daemon живёт в общем namespace»**. NG1 меняет одну вещь — владение namespace — и вся эта пирамидка рассыпается. Это правильный вывод.

---

## A. Что действительно солидно

### A1. Топология «router-in-a-box»

Один `rouvpn0` / `host0` veth pair, три класса трафика (forwarded payload, inbound transport, outbound transport) идут по обычному Linux L3. Никаких firewall-piercing tricks. Хост видит ROU как обычный маршрутизатор, ROU видит хост как обычный upstream. Это правильная абстракция для «маршрутизируй заданные префиксы через VPN».

### A2. Publication как relay, не как port-binding

В RC3 VPN-config привязывался к порту, и смена порта = reconfig VPN. NG1: VPN-config стабилен (`ocserv :44443`), publication меняется независимо. Это то, что делают Caddy/nginx fronting, stunnel, wstunnel; хорошо, что оформили как first-class primitive и подтвердили EXP-010/011.

### A3. Device/Profile split

Device = внешний ресурс (expected_interfaces + quota + publications). Profile = политика (direction + destinations + device_order). Разделение правильное и совпадает с тем, к чему сходятся NetworkManager, Tailscale, WireGuard-tools в admin-friendly обёртках.

### A4. `expected_interfaces` с quota — реальное улучшение

Позволяет Device декларировать «ожидаю либо `wg0` (exactly 1), либо до 5 `vpns*`» без reconfigure при добавлении интерфейса. Раньше в RC3 это требовало бы двух Profiles или переделки config.

### A5. Двухуровневый metric priority (device_order → expected_interfaces)

Хороший trade-off между coarse (Device priority) и fine (expected-interface priority), без произвольной вложенности. И `UNAVAILABLE_METRIC` / `BLACKHOLE_METRIC` как tail-резерв — правильный invariant для `/0` Profile.

### A6. UNKNOWN в normal tier

Ключевое решение, без него первая production-версия не могла бы маршрутизировать до появления availability detector. Правильно, что UNKNOWN ≠ AVAILABLE ≠ UNAVAILABLE, и что только positive UNAVAILABLE demotes.

### A7. Review-цикл NG1

6 findings, все закрыты, post-review PASS, implementation finding (overlapping selector example) пойман валидатором. Это здоровый сигнал. Не exhaustive, но правильное направление.

---

## B. Реальные gaps в спецификации

### B1. RPDB catch-all для неотправленного forwarded traffic

§5.1:
> Namespace main table is primarily the VPN transport/underlay routing domain. Typical meaning: `default -> host0`. Profile payload routing must not depend on the namespace main default.

Сценарий: host отправляет пакет к `rouvpn0` с destination **не входящим** ни в один Profile's `destinations[]`. Например, admin добавил host-route на `10.1.2.3/32 via rouvpn0`, но Profile с `10.1.2.3` ещё не существует.

Что происходит?
- **Если RPDB имеет catch-all `blackhole default`** → пакет дропается (правильно).
- **Если RPDB не имеет catch-all** → ROU main table → `default via host0` → пакет уходит обратно хосту. **Loop** (или двойная обработка, что тоже не то).
- **Если ROU main table имеет свой `blackhole default`** → дропается.

Ни в концепте, ни в архитектуре это не зафиксировано. Стоит добавить:

> RPDB содержит **финальное** `blackhole default` (или эквивалент), гарантирующее, что forwarded traffic, не совпавший ни с одним Profile dispatch entry, не попадает в ROU main table и не возвращается хосту.

Сейчас это либо «случайно работает» (если main table случайно имеет blackhole), либо «работает как loop» — без явной гарантии. Это блокер для fail-closed декларации.

### B2. Firewall-модель для shared Device между Profiles разной direction

§9: `direction` — per-Profile. §7: «Device may be shared by multiple Profiles».

Сценарий:
- Profile `corp`: `direction = "outbound"`, `device_order = ["oc-main"]`
- Profile `home`: `direction = "bidirectional"`, `device_order = ["oc-main"]`

Оба используют Device `oc-main`. ROU видит трафик через `vpns00` — но какой Profile его сгенерировал?

Firewall не знает «Profile». Он видит `iif`, `oif`, source, destination, conntrack state. Firewall должен различать «этот inbound VPN-пакет принадлежит BIDIRECTIONAL Profile home (allowed)» vs «принадлежит OUTBOUND Profile corp (must be rejected)».

Возможные модели:
1. **Per-destination filter** (natural, destinations disjoint): правило `-d 192.168.1.0/24 -i vpns00 -m conntrack --ctstate NEW -j ACCEPT` для home; `-d 10.0.0.0/8 -i vpns00 -m conntrack --ctstate NEW -j DROP` для corp. Работает, потому что destination disjoint глобально.
2. **Conntrack mark при dispatch**: packet приходит на `host0`, RPDB dispatch ставит mark по Profile; firewall фильтрует `-m mark --mark <profile_id>`. Сложнее, но семантически чище.
3. **Per-interface per-direction filter**: `iif host0 oif vpns00 ctstate NEW ACCEPT` для OUTBOUND; `iif vpns00 oif host0 ctstate NEW ACCEPT` для BIDIRECTIONAL. Но это не различает corp vs home для inbound traffic — оба идут `iif vpns00 oif host0`.

Модель 1 работает, модель 3 — нет (для shared Device). §14 говорит «TrafficEngine ... payload firewall/NAT policy», но не детализирует. **Это блокер для production-реализации**: без явной модели firewall можно реализовать что-то, что в common-case работает, а на shared-Device кейсе имеет дыру.

Рекомендация: зафиксировать в §10 или §14 явно:

> Firewall rules по Profile определяются destination-prefix: разрешающие/запрещающие правила строятся на `(destination, Profile)`, а не на `(interface, Profile)`. Since destinations disjoint by invariant 26, rules are non-conflicting. Device interface per destination resolves routing, not firewall classification.

### B3. `direction` + conntrack state model

§9 описывает direction семантически (NEW from host/VPN/both), но не уточняет conntrack.

Для OUTBOUND corp:
- NEW from `host0` → forward → allowed (firewall rule)
- ESTABLISHED/RELATED from `vpns00` → forward → allowed
- NEW from `vpns00` → rejected by firewall

Но в conntrack NEW не появляется «от vpns00» для conn, инициированного из host. ESTABLISHED появляется. Хорошо.

А что если оба конца инициируют независимо? Например corp = OUTBOUND, но VPN-peer одновременно инициирует conn к хосту. `NEW from vpns00` — drop. Good.

Для BIDIRECTIONAL home:
- `NEW from host0` — allow
- `NEW from vpns00` — allow
- `ESTABLISHED,RELATED` — allow в обе стороны

Это работает через стандартную conntrack семантику. Но нужно явно зафиксировать:

> Firewall filter использует conntrack: `NEW` разрешается в направлении(ях), указанных `direction`; `ESTABLISHED,RELATED` разрешено в обоих направлениях; `INVALID` дропается.

Без этой фиксации можно реализовать через stateless rules и получить обратный доступ через RETURN traffic, не помеченный как ESTABLISHED.

### B4. VPN process lifecycle — startup order и ownership

§13:
> DeviceEngine does not manage the Device itself. In particular the first production model does not require it to start, stop, restart, configure or repair a VPN transport.

Хорошо, это deferred to DeviceManager. Но **последовательность** не зафиксирована:

1. `rou up` → namespace → publication sockets → fail-closed state
2. VPN process (ocserv/wg) стартует **внутри namespace** — кто его запускает? Admin через `ip netns exec`? DeviceManager?
3. Interface появляется → DeviceEngine discovers → bind → TrafficEngine materializes routes

Если admin не запустил VPN, ROU остаётся fail-closed — правильно. Но без явной документированной последовательности admin не знает «start ROU then VPN» или «start VPN then ROU» или порядок не важен.

Технически порядок не важен (оба состояния valid), но для документации стоит явно сказать:

> Deployment sequence: ROU starts first in fail-closed state; VPN transports are started independently (by admin or future DeviceManager) inside the ROU namespace; ROU discovers their interfaces via normal Netlink observation and materializes traffic.

Плюс: **где именно admin запускает VPN-процесс?** В ROU namespace через `ip netns exec`. Это меняет deployment story относительно RC3 (где всё было в main namespace). Стоит добавить в §20 или в новый раздел §4.x пример «запуск VPN transport внутри ROU».

### B5. Publication relay — supervision

§2.4: «follows the ROU instance lifecycle». §3.1: step 5 — prepare publications. §3.2: step 1-2 — close them.

Но: **кто держит relay-процесс?** Relay живёт в main namespace (bind host-сокет) и форвардит в netns. Он должен:
- стартовать при `rou up`
- умирать при `rou down`
- перезапускаться при краше (иначе publication «тихо ломается»)

Если supervisor — systemd `rouvpn@<instance>.service`, то relay — часть его cgroup. Если что-то другое — надо уточнить.

Not blocking (v0 hardcodes it), but for production важна определённость.

### B6. `rp_filter` и forwarding sysctls в ROU namespace

§4 «namespace-local IPv4 sysctls» упоминает, но не детализирует.

Для BIDIRECTIONAL Profile traffic идёт `iif host0 oif vpns00` и `iif vpns00 oif host0`. Source VPN-адрес для `vpns00` — ROU main table may not have route back to source → `rp_filter=1` (strict) дропнет. Нужен `rp_filter=0` или `2` (loose) на соответствующих интерфейсах.

Аналогично `forwarding=1` внутри namespace. И `ipv6.disable_ipv6=1` для IPv4-only (унаследовано из RC3 §2.6).

Стоит явно перечислить minimal required namespace sysctls в §4 или новом §4.5.

### B7. Bootstrap config vs router config — где link addressing

§4:
> Bootstrap configuration defines **how the appliance is isolated and launched**. Router configuration defines **what the appliance routes and how profiles behave**.

Хорошо. Но §3.1 step 4 «configures link addressing» — а что конкретно? `192.0.2.1/30` на `rouvpn0`, `192.0.2.2/30` на `host0` — это bootstrap config? Или router config? Или auto?

Хост должен знать, куда маршрутизировать VPN destinations. Значит адрес `rouvpn0` критичен. Если он меняется между запусками — BOU/host routing ломается.

Явной формулировки нет. Стоит добавить раздел «Link addressing contract» с:
- кто выбирает адреса (admin);
- где они живут (bootstrap config);
- они не меняются без явного config change;
- host routing (BOU или manual) должен ссылаться на `rouvpn0` адрес.

---

## C. Меньшие замечания

### C1. Destination dispatch и RPDB rule set

§10:
> ROU builds global dispatch entries from all: (destination, Profile) and serializes them deterministically by: prefix length descending, network address ascending.

Это RPDB **rule** order? Или правило в одной таблице? Обычно RPDB rule применяется к каждому пакету до принятия решения о таблице. Правильная модель:

```
priority 10: to 10.1.2.3/32 lookup profile_corp
priority 20: to 10.0.0.0/8 lookup profile_corp
priority 30: to 192.168.1.0/24 lookup profile_home
priority 10000: blackhole  (catch-all)
```

Rule priority задаётся по «prefix length descending» — да, matches §10.

Но: если два Profiles имеют overlap `10.0.0.0/8` (corp) и `10.1.2.3/32` (home), то `10.1.2.3` → home, другие 10.x → corp. Это работает **только если home rule идёт раньше corp rule**. «prefix length descending» это гарантирует. Хорошо.

Однако §10 говорит «overlap at different prefix lengths is allowed» — это в destinations, не в RPDB rules. Всё консистентно.

### C2. Про shared Device: сколько bindings на Profile

Device с `expected_interfaces = ["vpns*/5"]` может создать до 5 bindings. Если Profile использует этот Device, все 5 становятся его paths.

Но: **все 5 — на одном Device**. Metric priority: device_order ставит Device на какую-то позицию. Внутри этого Device — expected_interface order. Так как все 5 из одного `vpns*/5`, они имеют один range, разные slots.

Metric assignment: 5 slots на одна expected_interfaces entry. Каждый получает slot по arrival order (survivor keeps slot). OK.

### C3. Quota promotion порядок

§7.2:
> If a bound interface disappears and the disappearance is verified and committed, a previously over-quota matching interface may occupy the freed quota on a later reconcile.

Какой из over-quota promoted? «Any» не годится — недетерминизм. Стоит зафиксировать:

> When promoting over-quota candidates to freed slots, use deterministic ordering: **first by the same rule as normal admission (bitwise ASCII ifname) for reproducible behavior; survivor keeps previous admission rule**.

Или, если it doesn't matter (over-quota all functionally equivalent), сказать это явно. Сейчас ambiguity.

### C4. `[a-z0-9][a-z0-9-]*` разрешает `1device`

Идентификаторы, начинающиеся с цифры, парсятся в TOML как `[device.1foo]` — bare key `1foo` валиден в TOML. Но:
- некоторые CLI tools (bash, `rou show 1device`) могут интерпретировать как argument;
- logs могут выглядеть как «1 device» — ambiguous;
- `systemd` unit names с digit first — deprecated convention.

Обычно «boring IDs» начинаются с буквы. Если хотите digits-first — ок, но проверьте, что не создаст friction в CLI.

### C5. Destination dispatch для Profile без /0

Profile `home` с `destinations = ["192.168.1.0/24"]`. RPDB dispatch: `to 192.168.1.0/24 lookup profile_home`. Всё ок.

Но что если host отправляет 192.168.1.5 → dispatch → profile_home table → route via vpns00 → out. Return comes from vpns00 → profile_home table (iif vpns00) → route to host0 → host. OK.

А если host отправляет **source** из VPN, destination вне home? Не dispatch in home table. Falls to RPDB catch-all → blackhole (если B1 fix). Good.

### C6. Multi-Profile destinations с одним Device

Profile corp `destinations = ["10.0.0.0/8"]`, Device oc-main.
Profile home `destinations = ["192.168.1.0/24"]`, Device oc-main.

Один vpns00 может быть bound to both Profiles. Metric assignment per (Profile, ifname, ifindex) — так что vpns00 может иметь metric 10 in corp и metric 10 in home (different tables). Correct per §11.

### C7. Publication с external port ≠ internal port

§2.4 «For equal external/internal ports the right side may later be made optional as shorthand». `44443/tcp>44443` vs `44443/tcp` (shorthand).

EXP-011 закрыл same-port кейс. Но **для arbitrary port translation** с advertised endpoints (как DTLS в OpenConnect) — это работает только если protocol knows to advertise external port. Как EXP-011 result честно говорит: «Arbitrary external/internal port translation for protocols that advertise transport endpoints remains protocol-specific and is not implied by EXP-011.»

Хорошо, что не over-claim. Но grammar всё ещё «open» (§6). Пока grammar deferred — ок.

### C8. Traffic envelope concept is deferred but underspecified

§7.4 «Device traffic envelope» — Device-side hard ACL on tunnel traffic. Пока только abstract.

Для production это нужно. Но можно отложить до первого use case. Стоит хотя бы sketch:
- «только destination set в X» (несколько CIDRs);
- «только protocol/port Y» (для services);
- «только from-source Z» (для inbound);

Без sketch невозможно понять — это per-Device или per-Profile? Это влияет на data model.

### C9. Multi-interface per Device: сколько одновременно?

Quota ограничивает bindings, но не ограничивает **observed** interfaces. `vpns*/5` с 20 реальными интерфейсами — все 20 наблюдаются, 5 bound. Over-quota видны в status.

Что происходит с over-quota traffic? Firewall не имеет правил для них (only active bindings), routes нет. Следовательно, пакеты к over-quota interface → RPDB dispatch → profile table → route exists? Нет route → blackhole default → dropped. Хорошо.

Но interface существует. Если over-quota interface посылает inbound пакет → RPDB dispatch → profile table → route (существующий через другой interface) → forward? Это плохо. Отдельная firewall rule должна дропать.

Не critical, но стоит явно зафиксировать:

> Interfaces matching ExpectedInterface but over-quota (or unbound for any reason) have no firewall ACCEPT and no route; inbound traffic from them is dropped by terminal blackhole. Их существование не влияет на forward path.

### C10. Reverse path — RPDB dispatch на inbound от VPN

Inbound VPN пакет приходит на `vpns00` с destination `10.0.0.5` (in 10/8). RPDB dispatch:
- rule `to 10.0.0.0/8 lookup profile_corp`
- packet matched → profile_corp table
- profile_corp table: route `10/8 → vpns00 metric X` — но wait, this is a route for outbound, not inbound.

Проблема: RPDB dispatch by destination doesn't distinguish direction. Inbound packet from vpns00 with destination 10.0.0.5 dispatches to profile_corp table. There's a route `10/8 → vpns00`. So ROU will route the packet right back out vpns00. **Loop!**

Firewall должен предотвратить это до маршрутизации. Правило типа:
- `iif vpns00 -d 10.0.0.0/8 -m conntrack --ctstate NEW -j DROP` (для OUTBOUND)
- или `iif vpns00 -d 10.0.0.0/8 -j DROP`

Для BIDIRECTIONAL так нельзя — inbound должен идти к host. Но destination 10.0.0.5 для inbound bidirectional? Это VPN peer sends to... what? Если host accepts inbound, destination должен быть host address, not VPN destination. Так что даже BIDIRECTIONAL inbound new connection to 10.0.0.5 (VPN destination) — bad, should be DROP.

Hmm actually this requires careful firewall design. Not a gap if firewall model (B2) is properly specified. But reinforces the need for B2.

### C11. Reverse path — main table также для inbound VPN transport

When VPN transport arrives (inbound transport, not payload):
- packet arrives on `host0` (from host, going to VPN listener inside namespace)
- destination is local (e.g., `192.0.2.2:44443`)
- ROU main table: local delivery → 44443 listener

Хорошо. Но: firewall в ROU должен разрешить это (`iif host0 -d 192.0.2.2 -p tcp --dport 44443 -j ACCEPT` или «allow transport publication internal delivery»).

Publication relay — это host-side socket, но фактический listener — inside namespace. Inbound transport packet goes: host → relay (host ns) → tunnel → inside ns (source = host0 addr) → local delivery to 44443.

Firewall в ROU должен recognize это. Не явно — но по факту «local delivery allowed» обычно default. Или нужно явное правило.

### C12. Если Device disabled, но Profile enabled ссылается

Valid по §10 («known enabled=false Devices are valid references and are skipped operationally»). Profile corp references `["oc-main", "wg-backup"]`, wg-backup disabled → uses only oc-main.

Что если `oc-main` fails (interface disappears)? Profile corp has no active binding → fail-closed (BLACKHOLE_METRIC, terminal blackhole).

Good. Should be documented as expected behavior — но по факту это правильно из существующей модели.

### C13. ROU external interface IP = 0.0.0.0/0? 

§2.2 говорит: «ROU does not know which host-side sources are trusted».

Правильно. Но ROU должен **принимать** forwarded traffic с любого source, если он диспатчится в profile. Firewall OUTBOUND rule: `-i host0 -d <profile destination> -m conntrack --ctstate NEW -j ACCEPT`. Source не ограничен — правильно, host решает кто может.

Firewall INBOUND rule: `-o host0 -i <device> -m conntrack --ctstate NEW -j ACCEPT`. Source = VPN peer. Return from host: `ESTABLISHED,RELATED` allowed.

OK. ROU «не знает» про source trust, но conntrack отслеживает return path. Правильно.

---

## D. Что missing на концептуальном уровне

### D1. Transition v0 → production

v0 = hardcoded, one OC Device, one OUTBOUND Profile, capacity 2, one destination. Production = generic.

Между ними: как отличить «правильный v0 lesson» от «v0 hardcode shortcut»? §20.1 говорит «hard-coded prototype may now be used as verified executable evidence while implementation moves toward generic NG1 model». Но что конкретно reuse, что переписать?

Стоит добавить раздел «v0 → production migration»:
- reuse: namespace lifecycle, publication relay, drift repair barrier, verification-before-commit, canonical filter/NAT comparison, fatal teardown on structural loss.
- rewrite: config parsing, Device abstraction, Profile abstraction, multi-Device metric allocation, availability model, multiple Profiles.

Это поможет при implementation.

### D2. Testing strategy для production

EXP-012 был live gate для v0. Для production — что?

Не блокер, но стоит зафиксировать:
- Unit tests for config/domain/routing projection (rootless);
- Integration tests for kernel boundary (netns, no real VPN);
- Live gate for full lifecycle (real ocserv);
- Regression suite to run per PR.

CI already validates compileall + unit suite (per CHANGELOG). Но live gate procedure не формализован.

### D3. Scale limits

Сколько Profiles? Сколько Devices? Сколько bindings per Profile? Не ограничено явно.

Для small deployment это неважно. Для production — важно, потому что route table size (per Profile table) и metric ranges имеют пределы.

Стоит хотя бы указать:
> First production target: up to N profiles, M devices, K bindings per profile. Beyond that: separate analysis.

Или, если предела нет — сказать «unbounded, tests scale as O(profiles × bindings)».

### D4. Interaction with host VPN

Если host уже имеет VPN (WireGuard/OpenVPN на host), и admin добавляет ROU с VPN — как они сосуществуют?

Ответ: host routing выбирает. BOU/forwarding rules решают. ROU не знает. Но operational guidance отсутствует.

Not blocking (BOU deferred), but worth a paragraph in concept.

---

## E. Что я бы хотел увидеть перед code

Перед code-refactor production-реализации NG1:

1. **B1 (RPDB catch-all)** — критично, без этого fail-closed не guarantee'd.
2. **B2 (Firewall model per-Profile)** — критично для shared-Device.
3. **B3 (Conntrack state model)** — критично для direction semantics.
4. **B4 (VPN lifecycle)** — operational, but affects deployment.

Все четыре — одна-две страницы текста. Не блокируют conceptual level, но блокируют production-level code.

## F. Меньшие gaps

C1-C13 — worth addressing progressively:
- C3 (quota promotion order) — детерминизм, easy fix.
- C4 (leading digit) — trivial, decide and document.
- C7 (traffic envelope sketch) — useful, not blocking.
- C9 (over-quota traffic) — fails closed правильно, но стоит явно зафиксировать.
- C10-C11 — resolves once B2/B3 specified.

## G. Verdict

**Архитектура и концепт в целом правильные.** Pivot с RC3 → NG1 корректен и радикально упрощает систему за счёт единственного архитектурного решения (владение namespace). Это не «выкинули неделю», а «нашли правильную абстракцию через неделю экспериментов» — нормальный паттерн.

Review-цикл (6 findings → response → post-review) здоровый. Implementation finding (overlapping selector example) пойман валидатором — хороший знак.

Для перехода от concept/architecture к production implementation нужно закрыть **4 реальных gaps** (B1-B4) плюс несколько lesser concerns. Не блокеры для текущего этапа, но блокеры для следующего code-refactor'а.

**Рекомендую следующий цикл:**

1. Fix B1-B4 в architectural text (несколько страниц).
2. Add scale limits (D3).
3. Add v0 → production migration section (D1).
4. Add testing strategy section (D2).
5. Тогда — code.

---

## Уточнение владельца архитектуры

> "Firewall не знает «Profile». Он видит iif, oif, source, destination, conntrack state. Firewall должен различать «этот inbound VPN-пакет принадлежит BIDIRECTIONAL Profile home (allowed)» vs «принадлежит OUTBOUND Profile corp (must be rejected)»." - нет, здесь как раз предполагался кондовый фаерволл на девайс для администартора - "сегодня с той стороны dev-01 к нам может ходить только Урюпинск, потому что Заборску сломали сетку и я им не верю, а вот на dev-02 мы сегодня прикрываем наш трафик на 8007, потому что были слухи, что он нас ломают проксмоксы, и я еще не отследил этого гада". Т.е. это общие firewall-политики на туннель, которые нельзя навесить на уровне хоста (там все детали  "кто, куда, кому и сколько" теряются)

## Ответ reviewer на уточнение

# Принял поправку — переформулирую B2

Я неправильно понял модель. Думал, что `direction` — это политика, которую firewall должен как-то энфорсить per-Profile. А это **routing semantics**, и фильтрация — отдельный слой на Device.

Тогда картина становится чище:

```
direction   = routing / dispatch semantics (какие iif допускаются к таблице Profile)
traffic_envelope (Device) = реальный firewall админа (что можно, что нельзя, кому, куда)
```

И моё «firewall должен различать Profile» — неверно. Firewall различает **Device interface** (`iif vpns00`, `oif vpns00`), а Profile — это маршрутизация по destination. Два Profile, шарящие oc-main, диспатчатся по destination, а firewall на vpns00 применяет **одну и ту же** envelope-политику к обоим.

Ваши примеры:
> «сегодня с той стороны dev-01 к нам может ходить только Урюпинск… а на dev-02 мы прикрываем наш трафик на 8007»

— это именно **Device envelope**, per-tunnel, admin-authored. В хосте это невыразимо, потому что хост до encap видит только `iif=lan, oif=rouvpn0` и не знает, через какой device пойдёт пакет. После decap — ещё хуже: хост вообще не видит этих пакетов. Так что envelope — **единственное** место, где эта политика может жить.

Это снимает моё возражение про «два Profile на Device с разным direction». Ответ: firewall не должен различать direction, он должен различать **Device** (правильно) и **трафик** (source/dest/port). Direction — orthogonal routing concern.

---

## Что это меняет в моём ревью

### B2 переформулирован

Было: «firewall должен уметь различать Profile в shared-Device сценарии».
Стало: **этого не нужно**. Модель:

```
dispatch (per-Profile, RPDB) → profile table → device interface (routing)
                     ↓
              firewall на device (envelope, admin)
```

Direction энфорсится через routing:
- `OUTBOUND`: dispatch только `iif host0` → profile table → route device;
- `INBOUND`: dispatch только `iif <device>` → profile table → route host0;
- `BIDIRECTIONAL`: dispatch без iif constraint.

Это RPDB-level constraint, не firewall. Firewall (envelope) — независимый слой на interface.

### B1 (RPDB catch-all) — становится критичнее

Раньше думал, что это мелочь. Теперь понимаю, что это **механизм return path**.

Проблема: VPN reply (dest = host-address) не попадает ни в один Profile destination → RPDB не диспатчит → fallback на main table. Но main table не должен иметь `default dev host0` без ограничения (иначе loop). А catch-all blackhole ломает return для ESTABLISHED.

Три возможные модели:

1. **Conntrack mark**: outbound flow marks conn, return packets match `fwmark` → route host0. Unmatched NEW → blackhole. Требует `iptables -t mangle -j MARK` или nftables.
2. **State-based RPDB**: return-таблица с `default dev host0`, диспатчится только по `ESTABLISHED` через отдельный conntrack-match (нет в стандартном ip rule, нужен mark).
3. **Firewall-страж на oif**: main table `default dev host0`, firewall `oif host0 ctstate NEW -j DROP` — но тогда INBOUND Profile не работает (New from VPN→host).

Модель 1 — чище всего, но добавляет mangle/conntrack mark в ROU. Это architecture decision, которого сейчас нет в документе. **Это gap**, и он теснее связан с direction, чем с catch-all как таковым.

Рекомендация: добавить в §5.1 или новый §5.4 explicit model:

> Return path for ESTABLISHED flows от bound Device к host0 обеспечивается через [conntrack mark / per-direction routing table / другой механизм]. Unmatched NEW traffic к destination вне dispatch routes → blackhole. Точный механизм — implementation decision, но семантика (return works, unmatched drops) — normative.

Без этого невозможно guarantee'd fail-closed + working bidirection в одной модели.

### B4 (VPN lifecycle) — не затронут, остаётся

По-прежнему нет explicit deployment sequence: «start ROU → start VPN in namespace → discover». Это операционный gap, не архитектурный.

### C10-C11 (reverse path) — теперь резолвятся проще

С правильной моделью firewall (envelope) + routing (direction через iif) + return path (B1 модель):
- VPN→VPN forwarding (inbound from vpns00 to VPN destination): dispatch → profile → route vpns00 → loop. Дропается через envelope: `iif vpns00 -d <profile destination> -j DROP` — это **admin decision**, не ROU. Или ROU ставит дефолт, admin расширяет.

Это не fire-and-forget; это часть envelope policy. Правильно, что admin решает.

### C7 (Device envelope syntax) — теперь HIGH priority

Было «deferred». Теперь понимаю: **это и есть основной admin-facing интерфейс firewall**. Ваш «кондовый фаерволл на девайс» — это то, что админ пишет каждый день, как в вашем примере («сегодня с той стороны dev-01 только Урюпинск»).

§6 rou-config.md говорит «Device traffic-envelope syntax» не закрыт. Это становится **первым приоритетом** после Device/Profile base model, потому что без него нет admin workflow.

Минимально должна выражать:
- source whitelist/blacklist (для вашего примера про Урюпинск);
- destination:port filter (для вашего примера про 8007);
- protocol (tcp/udp/icmp);
- direction (inbound/outbound to tunnel).

Скорее всего, это natural syntax на основе чего-то типа nftables-like rules или простой JSON с массивом правил. Не буду угадывать синтаксис, но рекомендую добавить хотя бы **sketch** в документ, чтобы было видно, что модель поддерживает ваши примеры:

```
[device.oc-main.envelope]
inbound = [
  { action = "accept", source = "10.50.0.0/16" },   # Урюпинск
  { action = "drop" }                                # остальное
]
outbound = [
  { action = "drop", dest = "0.0.0.0/0", port = 8007 },  # проксмоксы
]
```

(это sketch, не contract).

### C3 (quota promotion order) — не затронут

Остаётся: при освобождении slot, кто из over-quota promotes? Нужно детерминированное правило.

### BIDIRECTIONAL — теперь совсем непонятен

С моделью «direction = routing», `BIDIRECTIONAL` не имеет чёткой семантики:

- Dispatch без iif constraint → любой пакет к destination идёт в Profile table.
- Route к destination — это route к одному Device interface. Значит, либо из host0 → VPN, либо из VPN → host0, но не оба.
- Обратный flow от VPN к host (dest = host) не идёт в этот Profile (dest не в `destinations`), а fallback в main.
- Значит BIDIRECTIONAL сводится к: «и host, и VPN могут инициировать flow, и routing определяется по destination».

Для `destinations = ["10.0.0.0/8"]` (VPN-side):
- Host→10.0.0.5: dispatch → route vpns00 → out. ✓
- VPN→10.0.0.5: dispatch → route vpns00 → loop. Admin должен envelope-DROP'нуть это (что и есть «не хочу, чтобы VPN-сторона инициировала»).

Для `destinations = ["192.168.1.0/24"]` (host-side, INBOUND-ish):
- VPN→192.168.1.5: dispatch → route host0 → out. ✓
- Host→192.168.1.5: обычно уже не идёт через ROU.

Так что BIDIRECTIONAL — это, кажется, «маршрутизируй в обе стороны к тому, что в destinations, а кто может инициировать — решает envelope». Но тогда это то же, что и OUTBOUND или INBOUND в зависимости от того, куда destinations указывают.

Нужен явный пример в документе: что значит BIDIRECTIONAL и как это отличается от OUTBOUND/INBOUND на конкретном кейсе. Иначе implementation будет угадывать.

---

## Что предлагаю

Минимально к тексту (перед code):

1. **Explicit model** в §5.1 / §14: direction = routing-level iif constraint; envelope = firewall. Два слоя, orthogonal.
2. **Return path model** в §5.1: как VPN reply доходит до host (conntrack mark или эквивалент). Без этого fail-closed не работает для bidirectional.
3. **Device envelope syntax sketch** — даже если не финализирован, зафиксировать capability surface (source, dest, port, proto, direction). Ваши примеры — canonical use cases.
4. **BIDIRECTIONAL example** — один-два конкретных сценария.
5. **Quota promotion rule** — детерминированный порядок.

Это по-прежнему не блокирует реализацию ROU v0 (v0 = one Device, one OUTBOUND Profile), но блокирует generic production.

---

## Что понял про сам NG1

Пересмотрев всё с этой поправкой, **NG1 стал существенно чище**:

- Firewall = per-Device envelope, admin's daily tool.
- Direction = routing preference, ROU-generated (no admin rules).
- Profile = policy (destinations + device_order + direction hint).
- Device = external resource (expected_interfaces + envelope + publications).

Разделение ролей теперь чистое. Мои B2-B3 evaporate'нули как «не те gaps». Остались:
- B1 (return path) — стал критичнее;
- C7 (envelope syntax) — стал HIGH;
- BIDIRECTIONAL semantics — нужен пример.

Всё остальное из моего ревью в силе (B4, C3, C9, D1-D3), но с меньшим приоритетом.

Поправка полезная — без неё я бы предлагал городить per-Profile firewall, что противоречит вашей модели. Хорошо, что остановили.
