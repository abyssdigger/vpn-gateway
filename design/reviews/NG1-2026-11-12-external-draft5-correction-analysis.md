# Ревью внешнего ревью

Проверил каждое положение против Draft 4, кода и EXP-013. Резюме: **ревьюер прав практически по всем пунктам**, включая три серьёзные находки. Причём пункт 4 поймал моё собственное переусердствование в прошлом ревью.

Ниже — по пунктам.

---

## 1. Return path для inbound/bidirectional — реальный баг

**Проверка.** §5.4 говорит: *"Return routing needs no architecture-mandated conntrack mark: Device -> host return traffic is accepted as `ESTABLISHED` and follows main `default -> host0`"*.

Это верно для OUTBOUND:
- host → 10.0.0.5 (NEW, admitted) → RPDB dispatch по destination → Profile table → metric выбирает vpns00 → out.
- Reply 10.0.0.5 → host (ESTABLISHED) → main table → host0 → host.
- ✓ Correct, no mark needed.

Для INBOUND с multi-interface:
- Remote (via wg-backup) → host (NEW, admitted) → main table → host0 → host.
- Host reply → rouvpn0 → host0 (ESTABLISHED) → RPDB dispatch по destination=remote-source → Profile table → metric выбирает oc-main (если его metric ниже) → out через oc-main.
- ✗ Reply уходит через другой tunnel.

Про flowing через один bound interface: работает.
Про flowing через несколько bound interfaces: **сломан** для inbound/bidirectional.

**Оценка:** **HIGH, must-fix.** Ревьюер правильно формулирует: `"No conntrack marks required" holds only for outbound.`

**Оценка предложения:**
- Capacity-1 constraint — корректное решение для first slice. Единственный egress → выбор тривиален → destination dispatch совпадает с return steering.
- Flow pinning (connmark + fwmark RPDB) — правильная общая модель, но требует kernel experiment (connmark restore in PREROUTING before routing, RPDB fwmark rules, rp_filter interplay, mark retirement → blackhole). Ревьюер корректно откладывает через «dedicated kernel experiment».

**Интеграция в Draft 5:** фрагмент §5.4-A готов к вставке. Правильно сформулирован.

**Одно замечание к тексту:** в §5.4-A reviewer пишет *«direction = inbound and direction = bidirectional are accepted only for a Profile whose interface capacity is exactly 1»*, а в §5.5+§8 пишет *«Until the Device traffic-envelope grammar exists, inbound and bidirectional are reserved: the first parser recognizes the values and rejects them as not yet supported»*. Это **два независимых механизма**:
- Parser rejects inbound/bidirectional entirely (defensive, first slice);
- IF parser later admits inbound/bidirectional, THEN capacity-1 rule applies.

Reviewer сам это отмечает в Note, но при интеграции стоит явно разнести: первая итерация = parser reject; capacity-1 = backup rule, активируется когда парсер начнёт их принимать.

---

## 2. ESTABLISHED,RELATED не привязан к интерфейсам — реальное противоречие

**Проверка.** §5.4: *"ESTABLISHED,RELATED acceptance for admitted flows"*. Формулировка *«for admitted flows»* намекает на scoping, но не специфицирует.

§5.5: *«over-quota or otherwise unbound interface ... receives no generated payload ACCEPT state»*.

Инвариант 22: то же.

Инвариант 32: *«canonical stateful ordering rejects INVALID, accepts ESTABLISHED/RELATED admitted-flow traffic»* — без упоминания интерфейса.

**Возможный имплементационный исход:**
- `-m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT` (без `-i`) → unbound interface получает ACCEPT для matching tuple.
- Или `-i <bound-interface> -o host0 --ctstate ESTABLISHED,RELATED -j ACCEPT` → unbound не получает.

Draft 4 не фиксирует. Если реализатор выберет первое → §5.5 нарушается в практике.

**Оценка:** **HIGH, must-fix** (clarification, не fundamental bug).

**Оценка предложения §5.4-B:**
- Explicit `(I, host0)` pairs — правильная формулировка. Устраняет ambiguity.
- Residual: *«a packet that matches the tuple of a flow admitted through bound interface A but arrives on another bound interface B is accepted»* — это корректно задокументировано. Это и есть причина, по которой нужен flow pinning для полного fix (только для inbound/bidirectional; для outbound такого case не бывает, потому что reply от remote всегда приходит на тот же interface, где исходящий flow, — kernel FIB не переставляет source interface для ответа).

Actually wait — для outbound, reply от remote приходит на same interface где outbound ушёл (это tunnel внутренний). Значит A=B всегда. Residual case возникает только для inbound/bidirectional где remote выбрал interface. Правильно.

