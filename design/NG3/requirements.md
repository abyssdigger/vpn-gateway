# VPN-GATE NG3 — Requirements

**Status:** NG3 design-cycle draft  
**Cycle:** `ng3-design-cycle-20261116-config-intent-model-40m`  
**Normative model:** `design/requirements-model.md`  
**Architecture status:** no NG2 architecture is inherited automatically

This document is the normative requirement tree for NG3.

The seven primary project requirements are accepted. Their derived Requirement/Constraint
trees remain subject to normal requirement/constraint review.

Canonical compact form:

```text
**[PRODUCT0001]** Basis | Statement [pending_closure|closed|rejected_closure]       — primary R
**[PRODUCT0001-R...]** Purpose | Statement [pending_closure|closed|rejected_closure] — derived R
**[PRODUCT0001-...C...]** Reason | Statement [pending_closure|closed|rejected_closure] — C
```

For a primary project requirement the italicized part is **Основание**: a verifiable external
source answering «откуда это требование взято?». For a derived requirement it answers
**зачем**; for a constraint it answers **почему**. The part after `|` is the normative
statement.

The optional closure label records acceptance state only:
`[pending_closure]` means an architecture candidate exists but is not yet accepted;
`[closed]` means it has been accepted as sufficient for the current scope;
`[rejected_closure]` means the candidate failed acceptance. Requirements do not list the
architectural decisions themselves; those are found by searching architecture documents for
the requirement/constraint ID.

Section headings below are only human-readable grouping. They are not requirements and do
not participate in the requirement tree.

No NG2 component, state machine, event, Linux mechanism or configuration object becomes an
NG3 requirement merely because it existed before.

## VPN routing and VPN-channel service

**[VPNG0001]** *Основание: интервью заказчика с аналитиком, 2026-11-15; требование зафиксировано в initial NG3 requirement tree commit `4b3785b5c228782768afe317d4f09386fd46b440` от 2026-11-15 21:14:07 +03:00; тема: управляемый VPN-маршрутизатор.* | VPN-GATE должен позволять пользователю использовать продукт как управляемый сетевой узел для передачи выбранного IP-трафика через VPN без ручной сборки требуемого поведения из низкоуровневых сетевых команд. [closed]

