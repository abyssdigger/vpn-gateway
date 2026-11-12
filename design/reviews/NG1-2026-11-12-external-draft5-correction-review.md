Прочитал `vpn-gateway-architecture-ng1.md` (разделы 3–5, 8, 11–15, 20–22 целиком, остальное просмотром), всю пачку документов из сообщения, включая EXP-013, ревью и ответы на них, и конвенции. Файлы `NG1-…-concept-architecture-review.md`, `vpn-gateway-experiments.md` и `CHANGELOG.md` не открывал.

Модель стала заметно проще и честнее прежней: namespace убирает почти всю борьбу за владение таблицами хоста, два уровня политики (генерируемая `direction` и административный `traffic_envelope`) разведены, явные `ACCEPT/DROP` по longest-prefix закрывают fail-open на перекрытиях, а EXP-013 даёт реальную опору для fallback. Остальное ниже: то, что я считаю реальными дырами или лишней сложностью.

## Серьёзные

**1. Обратный маршрут для `inbound`/`bidirectional` при нескольких интерфейсах.**
§5.4 говорит, что марки не нужны: ответ хоста на входящий поток идёт «в таблицу Profile». Но таблица Profile выбирает путь по метрике, а не по интерфейсу, с которого пришёл запрос. Если удалённая сторона инициировала поток через `wg-backup`, а предпочтительный маршрут идёт через `oc-main`, ответ уйдёт в другой туннель. В лучшем случае поток сломается, в худшем ответ окажется в туннеле другого доверенного домена. Для `outbound` марки действительно не нужны, поэтому ошибка легко проходит тесты. Нужно либо явное требование connmark по интерфейсу прихода и `ip rule fwmark` для возврата (с экспериментом, например EXP-014), либо запрет `inbound`/`bidirectional` для Profile с несколькими привязанными интерфейсами. Сейчас «implementation may use marks» не гарантирует корректность.

**2. `ESTABLISHED,RELATED` не привязан к интерфейсам.**
§5.4 и инвариант 32 принимают такой трафик «для admitted flows» без условия по интерфейсу, а §5.5 и инвариант 22 обещают, что у не привязанного или сверхквотного интерфейса нет никакого `ACCEPT`-состояния. Это противоречие: пакет с чужого интерфейса, совпавший с кортежем существующего потока, принимается. Кроме того, возможна подмена в поток другого Device. Решение дешёвое: принимать `ESTABLISHED,RELATED` только для `-i host0` и для привязанных интерфейсов, правила перегенерируются вместе с привязками.

**3. Для `inbound`/`bidirectional` нет ограничения со стороны хоста, а `INPUT` для пакетов с Device-интерфейсов не описан.**
Profile содержит только удалённые префиксы, поэтому разрешённый `NEW` из Device к хосту принимается для любого адреса за `host0`. Ограничить его может только административный envelope, грамматики которого ещё нет, или хост/BOU, который необязателен. Предлагаю до появления envelope в первом парсере отвергать `inbound` и `bidirectional` (по уже принятому правилу не выдумывать синтаксис) либо явно записать это как границу доверия. Отдельно: §8 только требует допускать конечные точки публикации, но не говорит, что `INPUT` в namespace по умолчанию `DROP` для всего с Device-интерфейсов. Иначе удалённая сторона достаёт слушателей самого ROU.

## Упрощение

**4. Теневой fallback и барьер сейчас ничего не покупают.**
До появления детектора доступности все привязанные пути `UNKNOWN`, то есть `UNAVAILABLE` не возникает никогда, и теневой ECMP-fallback не используется. При этом инвариант 62 запускает «полную перепроекцию под защитным барьером» при любом исчезновении члена. Сам барьер определён только в §20 (прототип v0) как глобальный `ip_forward=0` во всём namespace, а в производственных разделах не определён. То есть отключение одного клиента ocserv остановит пересылку для всех Profile. А ядро при исчезновении интерфейса само удаляет маршруты через него, и нормальные маршруты выживших остаются; пропадает только multipath-fallback.