**Проверка proposed §5.4-B + §5.4-A consistency:** для outbound residual case невозможен → interface-pair rule достаточно. Для inbound/bidirectional residual case возможен → нужен flow pinning → отложен. Согласовано.

---

## 3. INPUT policy + inbound/bidirectional scope — реальный gap

**Проверка.** §8: *«ROU local INPUT policy must explicitly admit the configured internal publication endpoints needed by the relay/listener path. Publication never implies a blanket INPUT allow.»*

Это говорит «разрешить relay endpoints» но не говорит «всё остальное DROP». Если дефолт ACCEPT (что обычно для INPUT), то удалённая сторона может достигать любые ROU-local services. Не «must accept only» — «must explicitly admit», что двусмысленно.

§5.4 для INBOUND: NEW разрешён от remote к host. Destination не ограничен. Profile не содержит host-prefixes. Значит remote может достичь любой host address.

Для OUTBOUND такого нет — host уже выбрал использовать rouvpn0 (host routing/BOU). Для INBOUND — remote выбрал, и Profile не ограничивает destination.

**Оценка:** **HIGH, must-fix.** Это trust boundary.

**Оценка предложения §5.5+§8:**
- INPUT default DROP — правильно, закрывает ROU-local services.
- Только loopback + local-originated ESTABLISHED + host0→publication endpoints.
- Device→ROU-local DROP (включая сам listener).
- Reject inbound/bidirectional в first parser — безопасно и consistent с «не изобретать envelope syntax».

**Одно техническое замечание:** Device→ROU-local DROP для publication endpoints **не блокирует** правильно работающий relay. Relay на host side → traffic идёт host0→ROU-local listener, что разрешено. Direct remote→ROU-local publication не работает (ROU-local address 192.0.2.2 не routable извне). DROP для Device→ROU-local это defense-in-depth, не functional requirement. Ревьюер это подразумевает, но стоит явно указать.

---

## 4. Shadow fallback + barrier — ревьюер поймал моё переусердствование

Это самое интересное. Ревьюер прав по двум независимым причинам.

**Часть (a): shadow fallback не используется.**

Нет availability detector → все bound interfaces UNKNOWN → UNAVAILABLE никогда не возникает → fallback (persistent at 65535) никогда не выбирается. Маршрут есть, но не активен.

Формально: `route_intent.py` уже материализует. Полезность: 0 при отсутствии detector'а.

Формально можно отложить до detector'а — уменьшает first slice.

**Часть (b): barrier переусердствован — ЭТО Я САМ ВИНОВАТ.**

В прошлом ревью я написал C1 fix: *"multipath rebuild requires full Profile-route reprojection under the protective barrier."* И предложил инвариант 62.

Ревьюер правильно указывает: это overkill.

Детальный разбор, когда barrier действительно нужен:

**Case 1: binding member disappearance (например, ocserv client отключился).**
- Kernel сам удаляет route через этот interface.
- Multipath fallback с этим member удаляется целиком (EXP-013 A3).
- Таблица: normal routes для survivors (unchanged) + NO fallback + blackhole.
- Traffic к fallback-destination → blackhole → fail-closed. Safe.
- Apply: rebuild fallback with survivors.
- Kernel: add multipath route → применяется атомарно.
- Window: между «multipath gone» и «multipath rebuilt with survivors» — fallback отсутствует, но blackhole закрывает. **Fail-open window не возникает.**
- **Barrier НЕ нужен.**

**Case 2: binding member appearance (новый client).**
- Same logic: добавление в multipath, атомарно.
- **Barrier не нужен.**

**Case 3: availability change (AVAILABLE → UNAVAILABLE) с persistent shadow.**
- Fallback уже существует (never removed, только при binding removal).
- Normal route through this interface удаляется.
- Fallback теперь становится effective (normal gone, fallback at 65535).
- Traffic switches to fallback members (including this one, which is dead).
- EXP-013 B4 explicitly: ECMP hash, not sequential retry. Traffic may go to dead member and fail.
- **This is by design** — "last resort".
- **Barrier не нужен.** Persistent shadow eliminates fail-open window entirely.

**Case 4: structural drift (unexpected routes present, foreign routes).**
- Requires atomic repair under barrier.
- Barrier IS needed.

**Вывод:** Инвариант 62 (barrier на member disappearance) неправ. Barrier нужен только для structural drift. Persistent shadow fallback делает его ненужным для availability transitions И для binding transitions.

**Это моя ошибка в прошлом ревью.** Review caught it. Хорошо.