**[VPNG0001-R1]** *Чтобы пользователь мог использовать VPN-GATE как управляемый сетевой узел для передачи выбранного IP-трафика через VPN, не собирая поведение продукта вручную из низкоуровневых сетевых команд.* | VPN-GATE должен предоставлять управляемую маршрутизацию выбранного IP-трафика между обычной сетью и настроенными VPN-путями. [closed]

 **[VPNG0001-R1.R1]** *Чтобы трафик, принятый продуктом в обслуживание, действительно мог проходить через предназначенный для него VPN-путь в требуемом направлении.* | Для принятого в обслуживание IP-трафика VPN-GATE должен обеспечивать необходимое forwarding поведение между обычной сетью и разрешенными VPN-путями. [closed]

 **[VPNG0001-R1.R2]** *Чтобы эксплуатация продукта не зависела от ручного воспроизведения его внутренней сетевой механики оператором.* | Пользователь должен задавать требуемое поведение через продуктовую конфигурацию и управляющие операции VPN-GATE; внутренние сетевые действия должны выполняться продуктом. [closed]
 ↳ [decomp: VPNG0005-R5 -> VPNG0005-R5.R6]

  **[VPNG0001-R1.R2.R1]** *Чтобы пользователь описывал намерение продукта, а не последовательность Linux/networking действий.* | Продуктовая конфигурация должна выражать логические сущности и связи, необходимые принятым требованиям, без обязанности пользователя задавать внутренние route/rule/firewall/process операции VPN-GATE. [closed]

  **[VPNG0001-R1.R2.R2]** *Чтобы администратор мог описать заранее подготовленные VPN resources без ручного именования каждого случайно появившегося runtime endpoint.* | Декларативный контракт конфигурации должен позволять задать Device identity и binding expectations, достаточные для детерминированного получения логических VPN-путей и их concrete data-plane endpoint bindings внутри управляемого сетевого домена. [closed]

  **[VPNG0001-R1.R2.R3]** *Чтобы ошибочная декларативная конфигурация не превращалась в частично примененное или случайное сетевое состояние.* | VPN-GATE должен до применения зависящих сетевых изменений отклонять конфигурацию, из которой нельзя однозначно получить требуемые логические сущности, связи и обязательные binding/policy намерения; VPN-GATE должен оставлять причину отказа наблюдаемой. [closed]

  **[VPNG0001-R1.R2.R5]** *Чтобы human-facing config был однозначным административным контрактом, а не эвристическим языком, который разные версии могут «понимать» по-разному.* | Для каждого поддерживаемого user-facing поля VPN-GATE должен принимать один определенный canonical semantic form, отвергать неоднозначные/некорректные значения вместо молчаливого исправления и не требовать от пользователя повторного задания значений, которые однозначно выводятся из конфигурации или runtime observations. [closed]

   **[VPNG0001-R1.R2.R5.R1]** *Чтобы конфигурационные идентификаторы, поля и enum-значения оставались читаемыми и однозначными для человека и tooling.* | Human-facing schema должен использовать стабильные opaque object IDs, semantic snake_case field names, настоящие TOML booleans и одну canonical lowercase textual representation для каждого enum-like значения; VPN-GATE не должен неявно принимать aliases вроде нескольких spelling одного и того же semantic value. [closed]

   **[VPNG0001-R1.R2.R5.R2]** *Чтобы ошибочный network policy input не менял смысл через скрытую canonicalization.* | VPN-GATE должен выполнять strict semantic validation IPv4/CIDR и других policy values: в частности, он должен отклонять destination CIDR с host bits вместо silent canonicalization, бессмысленные duplicate declarations и недопустимые/неоднозначные ranges/references. [closed]

   **[VPNG0001-R1.R2.R5.R3]** *Чтобы пользовательский config описывал намерение, а не внутренние вычисляемые параметры Linux-реализации.* | Derived/redundant quantities и implementation identifiers (например aggregate Device quota, runtime ifindex, route metric/table/rule priority) не должны становиться обязательными user-facing полями, если их значение однозначно выводится продуктом и они не являются самостоятельным user policy knob. [closed]

   **[VPNG0001-R1.R2.R5.R4]** *Чтобы порядок элементов не превращался в скрытую policy там, где пользователь его не задавал.* | Collection order должен влиять на semantics только для полей, явно определенных как ordered policy (например `device_order` и `expected_interfaces`); для set-like declarations вроде `destinations` порядок записи не должен менять результат. [closed]

  **[VPNG0001-R1.R2.R4]** *Чтобы пользователь мог описывать ожидаемое сетевое поведение устойчивыми предметными сущностями, а не смешивать сетевую потребность с текущими runtime-интерфейсами.* | Пользовательская конфигурация должна предоставлять именованные сущности `Device` и `Profile`: Device описывает ожидаемый внешний VPN/network resource и его binding expectations, а Profile описывает пользовательскую сетевую потребность и связывает ее с разрешенными Devices. [closed]

   **[VPNG0001-R1.R2.R4.R1]** *Чтобы пользователь мог стабильно ссылаться на одну и ту же логическую сущность из других частей конфигурации, status и diagnostics.* | Каждый Device и Profile должен иметь стабильный уникальный user-visible ID; ссылки между сущностями должны использовать этот ID, а runtime interface name, metric или случайный object identity не должны подменять пользовательскую идентичность. [closed]

    **[VPNG0001-R1.R2.R4.R1.C1]** *В текущем human-facing contract не определена отдельная quoting/escaping semantics для Device/Profile IDs, поэтому идентификаторы должны оставаться однозначными в простой canonical textual form.* | В текущем human-facing contract Device/Profile ID ограничен формой `[a-z0-9][a-z0-9-]*`; dots, underscores, whitespace и uppercase не поддерживаются, leading digit допустим, а ID должен трактоваться как opaque string, не как число или системный identifier. [closed]

   **[VPNG0001-R1.R2.R4.R2]** *Чтобы пользователь мог заранее описать будущую или временно неиспользуемую часть конфигурации без ее фактической активации.* | Device и Profile должны иметь явное `enabled` состояние без неявного default; disabled объект может существовать как именованный placeholder и не должен сам по себе создавать active routing/binding behavior. [closed]

    **[VPNG0001-R1.R2.R4.R2.R1]** *Чтобы placeholder не требовал преждевременно заполнять еще не определенную будущую конфигурацию.* | Для `enabled = false` остальные поля Device/Profile могут отсутствовать и не должны проходить глубокую semantic validation, кроме корректности самой внешней структуры и идентичности объекта. [closed]

   **[VPNG0001-R1.R2.R4.R3]** *Чтобы один и тот же внешний VPN/network resource можно было переиспользовать в нескольких независимых пользовательских сетевых потребностях.* | Device должен быть отдельной от Profile сущностью; один Device может быть referenced несколькими Profiles, а Device-specific binding expectations не должны дублироваться внутри каждого Profile. [closed]

   **[VPNG0001-R1.R2.R4.R4]** *Чтобы Profile оставался описанием пользовательского намерения, а не снимком текущей Linux-реализации.* | Enabled Profile должен явно задавать direction, непустой набор remote destinations и непустой ordered список Device IDs; Profile не должен требовать от пользователя задания runtime interface names, Linux metrics или внутренних route/rule/firewall объектов. [closed]

    **[VPNG0001-R1.R2.R4.R4.R2]** *Чтобы исчезновение, замена или временное отсутствие transport paths не уничтожали саму пользовательскую сетевую потребность.* | Profile должен существовать как независимый logical routing/payload-policy domain независимо от текущего числа пригодных concrete paths; binding/path availability изменяют возможность и порядок materialization, но не идентичность, destinations или direction самого Profile. [closed]

    **[VPNG0001-R1.R2.R4.R4.R3]** *Чтобы пользовательская модель Profile не смешивалась с VPN transport implementation.* | Profile не должен идентифицироваться с VPN interface, peer, tunnel/session, route metric, probe target или набором Linux rules; эти объекты могут обслуживать Profile через отдельные binding/normalization/materialization boundaries. [closed]


    **[VPNG0001-R1.R2.R4.R4.R4]** *Чтобы разрешённый VPN→ordinary traffic мог достигать хостов обычной сети, которым не раздавались маршруты обратно к remote VPN prefixes, без обязательной перенастройки каждого такого хоста.* | VPN-GATE должен позволять пользователю для Profile явно запросить ordinary-side gateway source NAT для уже разрешённого VPN→ordinary payload, который после выхода из managed network domain пересылается хостом дальше в ordinary network; если такой режим для Profile не запрошен, VPN-GATE не должен добавлять эту трансляцию, а traffic, терминирующийся на самом host, не должен требовать ordinary-side gateway NAT. [closed]

     **[VPNG0001-R1.R2.R4.R4.R4.R1]** *Чтобы два разных назначения NAT не смешивались и не меняли наблюдаемые адреса раньше требуемой policy-проверки.* | VPN-GATE должен отличать Profile ordinary-side gateway NAT от Device VPN-side source NAT: Device `masquerade` применяется к ordinary→VPN payload внутри managed domain после Device/Profile firewall, а Profile ordinary-side gateway NAT — только к VPN→ordinary traffic после managed firewall на явно принадлежащей VPN-GATE host-boundary области. [closed]

     **[VPNG0001-R1.R2.R4.R4.R4.C1]** *Поскольку ordinary-side gateway NAT имеет смысл только на VPN→ordinary leg, отдельный независимый toggle создавал бы бессмысленные сочетания с outbound-only Profile и усложнял бы чтение policy.* | В Release 1 opt-in ordinary-side gateway NAT должен кодироваться только суффиксом `+snat` значения `direction`: допустимы `inbound+snat` и `bidirectional+snat`; базовые `inbound`/`bidirectional` означают отсутствие этой трансляции, `outbound+snat` недопустим, отдельного user-facing gateway-NAT поля нет. [closed]

    **[VPNG0001-R1.R2.R4.R4.R1]** *Чтобы availability определяла пригодность пути именно для конкретной пользовательской потребности.* | Availability-check configuration должна быть Profile-scoped: для каждого availability-enabled Profile проверка применяется к его использованию конкретных разрешенных путей, поэтому один и тот же Device/interface может иметь разные availability outcomes в разных Profiles. [closed]

   **[VPNG0001-R1.R2.R4.R5]** *Чтобы ссылки на конфигурационные сущности были предсказуемыми и не создавали скрытых объектов.* | Enabled Profile может ссылаться только на объявленные Device IDs; VPN-GATE должен отклонять конфигурацию с unknown Device reference, а ссылку на известный disabled Device должен трактовать как допустимую и означающую, что такой Device временно не участвует operationally без изменения самого Profile intent. [closed]

   **[VPNG0001-R1.R2.R4.R6]** *Чтобы transport-specific свойства не приходилось дублировать в каждом Profile и чтобы они не смешивались с Profile routing need.* | Device должен быть местом пользовательского описания transport/path policy, общей для его concrete paths и независимой от Profile payload need; такие свойства могут включать NAT intent, ordered Device firewall policy и transport publication intent, если соответствующая capability поддерживается продуктом. [closed]

    **[VPNG0001-R1.R2.R4.R6.R1]** *Чтобы source-NAT behavior не возникал из скрытого default и был понятен администратору как свойство transport path.* | Для enabled Device, который в текущей enabled-конфигурации может обслуживать ordinary→VPN leg (`outbound` или `bidirectional` Profile), Release-1 user-facing policy должна явно задавать boolean `use_outbound_nat`: `true` нормализуется в masquerade через текущий concrete path, `false` — в отсутствие payload source NAT. Для Device без ordinary→VPN роли это поле не требуется. [closed]

    **[VPNG0001-R1.R2.R4.R6.R2]** *Чтобы transport-level ограничения могли дополнительно защищать tunnel traffic, не превращаясь в обход Profile policy.* | VPN-GATE должен для каждого Device поддерживать дополнительную ordered firewall policy для payload traffic, проходящего через его concrete paths; effective permission должен оставаться пересечением Profile permission и Device firewall verdict, поэтому Device `ALLOW` не должен создавать destinations, direction или path eligibility, отсутствующие в Profile policy. [closed]

     **[VPNG0001-R1.R2.R4.R6.R2.R1]** *Чтобы пользователь мог описывать ограничения Device в привычной последовательной firewall-модели и понимать влияние порядка правил без скрытой оптимизации со стороны VPN-GATE.* | VPN-GATE должен сохранять заданный пользователем порядок `firewall = [...]`; Release-1 rule string имеет форму `<in|out> <allow|deny|reject> [tcp|udp|icmp] [from <IPv4-CIDR>[:port-bundle]] [to <IPv4-CIDR>[:port-bundle]]` с опциональным trailing comment, а первый применимый terminal verdict определяет результат Device firewall. `port-bundle` допустим только с TCP/UDP и состоит без пробелов из одного или нескольких comma-separated элементов `N` или `A-B`, где каждый порт в `1..65535`, `A <= B`, а один физический порт не может повторяться или входить в пересекающиеся элементы bundle; VPN-GATE должен сохранять declared item order и не должен переставлять правила или исправлять широкое раннее правило ради более позднего. [closed]

     **[VPNG0001-R1.R2.R4.R6.R2.R2]** *Чтобы пользовательские `IN/OUT` не требовали знания Linux FORWARD semantics и при этом однозначно соответствовали фактическому направлению пакета относительно VPN Device.* | VPN-GATE должен трактовать в Device firewall `OUT` как payload packet, входящий через ordinary/host boundary и уходящий через current concrete path этого Device, а `IN` — как packet, входящий через current concrete path Device и уходящий через ordinary/host boundary; source/destination addresses и ports должны означать буквальные L3/L4 поля payload packet в точке этой фильтрации, а не адреса внешнего VPN transport или значения после последующего VPN-GATE source NAT. [closed]

     **[VPNG0001-R1.R2.R4.R6.R2.R3]** *Чтобы отсутствие Device firewall configuration сохраняло прежний смысл «Device не вводит дополнительного ограничения», а явное ограничение не получало скрытого разрешающего fallthrough.* | Если пользователь не задаёт Device firewall rules, VPN-GATE должен нормализовать Device firewall к эквивалентной permissive policy, разрешающей любой поддерживаемый payload в обоих направлениях `IN` и `OUT`; если пользователь задал хотя бы одно явное правило, VPN-GATE должен сохранить только явную ordered policy, а отсутствие совпавшего terminal verdict должно завершаться `DROP`. [closed]

     **[VPNG0001-R1.R2.R4.R6.R2.R4]** *Чтобы Device firewall оставался защитой управляемого VPN-трафика, а не превращал VPN-GATE в универсальный host firewall.* | VPN-GATE должен применять пользовательскую Device firewall policy только к payload traffic, который проходит между explicit ordinary/host boundary и current concrete VPN paths этого Device внутри managed network domain; эта policy не должна захватывать произвольный host-local или host-to-host traffic вне VPN-GATE managed payload path. [closed]

     **[VPNG0001-R1.R2.R4.R6.R2.R5]** *Чтобы при нескольких VPN endpoints одного Device пользователь мог ограничить риск конкретного удалённого конца, не привязывая долгоживущую policy к случайному runtime имени интерфейса.* | VPN-GATE должен позволять пользователю ограничить Device firewall rule одним логически идентифицируемым transport endpoint этого Device, когда для current path существует подтверждённый endpoint provenance, и разрешать такой selector через logical endpoint/path binding, а не через заданный пользователем runtime ifname. [closed]

      **[VPNG0001-R1.R2.R4.R6.R2.R5.C1]** *Потому что first-release transport-endpoint provenance отложен ограничением `VPNG0001-R1.R3.R5.C1`, а окончательная human-facing named-endpoint grammar ещё не принята.* | Первый release не обязан поддерживать endpoint-scoped Device firewall rules; их materialization остаётся отложенной до принятия endpoint provenance для соответствующей integration и отдельного configuration-format review. Обычные Device firewall rules без endpoint selector не должны зависеть от этой будущей capability. [closed]

    **[VPNG0001-R1.R2.R4.R6.R3]** *Чтобы server-side VPN transports могли быть доступны извне без смешивания host-facing listener details с Profile routing policy.* | Transport publication, если требуется Device, принадлежит Device/transport boundary и в Release 1 задаётся `publish_vpn_server = "tcp|udp[/<host-IPv4|host-interface>]:<host-port-bundle>[><internal-port-bundle>]"` либо массивом таких строк. Port bundle использует ту же strict compact grammar `N[,N|A-B...]` без пробелов, duplicate/overlap ports запрещены. Отсутствие `>...` означает identity mapping каждого host port на тот же internal port; при явном internal bundle обе стороны разворачиваются в declared order в последовательности отдельных портов, должны иметь одинаковую cardinality и мапятся позиционно 1:1. Отсутствие host selector означает публикацию на допустимых host addresses. Потеря требуемой publication не должна оставаться незаметной. [closed]

    **[VPNG0001-R1.R2.R4.R6.C1]** *Поскольку несколько исторических prototype spellings описывают те же transport-policy semantics, Release 1 нужен один канонический внешний язык без скрытых compatibility aliases.* | Каноническая Release-1 Device grammar использует `use_outbound_nat` для VPN-side source NAT, `allow_vpn_client` для точных client-side transport/control flows, `publish_vpn_server` для host-side server publication и ordered однострочный `firewall`; parser должен отклонять исторические `nat`, `traffic_envelope`, `publications`, top-level `[integration.*]` и иные неподтвержденные aliases. Endpoint-scoped Device firewall syntax остаётся отдельно ограничена `VPNG0001-R1.R2.R4.R6.R2.R5.C1`. [closed]

 **[VPNG0001-R1.R3]** *Чтобы VPN-GATE мог использовать подготовленные VPN-соединения как реальные пути передачи управляемого трафика.* | VPN-GATE должен уметь принимать в обслуживание поддерживаемые VPN-каналы, однозначно идентифицировать их и использовать как VPN-пути в соответствии с текущей политикой. [closed]

  **[VPNG0001-R1.R3.R1]** *Чтобы normalized policy, availability и status могли различать VPN-пути независимо от случайной идентичности текущего runtime-объекта.* | Каждый VPN-путь, полученный из Device binding semantics и используемый продуктом, должен иметь однозначную логическую идентичность, стабильную для соответствующего Device/selector/slot binding lifecycle и отличимую от конкретного текущего data-plane endpoint. [closed]

  **[VPNG0001-R1.R3.R2]** *Чтобы конкретный внешний VPN endpoint мог безопасно использоваться как именно тот путь, который указан в политике.* | До использования VPN-пути VPN-GATE должен иметь однозначный текущий binding между логической идентичностью пути и конкретным data-plane endpoint; отсутствие, неоднозначность или несоответствие binding не должны приводить к использованию endpoint как этого VPN-пути. [closed]

  **[VPNG0001-R1.R3.R3]** *Чтобы замена или пересоздание внешнего VPN endpoint не оставляли старый runtime-объект неявно действующим представителем логического пути.* | При изменении текущего binding новый concrete endpoint может представлять тот же логический VPN-путь только после подтверждения нового binding; superseded endpoint после этого не должен считаться текущим endpoint этого пути. [closed]

  **[VPNG0001-R1.R3.R4]** *Чтобы пользователь мог описать ожидаемые runtime endpoints внешнего Device до их фактического появления и не зависеть от ручного назначения каждого обнаруженного интерфейса.* | Enabled Device должен задавать непустой ordered набор `expected_interfaces`, по которому VPN-GATE однозначно распознает допустимые runtime interface endpoints этого Device и допускает их к binding только в пределах заданных selector semantics. [closed]

   **[VPNG0001-R1.R3.R4.R1]** *Чтобы точный интерфейс и семейство динамически создаваемых интерфейсов можно было описать одной предсказуемой моделью.* | Expected-interface selector должен поддерживать exact interface identity с quota 1 и prefix-family selector с явной положительной quota; prefix selector без quota не должен молча получать неявную емкость. [closed]

   **[VPNG0001-R1.R3.R4.R2]** *Чтобы один runtime interface не мог одновременно и неоднозначно представлять несколько активных Devices.* | Expected-interface selectors должны быть не пересекающимися внутри одного Device и между Devices, одновременно активными в текущем configuration intent; VPN-GATE должен отклонять неоднозначный binding до использования endpoint. [closed]

   **[VPNG0001-R1.R3.R4.R3]** *Чтобы временное отсутствие или появление дополнительных runtime interfaces не меняло пользовательский смысл Device.* | Runtime binding должен отличать user-declared expected-interface capacity от фактически обнаруженных endpoints; отсутствие ожидаемого endpoint не создает другой Device, а endpoint сверх selector quota не должен неявно становиться управляемым путем. [closed]

    **[VPNG0001-R1.R3.R4.R3.R1]** *Чтобы replacement или появление соседнего endpoint не меняли идентичность уже известного пути и не ломали Profile preference/status.* | Каждый admitted selector slot должен соответствовать стабильной logical path identity, производной от Device identity, selector position и stable slot; concrete endpoint является текущим binding этой logical identity и может заменяться без изменения самой identity после подтверждения нового binding. [closed]

   **[VPNG0001-R1.R3.R4.R4]** *Чтобы объявление Device само по себе не запускало управление сетевым ресурсом, который пользователь пока ни для чего не использует.* | Device считается active для discovery/binding только если он enabled и referenced хотя бы одним enabled Profile; disabled или не referenced Device не должен создавать active binding/path behavior. [closed]

  **[VPNG0001-R1.R3.R5]** *Чтобы упростить описание пользователем типовых проверок доступности, правил фильтрации по конечной точке VPN и других функций, которым полезна логическая привязка к конечной точке VPN вместо явного указания её IP-адреса.* | VPN-GATE должен при обнаружении или обновлении current logical VPN path уметь однозначно определить transport endpoint/peer, соответствующий текущему concrete data-plane endpoint, когда принятый discovery contract поддерживаемой integration предоставляет для этого достаточные наблюдаемые данные, и связать определённый endpoint/peer с текущей generation этого path binding. [closed]

   **[VPNG0001-R1.R3.R5.C1]** *Потому что надёжное получение transport-endpoint provenance ещё не подтверждено для всех поддерживаемых first-release integrations, а базовые routing, binding и явно адресованные проверки доступности не требуют этой удобной логической привязки.* | Первый release не обязан предоставлять transport-endpoint provenance для каждого VPN path. Отсутствие подтверждённого provenance не должно делать сам path непригодным для функций, которым он не нужен, но функции, чья принятая семантика требует endpoint provenance, не должны угадывать endpoint, подменять его interface name/slot или считать такую зависимую функцию действующей без подтверждённого provenance. [closed]

    **[VPNG0001-R1.R3.R5.C1.R1]** *Чтобы отложенная endpoint-provenance capability не превращалась для пользователя в скрыто неработающую или ложно работающую настройку.* | Когда пользователь запрашивает функцию, которая по принятой семантике требует transport-endpoint provenance, а текущая integration не может его однозначно предоставить, VPN-GATE должен до объявления этой функции действующей выдать явный диагностируемый отказ; если та же функция поддерживает явное указание IP-адреса вместо endpoint provenance, этот явный вариант должен оставаться доступным независимо от endpoint discovery. [closed]

  **[VPNG0001-R1.R3.C1]** *Первый релиз сознательно ограничен использованием VPN-каналов, заранее развернутых и базово настроенных администратором во внешней эксплуатационной среде; автоматическое provisioning VPN-инфраструктуры не входит в принятый first-release scope.* | VPN-GATE первого релиза не обязан самостоятельно создавать и конфигурировать VPN-каналы; администратор должен заранее развернуть и настроить поддерживаемый VPN-канал так, чтобы VPN-GATE мог принять его в обслуживание. [closed]

   **[VPNG0001-R1.R3.C1.R1]** *Чтобы администратор мог выполнить возложенную на него часть без знания внутренних деталей реализации VPN-GATE.* | Проект VPN-GATE должен предоставлять для каждого поддерживаемого способа внешнего развертывания VPN-канала инструкции и необходимый контракт, позволяющие администратору сделать канал однозначно видимым и пригодным для управления и использования VPN-GATE. [closed]
   ↳ [decomp: VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1]

    **[VPNG0001-R1.R3.C1.R1.R1]** *Чтобы заявленная поддержка внешнего VPN-канала не оставалась только формальной схемой без доказанной эксплуатационной применимости.* | Для каждого способа внешнего развертывания VPN-канала, объявленного поддерживаемым первым релизом, проект должен иметь воспроизводимое acceptance evidence, подтверждающее, что администратор, следуя опубликованной инструкции и не изменяя внутренний код VPN-GATE, может сделать data-plane endpoint доступным внутри managed network domain, после чего VPN-GATE однозначно обнаруживает и привязывает его к ожидаемому logical path и может использовать этот path в принятом forwarding contract. [closed]
   ↳ [decomp: VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2]
   ↳ [decomp: VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2]

  **[VPNG0001-R1.R3.C1.C1]** *Поскольку автоматический поиск, клонирование, изменение, enable/start/stop и принятие ownership произвольных vendor systemd units существенно расширяют first-release integration scope, тогда как штатный systemd уже позволяет администратору привязать отдельный VPN service к существующему managed network namespace и его lifecycle.* | Первый release не обязан автоматически создавать, клонировать, патчить, enable/disable или принимать под прямое управление VPN systemd units администратора; для поддерживаемой интеграции администратор подготавливает отдельный stack-specific unit/instance или wrapper и привязывает его к managed network domain по опубликованному контракту. [closed]

   **[VPNG0001-R1.R3.C1.C1.R1]** *Чтобы переданная администратору systemd-интеграция оставалась воспроизводимой и не требовала знания внутренних деталей VPN-GATE.* | Документация каждого поддерживаемого first-release systemd способа onboarding должна показывать, как запустить VPN process непосредственно внутри managed network namespace и связать его service lifecycle с unit, владеющим managed domain; для systemd это должно включать эквивалент `NetworkNamespacePath=`, ordering/dependency не слабее `After=` + `BindsTo=`, отдельную однозначно узнаваемую stack-specific unit identity и сохранение обычных `systemctl start/stop/restart` semantics конкретного VPN service. [closed]

   **[VPNG0001-R1.R3.C1.C1.R2]** *Чтобы администратор мог подготовить VPN-specific configuration, не передавая VPN implementation неявное право изменять policy, которой внутри managed domain владеет VPN-GATE.* | Документация поддерживаемой integration должна явно отделять VPN-specific state/configuration от VPN-GATE-owned routes/RPDB/NAT/firewall и описывать integration-specific ограничения или настройки, необходимые для policy-neutral запуска внутри managed domain; host/external orchestration должна оставаться снаружи managed domain, а конфликтующие VPN hooks/equivalent network mutations не должны молча считаться поддерживаемыми. [closed]

   **[VPNG0001-R1.R3.C1.C1.R3]** *Чтобы fail-closed local INPUT/OUTPUT policy не делала формально bound VPN path неработоспособным и при этом не требовала широких локальных исключений.* | Для поддерживаемой integration onboarding contract должен предоставлять VPN-GATE достаточные transport/control facts для построения минимального integration-owned local/system allow внутри managed domain; в Release-1 human config client-side facts принадлежат соответствующему Device и задаются `allow_vpn_client = "tcp|udp[:<local-port>]><remote-IPv4>:<remote-port>"` либо массивом таких строк, а отдельный top-level integration object не является публичной сущностью. Неизвестные или недостаточные facts не должны заменяться blanket local allow, ambient socket discovery или иным расширением разрешений. [closed]

  **[VPNG0001-R1.R3.C2]** *Для выполнения требования изоляции управляемой сетевой среды NG3 использует отдельный изолированный network domain, а не host network namespace как рабочее пространство маршрутизации.* | Поддерживаемый внешний VPN-канал может использоваться VPN-GATE только если его data-plane endpoint может быть представлен внутри изолированной управляемой сетевой среды; VPN-адаптер, остающийся только в обычном сетевом пространстве хоста, не считается полноценным управляемым VPN-путем NG3. [closed]

   **[VPNG0001-R1.R3.C2.R1]** *Чтобы администратор мог выполнить требование изоляции без знания внутренней сетевой механики VPN-GATE.* | Onboarding contract для поддерживаемого внешнего VPN-канала должен описывать требуемый результат размещения его data-plane endpoint внутри изолированной управляемой сетевой среды; конкретный механизм достижения этого результата уточняется только после выбора поддерживаемого способа интеграции. [closed]
   ↳ [decomp: VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1]