Предлагаю в первой производственной итерации не материализовать теневой fallback вообще (он понадобится вместе с детектором), а при появлении барьер определить в производственном разделе и ограничить: нужен, когда активный уровень fallback, а не при каждом отключении, и по возможности на уровне Profile (подмена RPDB-правила на blackhole), а не глобальным `ip_forward=0`. Глобальный барьер оставить для структурного дрейфа.

## Меньшее

- **Порядок `rou up` (§3.1):** публикуемые сокеты на хосте создаются на шаге 5, а начальное fail-closed состояние ставится на шаге 8. Поменяй местами или явно скажи, что реле не пересылает до шага 12.
- **NAT:** §14 говорит «payload NAT where configured/required», но в конфигурации никаких полей NAT нет. Первой реализации придётся решать молча. Лучше записать политику по умолчанию (например, маскарад на привязанных Device-интерфейсах для `outbound`) до написания кода.
- **MTU/MSS:** про это нигде нет ни слова, а между veth 1500 и MTU туннеля клампинг MSS обычно необходим. Закладывай проверку в первый живой тест с реальным TCP.
- **ECMP:** распределение зависит от `net.ipv4.fib_multipath_hash_policy` в namespace; добавь в список sysctl §4.2.
- **Язык и конвенции:** NG1-документы английские, а `PROJECT-CONVENTIONS.md` требует русский, и его §6 всё ещё называет RC3 текущей нормативной архитектурой. Либо поправь конвенции под NG1 (с указанием, что язык NG1 английский), либо запланируй перевод и словарь терминов для NG1.

Три фрагмента ниже готовы к вставке в Draft 5. Они на английском, как и сам документ NG1; если решите перейти на русский, переведу. Нумерацию разделов и инвариантов подставьте свою. Фрагменты 1 и 3 оформлены так, чтобы первую итерацию можно было реализовать без марок.

## §5.4-A: возврат для `inbound` и `bidirectional`

> **Return steering for remote-initiated flows.**
> A reply to a Device-initiated flow enters ROU on `host0` and is dispatched by its destination to the Profile table. That table selects a path by metric, not by the interface on which the flow was admitted. When a Profile may have more than one bound interface at the same time, the reply could therefore leave through a different tunnel (a different Device, possibly a different trust domain) than the one that carried the request. "No conntrack marks required" holds only for `outbound`.
>
> **First production slice (no marks).** `direction = inbound` and `direction = bidirectional` are accepted only for a Profile whose *interface capacity* is exactly 1:
>
>     capacity(Profile) = sum(Device.interface_quota) over active Devices in device_order
>
> A Profile table then has at most one possible egress interface, so destination dispatch and return steering coincide. A Profile that violates this rule is a configuration error reported before mutation. Disabled Device references do not count; enabling one later is a configuration transition and is revalidated.
>
> **Later extension (flow pinning, requires an experiment).** For capacity > 1 every flow is pinned to the interface that admitted it: the interface carries a stable mark `M(I)`; the admitting `NEW` packet sets the connection mark; `host0`-ingress packets of established flows restore it before the routing decision; an RPDB rule `fwmark M(I) -> return table of I` precedes destination dispatch. Marks are allocated from a ROU-reserved mask, are never reused within one ROU instance lifetime, and a retired mark resolves to an explicit blackhole rather than falling through to destination dispatch. This extension is not part of the first slice and is gated by a dedicated kernel experiment.

## §5.4-B: `ESTABLISHED,RELATED` привязан к интерфейсам