**Оценка предложения:**
- Refinement barrier scope: **must-fix.** Инвариант 62 нужно удалить или резко сузить.
- Deferral shadow fallback: **optional, но разумно.** Если deferral — упрощает first slice и не теряет safety. Если retain — тоже безопасно, но требует барьерной ревизии.

**Моя рекомендация:** retain shadow fallback (он уже работает, тесты есть, EXP-013 его провалидировал), но **отдельно** исправить барьерную модель: убрать инвариант 62, ограничить barrier только структурным дрейфом (unexpected foreign routes/firewall/NAT). Definition barrier перенести в production section (не только §20).

**Обоснование retain vs defer:** если defer shadow fallback, то при добавлении availability detector через месяц придётся менять routing model (normal-only → normal + persistent shadow). Это architectural change. Retention: detector добавляется как pure addition (availability state меняется, projection уже готова). Меньше disruption при следующей итерации.

Но ревьюер прав, что это trade-off, не must-fix. Оба подхода работают.

---

## Minor points — все валидны

**rou up order.** §3.1: step 5 = publications, step 8 = fail-closed. Между ними окно с активными publication но без firewall. Real concern. Fix: либо переставить, либо явно «публикации не пересылают до шага 12». Ревьюер прав.

**NAT.** §14: *«payload NAT where configured/required»*, но config schema не имеет NAT fields. Real gap. Первая реализация будет решать молча. Default policy (MASQUERADE на bound Device interfaces для outbound) стоит зафиксировать.

**MTU/MSS.** Не упомянуто нигде. veth 1500 vs tunnel < 1500 → MSS clamping обычно нужен. Without it, TCP black-hole. First live test с real TCP поймает. Good catch.

**ECMP hash policy.** `net.ipv4.fib_multipath_hash_policy` в namespace не перечислен в §4.2. Real sysctl gap.

**Language.** NG1 docs English, PROJECT-CONVENTIONS §6 всё ещё называет RC3 текущей. Real inconsistency. Fix: либо конвенции правятся под NG1 (English allowed), либо план перевода.

---

## Оценка текстовых фрагментов

**§5.4-A** — корректен, с одним уточнением интеграции (см. пункт 1 про «два независимых механизма»).

**§5.4-B** — корректен, residual case честно задокументирован.

**§5.5+§8** — корректен. Замечание про Device→ROU-local defense-in-depth стоит явно отметить как non-functional (relay не блокируется).

**Invariants 63–66** — корректны. Если принимается barrier refinement, стоит добавить 67: *"Protective barrier is scoped to structural owned-state drift only; normal binding lifecycle transitions do not require barrier."*

**Tests 1–5** — корректны, стоит добавить test 6: *"Structural drift triggers barrier; normal member disappearance does not."*

---

## Итог

**Ревьюер прав.** По всем существенным пунктам. Это не мнение — это проверка против кода, EXP-013 и Draft 4.

**Приоритизация для Draft 5:**

*Must-fix (без них нельзя писать kernel materialization):*
1. §5.4-A (inbound/bidirectional return path) — с уточнением двух механизмов.
2. §5.4-B (ESTABLISHED interface-scoping) — прямолинейно.
3. §5.5+§8 (INPUT default DROP + reject inbound/bidirectional в first parser).

*Must-fix (structural):*
4. Barrier scope refinement + удаление/сужение инварианта 62.

*Should-fix (production readiness):*
5. rou up step order.
6. NAT default policy.
7. MTU/MSS note.
8. ECMP hash policy sysctl.

*Opinion / deferred:*
9. Shadow fallback deferral (retention preferable, но обоснованно).

*Bookkeeping:*
10. Language/conventions alignment.

**Одно, где ревьюер мягче, чем мог бы быть:** инвариант 62 не «over-scoped», а «неверен по существу». With persistent shadow, ни availability transition, ни binding transition не требуют barrier. Barrier только для structural drift (unexpected foreign routes/firewall/NAT). Если сохранять shadow fallback, инвариант 62 нужно **удалить**, а не уточнить. Если defer shadow fallback — тогда при появлении availability detector'а понадобится барьерная модель; и вот там refine scope понадобится.

Так что пункт 4 у ревьюера — не refinement, а **два независимых решения**, которые стоит принять отдельно.

---

Стоит закрыть всё это одним циклом (Draft 5) — ревью достаточно качественное, чтобы интегрировать все фрагменты в одну итерацию. Если нужен мой ответ на конкретный fragment — скажите, разберу подробнее. Но судя по структуре, все wedge'и готовы к применению с небольшими уточнениями выше.