## Explicit traffic policy

**[VPNG0002]** *Основание: интервью заказчика с аналитиком, 2026-11-15; требование зафиксировано в initial NG3 requirement tree commit `4b3785b5c228782768afe317d4f09386fd46b440` от 2026-11-15 21:14:07 +03:00; тема: явная пользовательская политика использования VPN.* | VPN-GATE должен использовать VPN для управляемого трафика как следствие явного решения пользователя, а не как побочный эффект наличия работоспособного VPN-пути. [closed]

**[VPNG0002-R2]** *Чтобы использование VPN было следствием явного решения пользователя, а не побочным эффектом наличия работоспособного VPN-пути.* | Пользователь должен иметь возможность явно определить, какой трафик VPN-GATE обслуживает, через какие VPN-пути этот трафик разрешено передавать и в каком направлении. [closed]

 **[VPNG0002-R2.R1]** *Чтобы можно было однозначно отличить управляемый VPN-GATE трафик от остального трафика системы.* | Политика должна однозначно определять, какой трафик входит в область управления VPN-GATE. [closed]

  **[VPNG0002-R2.R1.R1]** *Чтобы Profile мог прямо выражать remote network need пользователя.* | Enabled Profile должен задавать непустой набор strict IPv4 CIDR `destinations`, определяющий его remote/VPN-side prefixes; list order не должен иметь routing semantics, а некорректные/нестрогие CIDR не должны молча canonicalize-иться. [closed]

  **[VPNG0002-R2.R1.R2]** *Чтобы одна Profile destination semantics одинаково определяла нужную remote сеть в обоих направлениях передачи.* | Для ordinary/host-to-VPN NEW traffic VPN-GATE должен выбирать Profile по remote destination prefix; для VPN-to-ordinary/host NEW traffic VPN-GATE должен выбирать Profile по remote source prefix только среди Profiles, разрешающих фактический ingress Device/path. [closed]

 **[VPNG0002-R2.R2]** *Чтобы динамическое состояние системы не могло само расширять разрешенный пользователем набор VPN-путей.* | Для каждого управляемого класса трафика политика должна однозначно определять набор VPN-путей, через которые этот трафик разрешено передавать. [closed]

  **[VPNG0002-R2.R2.R2]** *Чтобы Profile intent оставался Device-level пользовательской политикой, а concrete paths появлялись только после безопасного binding.* | Profile задает допустимые Devices и их порядок, а effective concrete path membership должен получаться только из текущих валидных bindings этих Devices; отсутствие или неоднозначность binding не должны подменяться угадыванием concrete interface/peer. [closed]

  **[VPNG0002-R2.R2.R1]** *Чтобы Profile явно определял, какие пользовательски описанные VPN resources разрешено использовать для его трафика.* | `Profile.device_order` должен быть непустым ordered списком уникальных Device IDs; только enabled Devices из этого списка и их допустимо bound paths могут участвовать в forwarding данного Profile. [closed]

 **[VPNG0002-R2.R3]** *Чтобы разрешение одного направления передачи не становилось неявным разрешением другого.* | Политика должна однозначно определять разрешенное направление передачи управляемого трафика. [closed]

  **[VPNG0002-R2.R3.R3]** *Чтобы направление Profile было читаемым пользовательским policy decision, а не выводилось из topology.* | Enabled Profile должен явно задавать одно из `outbound`, `inbound`, `bidirectional`: outbound разрешает инициирование новых flows со стороны ordinary/host network к Profile destinations, inbound — со стороны разрешенного VPN path к ordinary/host network, bidirectional — оба направления; return traffic уже допустимых flows может обслуживаться statefully независимо от стороны инициатора. [closed]

   **[VPNG0002-R2.R3.R3.R1]** *Чтобы remote-initiated flow не требовал от администратора дублировать Profile destinations в host routing только ради возвратного трафика, если Linux может однозначно сохранить происхождение flow через explicit managed boundary.* | Для `inbound` и `bidirectional` Profile VPN-GATE по умолчанию должен обеспечивать stateful host-boundary return steering: flow, инициированный через разрешенный VPN path и вышедший из managed network domain через ordinary/host boundary, должен сохранять достаточную connection association, чтобы его host-local или forwarded return traffic мог быть направлен обратно в managed boundary без обязательного destination route к remote prefix в host main table. [closed]

    **[VPNG0002-R2.R3.R3.R1.R1]** *Чтобы оператор мог отказаться от host-side stateful return steering и использовать привычную route-based VPN semantics, не отключая conntrack или другие stateful функции целиком.* | Для `inbound` и `bidirectional` Profile пользователь должен иметь canonical opt-out `+route-return`, означающий, что VPN-GATE не использует stateful host-boundary return steering для этого Profile и должен обеспечить return reachability обычным host routing через managed boundary; `outbound+route-return` недопустим, потому что outbound не разрешает remote-initiated flows. [closed]

   **[VPNG0002-R2.R3.C1]** *Потому что безопасная return-path semantics для remote-initiated flow при нескольких одновременно допустимых VPN paths ещё не подтверждена на целевой платформе, а первый release не должен обещать неподтвержденный multi-path inbound behavior.* | В первом release Profile с direction `inbound` или `bidirectional` поддерживается только если его текущая принятая конфигурация может породить не более одного eligible logical VPN path; multi-path inbound/bidirectional относится к будущему release и требует отдельной архитектуры/evidence. [closed]

    **[VPNG0002-R2.R3.C1.R1]** *Чтобы неподдерживаемая multi-path inbound/bidirectional topology не возникала неожиданно после runtime discovery и не требовала угадывать безопасное поведение на лету.* | VPN-GATE должен на этапе config normalization до сетевой actuation отклонять enabled Profile с direction `inbound` или `bidirectional`, если суммарная максимально возможная eligible logical-path capacity его currently enabled referenced Devices превышает 1; VPN-GATE должен выдавать явную диагностируемую причину отказа. [closed]

  **[VPNG0002-R2.R3.R1]** *Чтобы разрешение отправки трафика из обычной сети через VPN не подразумевало обратный доступ.* | Политика должна позволять независимо определить, разрешена ли передача соответствующего управляемого трафика со стороны обычной сети в сторону выбранных VPN-путей. [closed]

   **[VPNG0002-R2.R3.R1.R1]** *Чтобы разрешенный ordinary-to-VPN flow действительно попадал в изолированный routing domain без ручного дублирования внутренней VPN-GATE policy администратором.* | Для каждого enabled Profile, разрешающего ordinary-side initiation (`outbound` или `bidirectional`), VPN-GATE должен создавать и удалять только необходимые ему явные host-boundary routing contributions, направляющие Profile destinations в managed network domain; эти contributions являются эксплуатационно управляемым состоянием VPN-GATE, а администратор обязан не удалять и не подменять их конфликтующей host routing policy во время работы сервиса. [closed]

  **[VPNG0002-R2.R3.R2]** *Чтобы разрешение передачи трафика из VPN в обычную сеть было отдельным явным решением пользователя.* | Политика должна позволять независимо определить, разрешена ли передача соответствующего управляемого трафика со стороны VPN-пути в сторону обычной сети. [closed]

 **[VPNG0002-R2.R4]** *Чтобы наличие работающего VPN или автоматически обнаруженной пригодности пути не изменяло пользовательскую политику доступа.* | Трафик или VPN-путь, не разрешенные текущей политикой, не должны становиться разрешенными из-за доступности, автоматического failover, recovery или иного runtime-состояния. [closed]

 **[VPNG0002-R2.R5]** *Чтобы одинаковая конфигурация не приводила к различному поведению при неоднозначном совпадении нескольких правил.* | Если к одному трафику применимы несколько частей политики, VPN-GATE должен получать один детерминированный эффективный результат либо явно отклонять неоднозначную конфигурацию. [closed]

  **[VPNG0002-R2.R5.R1]** *Чтобы несколько Profiles с пересекающимися remote prefixes не делали классификацию случайной.* | Одинаковый destination prefix не должен принадлежать более чем одному enabled Profile; overlap разных prefix lengths может быть допустим только при детерминированной most-specific классификации, а для VPN-to-host traffic классификация должна учитывать только Profiles, разрешающие фактический ingress Device/path, чтобы более специфичный prefix другого Device не затенял допустимый Profile. [closed]