> **Interface-scoped state acceptance.**
> `INVALID` is rejected first, independently of interfaces. `ESTABLISHED,RELATED` acceptance is generated **only** for these ordered interface pairs, for every currently *bound* interface `I`:
>
>     -i I     -o host0   ESTABLISHED,RELATED -> ACCEPT
>     -i host0 -o I       ESTABLISHED,RELATED -> ACCEPT
>
> No state-based ACCEPT exists for any other pair: not for Device-to-Device transit, not for an over-quota or unbound interface, and not for an interface that merely matches an `expected_interfaces` selector. A packet that matches an existing conntrack entry but arrives on an interface without a generated pair is dropped by the default `DROP`.
>
> The pair rules belong to the verified binding of `I` and are removed with it; they are never created from selector matches alone.
>
> *Residual (documented, not closed by this rule):* a packet that matches the tuple of a flow admitted through bound interface `A` but arrives on another bound interface `B` is accepted. Closing it requires the flow-pinning extension of §5.4-A, which also scopes the accepted state to the original interface.

## §5.5 и §8: политика `INPUT` и первые значения `direction`

> **ROU-owned INPUT policy is default `DROP`.** It accepts only:
> - loopback;
> - `ESTABLISHED,RELATED` for locally originated traffic;
> - from `host0`: the configured internal publication endpoints (protocol, port, ROU-local address) and nothing else.
>
> Traffic arriving from a Device interface (bound, over-quota or unbound) toward a ROU-local address is dropped. This includes the Device's own transport listener and any relay endpoint. Publication never implies an INPUT allow from Device interfaces. Administrator-authored admission of specific local services is part of the future Device envelope.
>
> **Host-side reach of remote-initiated flows.** A Profile defines only remote prefixes. When Device→host `NEW` is allowed, the generated policy constrains the *source* (remote prefix), not the *destination*: the remote side can reach any address reachable via `host0` that the host or BOU does not block. Until the Device traffic-envelope grammar exists, `inbound` and `bidirectional` are reserved: the first parser recognizes the values and rejects them as not yet supported. `outbound` is unaffected.

Примечание: пара §5.4-A и последний абзац согласованы. Правило ёмкости 1 нужно, когда `inbound`/`bidirectional` появятся, а пока они зарезервированы. Если захотите оставить `inbound` для лабораторных тестов, достаточно одного правила ёмкости без марок и зарезервированной грамматики envelope.

## Новые инварианты (продолжение нумерации)

> 63. Remote-initiated (`inbound`/`bidirectional`) Profiles are admitted only when their interface capacity is 1, or when flow pinning is implemented and proven.
> 64. State-based `ESTABLISHED,RELATED` ACCEPT exists only for `(bound interface, host0)` pairs in both directions; selector matches never create it.
> 65. ROU-owned INPUT is default `DROP`; Device interfaces have no implicit access to ROU-local addresses.
> 66. Until the Device traffic envelope exists, `inbound` and `bidirectional` are rejected by the configuration parser.

## Тесты, которые стоит добавить в проектор правил (rootless)

1. Профиль с `inbound` и ёмкостью 2: ошибка конфигурации до мутации; тот же профиль с ёмкостью 1: принят (когда значение будет разрешено).
2. Сверхквотный интерфейс: не создаёт ни `ESTABLISHED`-пар, ни маршрутов, ни `INPUT`-разрешений.
3. Пара `(I, host0)` исчезает вместе с привязкой `I`; новая привязка с тем же именем и другим `ifindex` не наследует правил.
4. Нет ни одной пары вида `(I, J)` для двух Device-интерфейсов.
5. `INPUT`: пакет с Device-интерфейса на адрес ROU (включая слушатель собственного транспорта) отбрасывается; пакет с `host0` на конечную точку публикации принимается, на любой другой порт отбрасывается.

## Для эксперимента перед расширением с маркировкой потоков

Когда дойдёте до ёмкости больше 1, проверить на целевом ядре: восстановление connmark в `mangle PREROUTING` до решения маршрутизации и срабатывание `fwmark`-правила RPDB; поведение при отключённом `rp_filter`; судьбу потока с меткой исчезнувшего интерфейса (ожидается blackhole, а не провал в диспетчеризацию по адресу); необходимость и способ сброса conntrack при отвязке.