## Path preference and availability

**[VPNG0003]** *Основание: интервью заказчика с аналитиком, 2026-11-15; требование зафиксировано в initial NG3 requirement tree commit `4b3785b5c228782768afe317d4f09386fd46b440` от 2026-11-15 21:14:07 +03:00; тема: предсказуемое использование нескольких разрешённых VPN-путей.* | Если пользователь разрешил для трафика несколько VPN-путей, VPN-GATE должен обеспечивать предсказуемое использование этих путей и сохранять практическую работоспособность удалённого соединения при деградации предпочтительного пути. [closed]

**[VPNG0003-R3]** *Чтобы при наличии нескольких разрешённых пользователем VPN-путей трафик использовал их предсказуемо и сохранял практическую работоспособность при деградации предпочтительного пути.* | Если пользователь разрешил для данного трафика несколько VPN-путей, VPN-GATE должен использовать их в заданном пользователем порядке предпочтения, автоматически понижать предпочтение действительно проблемных путей и после их восстановления возвращаться к заданному пользователем порядку. [closed]

 **[VPNG0003-R3.R1]** *Чтобы при нормальной работе выбор между несколькими разрешёнными пользователем путями соответствовал намерению пользователя.* | Пользователь должен иметь возможность задать детерминированный порядок предпочтения нескольких разрешённых путей, а VPN-GATE должен использовать этот порядок как настроенный baseline preference. [closed]

  **[VPNG0003-R3.R1.R1]** *Чтобы пользовательский порядок Devices и ожиданий внутри Device сохранялся при появлении нескольких runtime endpoints.* | Для Profile настроенный baseline preference должен следовать иерархии `Profile.device_order -> Device.expected_interfaces order -> stable runtime slot внутри selector quota`; появление нового endpoint не должно произвольно переставлять уже bound survivors. [closed]

 **[VPNG0003-R3.R2]** *Чтобы availability-механизм не подменял собой пользовательскую политику.* | Автоматическая адаптация по состоянию пути может изменять только эффективное предпочтение среди уже разрешенных путей и не должна изменять их policy membership. [closed]

  **[VPNG0003-R3.R2.R1]** *Чтобы временная проблема path не переписывала смысл Profile и не превращала runtime health в источник structural policy.* | Availability outcome может использоваться только как отрицательный модификатор effective priority конкретного Profile-path; он не должен изменять Profile destinations, direction, Device membership, binding eligibility или структурный payload-policy request. [closed]

 **[VPNG0003-R3.R3]** *Чтобы новый трафик не продолжал предпочитать путь, для которого получены достаточные признаки практической непригодности, когда существует разрешённая пользователем пригодная альтернатива.* | После достаточного подтверждения проблемы на предпочтительном пути VPN-GATE должен понизить его эффективное предпочтение относительно разрешенных путей без подтвержденной проблемы. [closed]

 **[VPNG0003-R3.R4]** *Чтобы временная деградация не превращалась в постоянное изменение пользовательской политики.* | После достаточного подтверждения восстановления пути VPN-GATE должен вернуть его к позиции, заданной настроенным порядком предпочтения. [closed]

 **[VPNG0003-R3.R5]** *Чтобы единичное, кратковременное или случайное наблюдение не вызывало ненужной перестройки маршрутизации.* | Переход между нормальным и пониженным предпочтением должен требовать достаточного подтверждения деградации и восстановления, чтобы единичное случайное наблюдение само по себе не вызывало переключение. [closed]

  **[VPNG0003-R3.R5.R1]** *Чтобы единичная потеря или отсутствие одного положительного наблюдения не понижали путь, который практически остается пригодным.* | Путь без установленной availability-проблемы должен переходить в пониженное предпочтение только после достижения конечного policy-defined порога подтверждения деградации по актуальным evidence/evaluation boundaries. [closed]

  **[VPNG0003-R3.R5.R2]** *Чтобы случайное единичное успешное наблюдение не возвращало проблемный путь в предпочтительное положение раньше устойчивого восстановления.* | Путь с установленной availability-проблемой должен возвращаться к настроенному предпочтению только после достижения конечного policy-defined порога актуальных положительных свидетельств восстановления. [closed]

 **[VPNG0003-R3.R6]** *Чтобы автоматическая адаптация опиралась на сведения, действительно относящиеся к текущей пригодности конкретного пути, а не на догадку о его состоянии.* | VPN-GATE должен получать достаточно актуальные сведения о пригодности каждого пути, для которого включена автоматическая availability-адаптация, используя механизм наблюдения, достаточный для поддерживаемого сценария. [closed]

  **[VPNG0003-R3.R6.R1]** *Чтобы сведения о пригодности одного Profile-path не изменяли решение для другого Profile, даже если они используют тот же Device/interface.* | Каждое availability-свидетельство, используемое для адаптации, должно быть однозначно связано с availability subject = (Profile, logical VPN path); физический interface/endpoint сам по себе не является достаточной идентичностью availability. [closed]

  **[VPNG0003-R3.R6.R2]** *Чтобы старое наблюдение не изменяло решение после замены наблюдаемого экземпляра пути или существенного изменения контекста, к которому относилось это наблюдение.* | Availability-свидетельство, потерявшее актуальность для текущего экземпляра или контекста пути, не должно влиять на текущее effective preference. [closed]

  **[VPNG0003-R3.R6.R3]** *Чтобы формально успешное наблюдение локального объекта не скрывало отказ, который делает VPN-путь непригодным в реально поддерживаемом сценарии.* | Механизм получения availability evidence должен наблюдать свойство, достаточное для выявления тех видов непригодности пути, которые существенны для поддерживаемых продуктовых сценариев. [closed]

   **[VPNG0003-R3.R6.R3.R1]** *Чтобы критерий пригодности соответствовал сетевой потребности конкретного Profile, а не универсальному предположению VPN-GATE о том, что означает «интерфейс работает».* | Для availability-enabled сочетания Profile и логического VPN-пути пользователь должен иметь возможность задать Profile-scoped проверку пригодности как механизм наблюдения и, когда механизм этого требует, целевой endpoint; именно результат этой проверки определяет evidence для данного availability subject. [closed]

    **[VPNG0003-R3.R6.R3.R1.C1]** *Для первого release принят минимальный достаточный active-check scope: необходимость универсального probe framework не подтверждена требованиями до реализации и проверки базового ICMP path.* | В первом release поддерживаемым пользовательским механизмом availability-проверки является ICMP echo; конфигурация и architecture contracts не должны считать TCP, UDP, HTTP или иной механизм уже поддерживаемым. [closed]

     **[VPNG0003-R3.R6.R3.R1.C1.R1]** *Чтобы пользователь мог осознанно выбрать пригодный ICMP-критерий в пределах ограничения первого release.* | Release-1 Profile config должен использовать `availability_check = "icmp"` для path-specific автоматически выводимого target или `availability_check = "icmp/<IPv4>"` для явно заданного target; отсутствие поля отключает active check. Timing/hysteresis knobs в Release-1 не требуются; невозможность выполнить или однозначно разрешить target должна диагностироваться. [closed]

   **[VPNG0003-R3.R6.R3.R2]** *Чтобы пользователь мог использовать краткую Profile-level availability-проверку без дополнительного ручного IP, когда конкретная path-specific точка однозначно следует из уже заданной топологии/семантики.* | Target пользовательской availability-проверки должен быть опциональным во внешней конфигурации; до формирования runtime probe demand VPN-GATE должен нормализовать конфигурацию так, чтобы каждый enabled probe имел один конкретный IPv4 target. Если пользователь задал target явно, VPN-GATE должен сохранить именно его в нормализованном probe. Если пользователь опустил target, VPN-GATE должен детерминированно вывести один target из уже принятой конфигурации и наблюдаемых semantics соответствующих Profile, logical path, Device/interface/binding/peer topology — без универсального глобального default IP и без требования дополнительного ручного target. Если VPN-GATE не может вывести однозначный target, он не должен молча использовать произвольный адрес и должен предоставить диагностируемую причину. [closed]

 **[VPNG0003-R3.R7]** *Чтобы само включение availability-функции не ухудшало или произвольно изменяло нормальное поведение маршрутизации.* | Пока для разрешенных путей нет достаточного подтверждения проблемы, effective order должен совпадать с настроенным пользовательским порядком. [closed]

## Safety under uncertainty and failure

**[VPNG0004]** *Основание: интервью заказчика с аналитиком, 2026-11-15; требование зафиксировано в initial NG3 requirement tree commit `4b3785b5c228782768afe317d4f09386fd46b440` от 2026-11-15 21:14:07 +03:00; тема: безопасное поведение при ошибке и неопределённости.* | VPN-GATE должен предотвращать передачу управляемого трафика способом, который пользователь не разрешил, когда ошибка, неполная конфигурация или непроверенное состояние не позволяют подтвердить допустимость передачи. [closed]

**[VPNG0004-R4]** *Чтобы ошибка, неполная конфигурация или непроверенное состояние не приводили к передаче управляемого трафика способом, который пользователь не разрешал.* | VPN-GATE не должен передавать управляемый трафик способом, не разрешенным текущей политикой или безопасность которого продукт не может подтвердить; при существенной неопределенности предпочтителен отказ от передачи. [closed]

 **[VPNG0004-R4.R1]** *Чтобы отсутствие однозначного policy result не превращалось в неявное разрешение.* | Если VPN-GATE не может однозначно определить разрешенное поведение для управляемого трафика, такой трафик не должен получать неявный VPN forwarding. [closed]

  **[VPNG0004-R4.R1.R1]** *Чтобы временное отсутствие всех допустимых paths не превращало Profile destination в обычный трафик, способный уйти через ambient/main routing.* | Если enabled Profile существует, но для него сейчас нет ни одного валидного effective concrete path, его управляемые destinations должны оставаться в Profile policy domain и завершаться fail-closed; Profile не должен исчезать из structural policy только из-за `paths = 0`. [closed]

 **[VPNG0004-R4.R2]** *Чтобы продукт не считал желаемое сетевое состояние фактически действующим без подтверждения.* | Если фактическое сетевое состояние, критичное для безопасной передачи, неизвестно или не может быть подтверждено, VPN-GATE должен сохранять или устанавливать безопасное ограничивающее поведение до получения достаточного подтверждения. [closed]

 **[VPNG0004-R4.R3]** *Чтобы корректная конечная конфигурация не достигалась через промежуточное состояние с неразрешенной передачей трафика.* | VPN-GATE должен выполнять изменение effective network policy так, чтобы промежуточные состояния не создавали передачу, запрещенную до или после изменения. [closed]

  **[VPNG0004-R4.R3.R1]** *Чтобы обычное изменение приоритета между уже разрешенными VPN-путями не превращалось в плановый разрыв сервиса только ради перестановки маршрутов.* | Если transition меняет только effective priority/order уже разрешенного неизменного набора VPN-путей, все эти пути должны оставаться представленными в forwarding state на протяжении transition; допустима временная дополнительная route-копия того же разрешенного пути, но разрешенный путь не должен временно удаляться как staging-жертва перестановки. [closed]

  **[VPNG0004-R4.R3.R2]** *Чтобы более широкое изменение policy не требовало небезопасного сохранения forwarding любой ценой.* | Если transition изменяет membership, direction, filtering/NAT или другую структурную semantics помимо одной перестановки приоритета, VPN-GATE может временно ограничить затронутый forwarding, когда это необходимо для выполнения safety postconditions, но не должен открывать передачу, запрещенную старой или новой policy. [closed]

 **[VPNG0004-R4.R4]** *Чтобы запуск процесса не открывал трафик до построения и проверки требуемой политики.* | До подтверждения безопасной исходной сетевой границы VPN-GATE не должен считать payload forwarding готовым к использованию. [closed]

 **[VPNG0004-R4.R5]** *Чтобы ошибка посреди изменения сетевого состояния не оставляла продукт в неизвестном разрешающем режиме.* | После частично выполненного или неуспешного изменения network policy VPN-GATE должен повторно установить авторитетное фактическое состояние и либо безопасно довести его до требуемого результата, либо оставить соответствующий трафик закрытым. [closed]

 **[VPNG0004-R4.R6]** *Чтобы ошибки, восстановление и развитие VPN-GATE не изменяли несвязанные сетевые настройки хоста и не превращали host networking в неявную часть внутреннего состояния продукта.* | Сетевое состояние, которым VPN-GATE управляет для обслуживания трафика, должно быть изолировано от обычного сетевого пространства хоста и взаимодействовать с ним только через явно определенные границы; изменения внутри управляемой области не должны требовать владения или произвольного изменения несвязанного host network state. [closed]

  **[VPNG0004-R4.R6.R1]** *Чтобы изоляция была не декларацией, а проверяемой границей владения сетевым состоянием.* | VPN-GATE должен иметь отдельный управляемый сетевой домен, в котором локализованы принадлежащие продукту routing/policy/data-plane состояния; взаимодействие этого домена с внешней сетью и хостом должно происходить только через явно определенные граничные точки, а используемые VPN data-plane endpoints должны быть представлены внутри этого домена. [closed]

   **[VPNG0004-R4.R6.R1.R1]** *Чтобы внутренние изменения VPN-GATE не требовали знания или изменения несвязанных сетевых объектов хоста.* | Сетевые объекты и mutable state, необходимые для внутренней маршрутизации и policy VPN-GATE, должны принадлежать управляемому сетевому домену либо явно объявленной boundary-области; произвольные host routes/rules/firewall state не должны использоваться как скрытая часть внутренней модели VPN-GATE. [closed]

   **[VPNG0004-R4.R6.R1.R2]** *Чтобы весь обмен между управляемой сетью VPN-GATE и внешней средой был видим, проверяем и управляем.* | Вход и выход управляемого трафика из сетевого домена должны происходить через явно определенные boundary endpoints с известной ролью и направлением; наличие обычной host connectivity само по себе не должно создавать неявную границу передачи. [closed]

   **[VPNG0004-R4.R6.R1.R3]** *Чтобы VPN-путь подчинялся тем же routing, policy и safety правилам, что и остальная управляемая сеть.* | Data-plane endpoint каждого VPN-пути, используемого VPN-GATE для managed forwarding, должен быть доступен внутри управляемого сетевого домена как его внутренний path endpoint; endpoint, существующий только в обычном host network space, не должен использоваться напрямую как управляемый VPN-путь. [closed]

   **[VPNG0004-R4.R6.R1.R4]** *Чтобы продукт не считал внешнюю интеграцию корректной только потому, что администратор выполнил некоторую настройку.* | До использования внешнего boundary endpoint или VPN path endpoint VPN-GATE должен иметь возможность проверить, что требуемый endpoint присутствует в правильном управляемом домене, однозначно соответствует ожидаемой роли/идентичности и пригоден для дальнейшего применения policy; несоответствие должно оставаться безопасным и наблюдаемым. [closed]


   **[VPNG0004-R4.R6.R1.R5]** *Чтобы наличие сетевого стека и локальных/forwarding hooks внутри managed domain само по себе не создавало неописанную разрешающую поверхность при неполной policy.* | VPN-GATE должен до объявления managed payload forwarding готовым поддерживать в своём managed network domain default filter policies `INPUT=DROP`, `OUTPUT=DROP` и `FORWARD=DROP`; разрешения поверх этих defaults должны быть явными owned contributions, подтверждаемыми из текущей принятой policy и внутренних product needs. [closed]

    **[VPNG0004-R4.R6.R1.R5.R1]** *Чтобы пользовательский Device firewall ограничивал VPN payload, не заставляя пользователя одновременно администрировать внутренний control/probe plane VPN-GATE.* | Пользовательские Device firewall rules должны влиять только на managed payload forwarding, а необходимые локальные `INPUT/OUTPUT` исключения для поддерживаемых VPN-GATE control, probe, publication или integration функций должен формировать и владеть сам VPN-GATE; такие исключения не должны становиться разрешением произвольного payload forwarding или изменением firewall обычного host network namespace. [closed]


   **[VPNG0004-R4.R6.R1.R6]** *Чтобы optional gateway NAT за пределами managed network domain не превращал явную boundary-функцию в произвольное владение host networking.* | Когда Profile ordinary-side gateway NAT включён, VPN-GATE должен создавать, проверять и удалять только явно принадлежащие ему host-boundary NAT contributions, необходимые для этой функции; они должны быть ограничены traffic, вышедшим из managed boundary после принятой VPN policy, и не должны давать VPN-GATE право произвольно изменять несвязанный host firewall/routing state. [closed]

    **[VPNG0004-R4.R6.R1.R6.R1]** *Чтобы после общего host boundary gateway NAT одного Profile не применялся к traffic другого Profile с пересекающимися remote prefixes или другим ingress path.* | До применения Profile ordinary-side gateway NAT VPN-GATE должен сохранить или иным проверяемым способом перенести через explicit host boundary однозначную ассоциацию packet с уже выбранным Profile; если lower realization не может подтвердить такую ассоциацию, VPN-GATE не должен применять per-Profile gateway NAT или объявлять эту функцию готовой. [closed]
   ↳ [decomp: VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2]

## Lifecycle and recovery

**[VPNG0005]** *Основание: интервью заказчика с аналитиком, 2026-11-15; требование зафиксировано в initial NG3 requirement tree commit `4b3785b5c228782768afe317d4f09386fd46b440` от 2026-11-15 21:14:07 +03:00; тема: предсказуемый жизненный цикл и восстановление.* | Оператор должен иметь возможность предсказуемо запускать, эксплуатировать, перезапускать и останавливать VPN-GATE без ручной уборки или восстановления внутренних сетевых объектов продукта. [closed]

**[VPNG0005-R5]** *Чтобы VPN-GATE можно было предсказуемо запускать, эксплуатировать, перезапускать и останавливать без ручной уборки или восстановления его внутренних сетевых объектов.* | VPN-GATE должен управлять жизненным циклом принадлежащего ему runtime-состояния, восстанавливать требуемое состояние после обычных восстановимых изменений среды и явно сообщать, когда безопасное восстановление невозможно. [closed]

 **[VPNG0005-R5.R1]** *Чтобы одинаковая допустимая конфигурация приводила к воспроизводимому рабочему состоянию.* | Startup должен из безопасной исходной границы построить и подтвердить необходимое runtime-состояние до объявления соответствующих функций готовыми. [closed]

 **[VPNG0005-R5.R2]** *Чтобы обычное изменение или потеря принадлежащего продукту runtime-состояния не требовали ручного пересоздания всей системы.* | Во время работы VPN-GATE должен уметь обнаруживать существенное расхождение между требуемым и фактическим принадлежащим ему состоянием и восстанавливать его, если это безопасно и возможно. [closed]

  **[VPNG0005-R5.R2.R1]** *Чтобы тихое внешнее изменение принадлежащего VPN-GATE состояния было обнаружено даже без нового действия пользователя.* | Пока соответствующая функция VPN-GATE активна, обнаружение существенного drift не должно зависеть только от прихода новой конфигурации или управляющей операции; продукт должен повторно наблюдать принадлежащее ему фактическое состояние с конечной cadence, достаточной для обычного автоматического восстановления. [closed]

 **[VPNG0005-R5.R3]** *Чтобы временный технический отказ не становился постоянной потерей функции после исчезновения его причины.* | Операция, не выполненная из-за восстановимой ошибки, должна оставаться повторяемой из актуального подтвержденного состояния без необходимости перезапуска всего продукта, если этого не требует сама внешняя среда. [closed]

  **[VPNG0005-R5.R3.R1]** *Чтобы после временного отказа пользователь не был обязан повторно отправлять уже действующее намерение только для запуска восстановления.* | Если требуемое состояние остается актуальным после восстановимой ошибки, VPN-GATE должен самостоятельно выполнить последующую попытку его достижения после нового наблюдения фактического состояния; повтор не должен требовать нового пользовательского request. [closed]

 **[VPNG0005-R5.R4]** *Чтобы остановленный или удаленный VPN-GATE не продолжал незаметно влиять на сетевое поведение системы.* | После успешного shutdown/cleanup не должны оставаться активные сетевые или процессные ресурсы, принадлежащие остановленному экземпляру VPN-GATE и продолжающие влиять на трафик. [closed]

 **[VPNG0005-R5.R5]** *Чтобы отказ одной независимой части cleanup не мешал попытке безопасно убрать другие принадлежащие продукту части состояния.* | Если несколько независимо управляемых областей требуют cleanup или recovery, ошибка одной области не должна сама по себе отменять попытку обработать остальные; все существенные ошибки должны оставаться наблюдаемыми. [closed]

 **[VPNG0005-R5.C1]** *Поскольку root/admin может произвольно удалить или изменить owned namespace, veth, unit dependency или другой host artifact вне штатного lifecycle, а автоматическое forensic-восстановление произвольно поврежденной среды потребовало бы небезопасного adoption чужих процессов и неоправданно универсальной recovery-механики.* | Гарантии автоматического lifecycle/recovery первого release действуют для состояния, управляемого через штатный VPN-GATE/systemd contract; прямое out-of-band изменение или удаление VPN-GATE-owned host artifacts является внешним вмешательством. VPN-GATE должен при обнаружимом нарушении инварианта fail closed и диагностировать его, но не обязан автоматически находить, усыновлять или очищать произвольные процессы/namespace references, оставшиеся после такого вмешательства. [closed]

  **[VPNG0005-R5.C1.R1]** *Чтобы ограничение recovery не превращалось для администратора в скрытую ловушку.* | Административная документация должна явно перечислять границу штатного lifecycle, предупреждать против ручного изменения VPN-GATE-owned namespace/dependency artifacts и описывать, что устранение последствий такого out-of-band вмешательства является обязанностью администратора до возврата к штатному start/recovery. [closed]

 **[VPNG0005-R5.R6]** *Чтобы оператор управлял жизненным циклом VPN-GATE через продуктовые операции, а не вручную воспроизводил внутренние сетевые действия.* | VPN-GATE должен предоставлять явные lifecycle-операции как минимум для запуска, остановки и перезапуска экземпляра; результат каждой операции должен определяться достижением соответствующего безопасного postcondition, а не фактом выдачи внутренних команд. [closed]

  **[VPNG0005-R5.R6.R1]** *Чтобы успешный start означал готовый к эксплуатации экземпляр, а не только запущенный процесс.* | Операция start должна считаться успешной только после выполнения и подтверждения startup postconditions, требуемых текущей конфигурацией и safety policy. [closed]

  **[VPNG0005-R5.R6.R2]** *Чтобы успешный stop означал прекращение влияния экземпляра на сеть.* | Операция stop должна считаться успешной только после выполнения требуемого cleanup принадлежащего экземпляру активного состояния либо должна явно сообщить о неполном cleanup. [closed]

  **[VPNG0005-R5.R6.R3]** *Чтобы restart не требовал ручного устранения следов предыдущего экземпляра.* | Операция restart должна обеспечивать безопасный переход от текущего экземпляра к состоянию, эквивалентному успешному новому start после необходимого stop/cleanup; неполное завершение предыдущего состояния не должно молча объявляться успешным restart. [closed]

## Observability

**[VPNG0006]** *Основание: интервью заказчика с аналитиком, 2026-11-15; требование зафиксировано в initial NG3 requirement tree commit `4b3785b5c228782768afe317d4f09386fd46b440` от 2026-11-15 21:14:07 +03:00; тема: наблюдаемость фактического и эффективного состояния.* | Оператор должен иметь возможность определить фактическое поведение VPN-GATE и причину невозможности выполнить требуемую политику без реконструкции внутреннего состояния по логам и kernel-командам. [closed]

**[VPNG0006-R6]** *Чтобы оператор мог понять фактическое поведение VPN-GATE и причину невозможности выполнить требуемую политику, не восстанавливая внутреннее состояние по логам и kernel-командам.* | VPN-GATE должен предоставлять наблюдаемую текущую проекцию существенного настроенного, фактического и эффективного состояния, а также проблем, мешающих выполнить требуемую политику. [closed]

 **[VPNG0006-R6.R1]** *Чтобы оператор мог проверить, какое поведение продукт считает требуемым.* | Оператор должен иметь возможность определить существенную текущую конфигурацию и policy intent, используемые VPN-GATE. [closed]

 **[VPNG0006-R6.R2]** *Чтобы оператор мог понять, какие разрешенные VPN-пути фактически участвуют в текущем выборе и каков их effective order.* | Оператор должен иметь возможность определить текущий набор разрешённых для использования путей, существенное availability-состояние и effective preference, применяемые VPN-GATE к управляемому трафику. [closed]

 **[VPNG0006-R6.R3]** *Чтобы невозможность выполнить требование не выглядела как молчаливое отсутствие функции.* | Существенные проблемы, из-за которых требуемая policy, lifecycle operation или safety postcondition не могут быть выполнены, должны быть доступны оператору. [closed]

 **[VPNG0006-R6.R4]** *Чтобы observability не сообщала желаемое состояние как фактическое.* | Текущая status-проекция должна различать требуемое, подтвержденное фактическое и неизвестное/неподтвержденное состояние там, где это различие влияет на пользовательское понимание поведения или safety. [closed]

## Implementation quality

**[VPNG0007]** *Основание: интервью заказчика с аналитиком, 2026-11-15; требование зафиксировано в initial NG3 requirement tree commit `4b3785b5c228782768afe317d4f09386fd46b440` от 2026-11-15 21:14:07 +03:00; тема: сопровождаемость и контролируемая сложность реализации.* | Разработчики и применяемые в проекте AI-инструменты должны иметь возможность безопасно развивать и сопровождать VPN-GATE без превращения продукта в неоправданно универсальную систему или хрупкий монолит. [closed]

**[VPNG0007-R7]** *Чтобы VPN-GATE можно было безопасно развивать и сопровождать живыми разработчиками и AI, не превращая продукт ни в универсальную систему из ненужных механизмов, ни в хрупкий монолит, изменение которого требует понимания всего кода сразу.* | Реализация VPN-GATE должна быть минимально достаточной для принятых требований, сопровождаемой и понятной, допускать локальное изменение и параллельную разработку через явные внутренние контракты и не содержать сложности, не оправданной требованиями или реальными целевыми сценариями. [closed]

 **[VPNG0007-R7.R1]** *Чтобы развитие продукта не создавало состояния, компоненты и универсальные механизмы, которые увеличивают стоимость сопровождения без продуктовой ценности.* | Каждый существенный механизм, состояние, очередь, lifecycle, retry policy, interaction и компонент должны быть необходимы для конкретного принятого требования или ограничения; неоправданная общность должна удаляться или не создаваться. [closed]

  **[VPNG0007-R7.R1.R1]** *Чтобы локальная задача не превращалась в систему хранения и воспроизведения истории без необходимости.* | Если требование может быть полностью выполнено текущим или ограниченным агрегированным состоянием, реализация не должна вводить неограниченную историю, журнал или replay-механику. [closed]

 **[VPNG0007-R7.R2]** *Чтобы сопровождение и review не зависели от знания неявной глобальной механики одним автором.* | Существенные обязанности, состояния, контракты и причины проектных решений должны быть локализованы и документированы настолько, чтобы разработчик или AI мог определить назначение блока, его границы и последствия изменения без реконструкции всей системы. [closed]

 **[VPNG0007-R7.R3]** *Чтобы изменения внутри одной области не распространялись на несвязанные части продукта через неявные зависимости.* | Внутренние области реализации должны взаимодействовать через явные контракты, скрывающие детали, которые не требуются соседней области. [closed]

  **[VPNG0007-R7.R3.R1]** *Чтобы зависимость между частями системы была видима для разработки, review и тестирования.* | Материальная межкомпонентная зависимость должна быть представлена явным контрактом, определяющим необходимые входы, выходы и семантику взаимодействия. [closed]

  **[VPNG0007-R7.R3.R2]** *Чтобы замена или изменение внутреннего механизма нижней области не требовали переделки верхней policy без продуктовой причины.* | Внутренние технические детали одной предметной области не должны пересекать ее контрактную границу, если они не нужны другой области для выполнения собственного принятого требования. [closed]

  **[VPNG0007-R7.R3.R3]** *Чтобы исправление или развитие одной ответственности можно было выполнять и проверять изолированно.* | Изменение реализации внутри стабильного внутреннего контракта не должно требовать изменения несвязанных потребителей этого контракта. [closed]

 **[VPNG0007-R7.R4]** *Чтобы независимые части продукта можно было проектировать, реализовывать и проверять параллельно без постоянной сериализации работы через общий внутренний код.* | Архитектура должна позволять выделять независимые review/development units с явными контрактными границами и достаточным локальным evidence, когда требования не создают неизбежной общей транзакционной ответственности. [closed]

 **[VPNG0007-R7.R5]** *Чтобы декомпозиция NG3 использовала единый проверяемый словарь обязанностей и взаимодействий вместо ad-hoc архитектурных ролей.* | Архитектура и реализация NG3 должны соответствовать `design/component-model.md`; существенное отклонение допускается только после явного изменения требования, ограничения или самой компонентной модели через review. [closed]

 **[VPNG0007-R7.R6]** *Чтобы архитектура оставалась отчетом о реализации принятых требований, а не становилась самостоятельным источником новых функций и сложности.* | Каждое существенное архитектурное решение NG3 должно явно ссылаться на наиболее конкретные requirement/constraint IDs, которые его требуют или ограничивают; решение без честной трассировки является finding. [closed]

  **[VPNG0007-R7.R6.R1]** *Чтобы можно было как найти реализацию требования, так и установить причину существования архитектурного элемента.* | Документация должна позволять пройти по связям `requirement -> architecture -> implementation/evidence` и обратно `architecture -> requirement/constraint`. [closed]

  **[VPNG0007-R7.R6.R2]** *Чтобы изменение смысла требования не оставляло архитектуру, формально ссылающуюся на уже другой contract.* | Изменение requirement/constraint требует повторной проверки архитектурных решений, ссылающихся на измененный узел или его затронутых потомков, до продолжения реализации. [closed]

 **[VPNG0007-R7.R7]** *Чтобы развитие VPN-GATE оставалось управляемым, предсказуемым и доказуемым, а реализация или эксперимент не становились самостоятельным источником продуктовой семантики.* | Каждый существенный development/evidence unit должен быть необходим для реализации, проверки или честного закрытия конкретного принятого Requirement/Constraint и до начала работы иметь явную трассировку к этому R/C и ожидаемому результату evidence/review. [closed]

  **[VPNG0007-R7.R7.R1]** *Чтобы разработка интеграции не закрепляла lifecycle, ownership или safety решения поверх недоказанной базовой возможности использовать реальный VPN внутри целевого stack.* | Зависимая разработка интеграции, предполагающая поддерживаемый VPN внутри managed network domain, должна начинаться только после воспроизводимого PASS базового applicability evidence, требуемого `VPNG0001-R1.R3.C1.R1.R1`; FAIL этого gate должен сначала вернуть затронутые integration assumptions в requirement/architecture review. [closed]

   **[VPNG0007-R7.R7.R1.R1]** *Чтобы после подтверждения базовой запускабельности VPN проект не принял lifecycle/ownership контракт, работающий только на одном чистом запуске или на безобидной VPN-specific конфигурации.* | После PASS базового applicability gate проект должен на той же подтвержденной integration провести отдельный lifecycle experiment до принятия зависимой bounded-VPN lifecycle семантики: проверить start, stop, restart с неизмененной VPN-specific конфигурацией, restart с измененной VPN-specific конфигурацией, отсутствие зависимости нового запуска от runtime-состояния предыдущего экземпляра и поведение при aggressive VPN-specific configuration, включая hooks или другие механизмы, пытающиеся изменять routes, RPDB, NAT, firewall, sysctl или иное сетевое состояние внутри managed network domain. [closed]

 **[VPNG0007-R7.R8]** *Чтобы требуемая `VPNG0007-R7` безопасная сопровождаемость long-running привилегированного runtime не зависела от ручного предотвращения классов memory-management дефектов и от менее предсказуемой runtime performance-модели там, где локальные изменения непосредственно влияют на сетевую policy.* | Целевая production-реализация VPN-GATE runtime должна быть выполнена на Rust. Production runtime включает код, непосредственно участвующий в lifecycle, configuration normalization, runtime state, policy calculation/reconciliation, VPN-path observation и взаимодействии с сетевым состоянием ОС. [closed]

  **[VPNG0007-R7.R8.C1]** *Поскольку ранние releases прежде всего должны проверить продуктовую семантику, integration applicability и эксплуатационную пригодность, а обязательный предварительный перенос уже работающего reference runtime на Rust замедлил бы получение такого evidence без изменения пользовательского поведения.* | Требование целевой реализации production runtime на Rust не является release gate для первых alpha/beta releases VPN-GATE. Ранние releases могут использовать существующую реализацию на другом языке, включая Python reference implementation, пока такой release явно не объявлен окончательной production/stable реализацией. Переход на Rust должен быть выполнен до release, для которого проект впервые заявляет соответствие целевой production implementation boundary этого требования. [closed]

  **[VPNG0007-R7.R8.R1]** *Чтобы выбор Rust для production runtime не запрещал более дешевые и удобные инструменты там, где их свойства не входят в runtime safety/performance boundary продукта.* | Другие языки допускаются для disposable experiments, evidence/CI harnesses, test fixtures, build/install tooling, code generation и исследовательских/reference implementations, если такой код не становится частью окончательной production runtime implementation boundary. [closed]

  **[VPNG0007-R7.R8.R2]** *Чтобы наличие Rust само по себе не создавало ложного утверждения о memory safety при произвольном использовании небезопасных границ.* | `unsafe` Rust и memory-unsafe FFI в production runtime должны быть ограничены минимально необходимыми lower-level boundaries, локализованы, иметь явное техническое обоснование и не использоваться для обхода invariants, выразимых средствами safe Rust. [closed]

  **[VPNG0007-R7.R8.R3]** *Чтобы текущие executable Python implementations не превратились по инерции из design/evidence artifacts в неподтвержденную окончательную production architecture.* | Python-код, созданный в NG3 для reference implementation, экспериментов и executable evidence, должен рассматриваться как источник проверяемого поведения и реализации принятых contracts. Его использование в ранних releases допускается `VPNG0007-R7.R8.C1`, но оно не отменяет целевой Rust implementation boundary; перенос поведения на Rust должен сохранять соответствующие requirement, architecture и evidence contracts без изменения продуктовой семантики только по причине смены языка. [closed]

## Initial acceptance/evidence expectations

This table adds no new requirement semantics.

| L1 | Minimum final evidence type |
| --- | --- |
| `VPNG0001-R1` | end-to-end VPN-path forwarding and externally provisioned channel onboarding scenario |
| `VPNG0002-R2` | policy acceptance/rejection scenarios |
| `VPNG0003-R3` | deterministic failover/failback scenarios with path-state changes |
| `VPNG0004-R4` | negative/failure scenarios proving no unintended forwarding |
| `VPNG0005-R5` | startup, drift, retry and shutdown lifecycle scenarios |
| `VPNG0006-R6` | status projection checked against authoritative runtime state |
| `VPNG0007-R7` | architecture/review traceability plus isolated-change evidence |

## Constraint policy for this NG3 pass

No NG2 implementation constraint is accepted into NG3 merely by inheritance.

`VPNG0001-R1.R3.C1` is accepted explicitly for the first product release: VPN-channel
provisioning/configuration remains an administrator responsibility, while VPN-GATE must
provide the instructions/contract required to consume those channels.

Other candidate constraints discovered while building the NG3 architecture must be added at
the requirement node whose promise they actually restrict and must pass normal constraint
lifting before they become accepted NG3 constraints.
