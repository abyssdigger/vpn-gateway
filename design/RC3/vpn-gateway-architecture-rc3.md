# VPN Gateway — архитектурные решения и инварианты

**Статус:** Release Candidate — кандидат на утверждение и реализацию
**Версия:** RC3
**Дата:** 2026-11-09

Документ фиксирует принятые архитектурные решения проекта VPN Gateway. Он описывает обязательные инварианты, жизненный цикл сервиса, модель владения kernel-state и правила конфигурации. Нереализованные детали, которые ещё требуют отдельного решения, вынесены в раздел **«Открытые решения»**.

Нормативная терминология проекта определена в [«Терминах и определениях»](terms-and-definitions.md).

## 1. Назначение

VPN Gateway — локальный IPv4-шлюз, который:

- направляет заданные сети через один или несколько VPN-профилей;
- не зависит от конкретной VPN-реализации;
- применяет собственную фильтрацию `INPUT`/`FORWARD`;
- применяет NAT;
- использует защитные blackhole-маршруты для fail-closed поведения;
- отслеживает появление/исчезновение VPN-интерфейса через Netlink.

Конфигурация может содержать произвольный каталог описанных VPN-профилей. Runtime daemon отслеживает и обслуживает только профили, перечисленные в top-level `managed_vpns`. Автоматического failover между профилями нет.

IPv6-маршрутизация проектом не поддерживается.

## 2. Общие принципы

### 2.1. Жёсткий отказ

При ошибке очистки, валидации или применения конфигурации сервис не переходит в частично рабочее состояние.

Ошибка на старте означает:

- `ip_forward` не включается;
- новая конфигурация не считается применённой;
- процесс завершается с ненулевым кодом;
- systemd переводит сервис в `failed`.

Режим `DEGRADED` на старте не используется.

### 2.2. Отказ с запретом

Защищаемый трафик не должен при отказе VPN или ошибке конфигурации уходить через обычный default route.

Blackhole-маршруты являются одним из защитных механизмов и устанавливаются до разрешения forwarding.

Важно: blackhole обеспечивает отказ с запретом на уровне выбора маршрута для соответствующего префикса. Он не является универсальной гарантией доставки и не заменяет независимую фильтрацию `FORWARD`.


### 2.3. Один владелец сетевого состояния

Один долгоживущий процесс `vpn-gatewayd` является единственным владельцем ресурсов проекта:

- daemon-owned firewall policy;
- blackhole;
- VPN-маршрутов;
- NAT;
- `net.ipv4.ip_forward`.

Внешние скрипты и административные клиенты не должны самостоятельно изменять эти ресурсы.

`vpn-gatewayd` предназначен для выделенного VPN-gateway host. Совмещение с Docker,
Kubernetes, другими gateway-сервисами или иными компонентами, которым требуется
`net.ipv4.ip_forward=1`, не поддерживается.

Эксклюзивное владение глобальным `net.ipv4.ip_forward` означает эксклюзивную
ответственность за **весь IPv4 FORWARD decision** во время работы daemon. Пока
`ip_forward=1`, каждый forwarded IPv4 packet обязан получить окончательное решение внутри
daemon-owned префикса правил; пакет не может провалиться в сторонние правила или built-in
`FORWARD ACCEPT`.

Чужие FORWARD rules не удаляются и не переписываются. Они физически остаются после
daemon-owned prefix, но при включённом forwarding недостижимы из-за terminal
`VPNG-FORWARD-DENY`. После `cleanup()` daemon-owned jumps/chains исчезают и
`ip_forward=0`; базовый firewall хоста снова полностью принадлежит администратору.

`net.ipv4.ip_forward` находится в exclusive ownership daemon'а. Ручное изменение sysctl
не является persistent administrative pause/override и будет приведено daemon'ом к
требуемому значению на следующем завершённом цикле согласования.

### 2.4. Никакого скрытого fallback на старый конфиг

Конфигурация читается только при старте процесса.

Изменения применяются только через:

```bash
systemctl restart vpn-gateway.service
```

`reload-config` отсутствует.

После изменения файла допустимы только два состояния:

1. сервис успешно стартовал с новой конфигурацией;
2. сервис не стартовал и находится в `failed`.

Работа на старой конфигурации при уже изменённом файле не допускается.

### 2.5. Никаких сторонних Python-зависимостей

Python-реализация использует только:

- стандартную библиотеку Python;
- штатные системные утилиты Debian 13.

Запрещены:

- `pip`;
- PyPI;
- `apt install python3-*` ради дополнительных библиотек.

Python рассматривается как промежуточная реализация; архитектура должна оставаться пригодной для последующего переноса на Rust.


## 3. Процессная модель

Основной компонент:

```text
vpn-gatewayd
```

Это постоянно работающий процесс под управлением systemd.

Он:

- читает и валидирует конфигурацию;
- хранит разобранный конфиг в памяти;
- отслеживает состояние VPN-интерфейсов managed-профилей;
- применяет firewall;
- применяет blackhole;
- применяет VPN-маршруты;
- применяет NAT;
- управляет IPv4 forwarding;
- выполняет полную самоподчистку при старте и штатном завершении.

Отдельный событийный `vpn-monitor` после перехода на эту архитектуру не требуется.

Daemon пишет обычные текстовые логи в `stderr`; при запуске под systemd они захватываются journal. Structured logging/JSON не требуется.


## 4. Мониторинг VPN-интерфейса и runtime-привязка

Для мониторинга используется Linux Netlink через стандартный Python `socket`:

```text
AF_NETLINK
NETLINK_ROUTE
```

Сервис реагирует как минимум на:

- `RTM_NEWLINK`;
- `RTM_DELLINK`;
- `RTM_NEWADDR`;
- `RTM_DELADDR`.

При запуске daemon выполняет полный interface/address snapshot и не полагается только на
будущие события. При потере Netlink-событий, например `ENOBUFS`, выполняется полная
пересверка. Периодическое согласование остаётся страховкой от дрифта ресурсов и потерянных
событий.

### 4.1. Селектор интерфейса

Поле config `interface` является **селектором**, а не обязательно конкретным Linux netdev.

Поддерживаются две формы:

```text
wg0    -> точный селектор
vpns+  -> префиксный селектор
```

Завершающий `+` использует семантику сопоставления по префиксу, подтверждённую EXP-005
для входного interface operand `iptables -i prefix+`: `vpns+` означает всё пространство
имён интерфейсов с префиксом `vpns`, включая имя `vpns` без суффикса.

Это не shell glob и не пользовательский regex.

Селектор используется только для поиска и классификации runtime-интерфейсов. Строка
префиксного селектора с `+` **никогда** не передаётся в route, ACCEPT или NAT operations;
после разрешения селектора эти ресурсы используют только точное имя найденного интерфейса.

Daemon разрешает селектор по одному interface snapshot:

```text
0 совпадений  -> ABSENT (отсутствует)
1 совпадение  -> BOUND(name, ifindex), жесткая привязка
>1 совпадения -> AMBIGUOUS (неоднозначен)
```

Жесткая привязка содержит как минимум точное имя интерфейса и ifindex из snapshot. Ifindex
нужен для обнаружения удаления и повторного создания интерфейса под тем же именем;
route/iptables operations всё равно используют точное имя netdev.

Daemon никогда не выбирает «первый», «минимальный номер», «самый новый» или иной
произвольный интерфейс при неоднозначности.

### 4.2. Конфликты селекторов в конфигурации

Два одновременно управляемых селектора не могут иметь непустое множество общих возможных
runtime-имён интерфейсов.

Это ошибка конфигурации, блокирующая запуск.

Примеры конфликтов:

```text
vpns+ + vpns0
vpns+ + vpns1+
vpns+ + vpns+
```

Точные имена и сопоставление селектора чувствительны к регистру, как и Linux interface
names.

Для префиксного селектора префикс должен содержать хотя бы один допустимый символ Linux
interface name; завершающий `+` является оператором селектора и не входит в конкретное имя.

Неуправляемые definitions не блокируют runtime-запуск; соответствующие конфликты с
управляемыми профилями являются WARNING в `--check-config`, как и остальные
cross-conflicts неуправляемых definitions.

### 4.3. Критерий готовности VPN

Профиль считается готовым, если одновременно:

1. селектор разрешён ровно в один интерфейс;
2. это та же жесткая привязка `name + ifindex`, которая рассматривается в текущем цикле
   согласования;
3. на интерфейсе присутствует ожидаемый `local_address`.

Не используются как критерий готовности:

- `operstate`;
- `LOWER_UP`;
- доступность удалённого peer;
- ping;
- handshake VPN-протокола;
- фактическое прохождение трафика.

Если селектор не имеет совпадений либо найденный интерфейс существует без ожидаемого local
IPv4, профиль не готов. Его защищаемые маршруты остаются под blackhole и окончательным
FORWARD REJECT.

Если селектор находится в состоянии `AMBIGUOUS` (неоднозначен):

- при запуске это fatal runtime-environment conflict; сервис не включает forwarding;
- в RUN профиль переходит в FAIL/DEGRADED;
- правила allow/NAT/unicast, зависящие от привязки, должны быть удалены или не созданы;
- blackhole и запрещающая политика сохраняются.

### 4.4. Смена привязки и остаточное окно реакции

Появление, исчезновение, замена ifindex либо изменение числа совпадений селектора считается
событием смены привязки и инициирует полное сериализованное согласование.

При подтверждённой смене привязки daemon сначала best-effort отключает `ip_forward`,
затем применяет политику и маршруты для нового immutable snapshot привязки, проверяет
состояние и только после этого может вернуть forwarding.

Существует принципиальное окно реакции между событием ядра и обработкой Netlink-события
daemon. Особенно это заметно при быстром появлении второго подходящего интерфейса или при
удалении и повторном создании интерфейса под тем же именем: старые exact-name rules
физически существуют до реакции daemon.

Архитектура принимает это ограниченное окно реакции как неизбежную границу многозадачной ОС
на выделенном доверенном gateway host. Оно уменьшается пробуждением по Netlink и
периодической полной пересверкой, но не изображается как атомарная kernel transaction.

Граница модели угроз для этого окна явная:

- недоверенные локальные пользователи и процессы не имеют `CAP_NET_ADMIN` и не могут
  создавать, переименовывать или удалять network interfaces;
- жизненным циклом runtime-netdev управляют доверенное VPN software, kernel и administrator;
- ifindex позволяет обнаружить повторное создание интерфейса под тем же именем при следующем
  snapshot, но существующее iptables rule по имени нельзя задним числом привязать к старому
  ifindex.

При этом новые или ещё не привязанные интерфейсы префиксного семейства не должны иметь
статических разрешающих правил по шаблону. Для local INPUT заранее устанавливается
**защитное правило селектора только с запретом** `-i prefix+`; область его совпадения и
каноническое представление в `iptables-save` подтверждены EXP-005. Оно блокирует трафик
семейства селектора, если его не завершила более ранняя точная цепочка профиля, зависящая
от привязки. Сопоставление по префиксу никогда не используется для ACCEPT или NAT.

## 5. Жизненный цикл сервиса

### 5.1. Старт

Базовая модель:

```text
START
  ↓
LOCK
  ↓
CLEANUP
  ↓
LOAD + VALIDATE CONFIG
  ↓
APPLY
  ↓
RUN
```

Любая ошибка до `RUN` является фатальной.


### 5.2. Runtime directory и блокировка экземпляра

Default runtime directory:

```text
/run/vpn-gateway
```

Default lifetime lock:

```text
/run/vpn-gateway/vpn-gatewayd.lock
```

Перед открытием lock daemon безопасно ensure/validate runtime directory:

- final component не следует через symlink;
- существующий объект обязан быть directory;
- mode обязан быть `0700`;
- owner обязан совпадать с ожидаемой service identity текущего deployment;
- если каталог отсутствует и процесс имеет право его создать, он создаётся с `0700`;
- существующий неправильный owner/mode не исправляется молча через chmod/chown, а даёт fatal error.

Для текущего root foreground deployment expected owner — UID 0. Будущий systemd deployment
под отдельным service user использует owner этого service identity.

Lock-файл открывается с `O_NOFOLLOW`, mode `0600` и удерживает non-blocking exclusive
`flock` всё время жизни процесса. Busy lock диагностируется как отдельная ошибка
«another instance is running».

Отдельный configurable shared lock path не вводится без реального multi-instance use case.

### 5.3. Штатное завершение и сигналы

Signal handlers для `SIGTERM`/`SIGINT` устанавливаются **до первой startup phase**. Handler не выполняет kernel operations и только взводит shutdown flag.

Во время `STARTING` shutdown flag проверяется на границах фаз:

```text
install handlers
  ↓
LOCK
  ↓ checkpoint
CLEANUP
  ↓ checkpoint
LOAD + VALIDATE CONFIG
  ↓ checkpoint
APPLY
  ↓ checkpoint
RUN
```

Если сигнал пришёл до получения lifetime lock, процесс выходит без cleanup: он ещё не владеет gateway resources.

Если сигнал пришёл после lock:

- завершить текущую ограниченную по времени фазу;
- на ближайшей границе не начинать следующую;
- если завершённая фаза могла создать kernel-state (`APPLY`), выполнить universal `cleanup()`;
- если startup ещё не создавал kernel-state после уже успешного initial `cleanup()`, дополнительный cleanup не обязателен;
- выйти без перехода в `RUN`.

Критический checkpoint существует после успешного `APPLY` и **до** `READY=1`: сигнал в окне после `ip_forward=1` не должен оставлять daemon-owned forwarding без cleanup.

После входа в `RUN`:

```text
SIGTERM/SIGINT
 ↓
shutdown flag + wakeup serialized event loop
 ↓
CLEANUP
 ↓
EXIT
```

Для blocking selector/event-loop signal handler используется совместно с `signal.set_wakeup_fd()`/self-pipe-equivalent, чтобы graceful shutdown не ожидал periodic timeout.

`SIGHUP` игнорируется: config reload архитектурой отсутствует, журнал пишется в stderr/journal и reopen файлов по HUP не требуется.

Если финальный `cleanup()` не смог подтвердить полную очистку, процесс завершается с ошибкой.

Для systemd deployment preferred mode — `Type=notify` с `WatchdogSec`, если реализация поддерживает `sd_notify`. Это не меняет lifecycle semantics: watchdog лишь подтверждает живость serialized event loop; требования к heartbeat/deadline зафиксированы в §24.


### 5.4. Deployment/service recommendations

Рекомендуемый systemd deployment:

```text
RuntimeDirectory=vpn-gateway
RuntimeDirectoryMode=0700
Restart=on-failure
RestartSec=<bounded delay>
StartLimitIntervalSec=<bounded window>
StartLimitBurst=<bounded count>
ExecStopPost=<best-effort ip_forward=0 safety action>
```

`RuntimeDirectory` остаётся preferred deployment path и особенно важен при будущем
non-root service identity. Но корректность standalone daemon не зависит от systemd:
если процесс имеет право создать runtime directory, он делает это сам и затем применяет тот
же security validation.

`ExecStopPost` является вторичным fail-closed safety net на случай SIGKILL, watchdog timeout
или аварии процесса, когда Python cleanup физически не исполнился. Failure этого safety net
не заменяет daemon cleanup и не маскируется как успешная очистка.

Deployment не должен постоянно задавать `net.ipv4.ip_forward=1` через `sysctl.d`.
Runtime owner этого sysctl — vpn-gatewayd.

Другие firewall managers могут иметь свои INPUT/OUTPUT rules и физически сохраняемые
FORWARD rules, но пока daemon включает forwarding, его terminal FORWARD prefix имеет
приоритет. Конфигурация, в которой внешний сервис постоянно переписывает daemon-owned
`VPNG-*` namespace или его prefix jumps, unsupported.

Архитектура не требует `geteuid()==0`. Предпочтительно сохранить возможность отдельного
service user с минимальными capabilities/permissions, если live deployment подтвердит
достаточность. Config/path security contract остаётся root-controlled.


## 6. Универсальная очистка

`cleanup()` не зависит от текущего конфига и persistent runtime state. Он используется
перед загрузкой config при запуске, после аварийного предыдущего запуска и при штатном stop.

Успешная очистка означает отсутствие всех marker-owned ресурсов VPN Gateway и
`ip_forward=0`.

### 6.1. Ownership markers

Принятые маркеры:

```text
blackhole routes -> proto 201 + type BLACKHOLE + metric 65536
VPN routes       -> proto 202
iptables chains  -> reserved namespace VPNG-*
owned jumps      -> jumps с target VPNG-*
```

Префикс `VPNG-` целиком зарезервирован daemon'ом в используемых iptables tables.

### 6.2. Инвентаризация маршрутов для очистки

Не зависящая от конфигурации очистка **не читает полный main route snapshot**.

Для owned route discovery используются marker-selective queries:

```text
ip -j -N -4 route show table main proto 202
ip -j -N -4 route show table main proto 201
```

EXP-004.5 подтвердил, что такие selectors исключают unrelated foreign multipath state.

При protocol-filtered query iproute2 может не печатать поле `protocol`; adapter назначает
известный protocol из query context. Для `proto 201` cleanup дополнительно требует
`type=BLACKHOLE` и `metric=65536`.

Strict full-table `list_routes()` сохраняется для normal reconciliation и по-прежнему
ошибается на непредставимых multipath/nhid forms, а не silently omits их.

### 6.3. Порядок очистки

1. read-before-write привести `ip_forward` к 0 и подтвердить;
2. selective inventory + удалить `proto 202`;
3. inventory firewall/NAT и удалить daemon-owned jumps/chains exact cleanup payload'ом;
4. только после успешного firewall/NAT cleanup selective inventory + удалить owned
   `proto 201 type BLACKHOLE metric 65536`;
5. fresh selective route inventory и firewall inventory подтвердить полную чистоту.

EXP-004.4 подтвердил используемый per-table cleanup transaction pattern на Debian 13 /
iptables-nft 1.8.11: duplicate `-D`, затем `-F/-X`, один `COMMIT`. Failure удаления chain
не оставляет частично применённую table transaction на протестированном backend.

### 6.4. Результаты очистки

**SUCCESS**

- `ip_forward=0`;
- нет `proto 202`;
- нет owned `proto 201 BLACKHOLE metric 65536`;
- нет `VPNG-*` chains/jumps.

**FAILURE**

Полная очистка не подтверждена. Startup не продолжается. Blackhole не снимаются, если
очистка остальных owned resources не подтверждена.

### 6.5. Никаких слепых flush

Запрещено:

- flush всей routing table;
- flush всей `filter`/`nat` table;
- удалять чужие маршруты вне authoritative exact-route scope;
- удалять foreign firewall rules, не являющиеся marker-owned jump в `VPNG-*`.

Exact protected destination prefixes остаются отдельным authoritative routing scope normal
reconciliation; cleanup этим исключением не пользуется.

## 7. Load и validate

### 7.1. Runtime config projection

После успешного `cleanup()` daemon парсит TOML-документ и строит **runtime projection** только для `managed_vpns`.

На обычный startup влияют:

1. синтаксическая корректность TOML;
2. top-level runtime schema (`managed_vpns`, `common_allowed_sources`, `reconcile_interval`);
3. возможность однозначно разрешить каждую ссылку из `managed_vpns` к `[vpn.<profile>]`;
4. полная schema/value/semantic validation только выбранных managed definitions;
5. selection-dependent conflicts только внутри managed set.

Тела unmanaged `[vpn.*]` не создают runtime-state и **не валидируются по value/schema на обычном startup**. Ошибочный IP, отсутствующее поле, неизвестный profile-key или иной дефект unmanaged definition не должен остановить работающий gateway.

Это сознательно разделяет:

```text
TOML document + selection
        ↓
validated managed runtime projection
```

`VpnGatewayDaemon` получает только validated managed projection.

### 7.2. Offline lint: `--check-config`

`--check-config` дополнительно анализирует весь каталог definitions.

Для managed set он выдаёт те же `ERROR`, которые сделали бы startup невалидным.

Для unmanaged definitions и conflicts, возникающих только при их возможной будущей совместной активации, он выдаёт `WARNING`, например:

- malformed/invalid field value;
- missing/unknown profile field;
- invalid profile ID;
- interface conflict;
- route overlap;
- `routes` ↔ `vpn.network` overlap;
- case-insensitive ambiguous definitions;
- безвредные exact duplicates в set-like lists.

Наличие только `WARNING` не меняет exit code `0`.

`NOTE` используется для валидных, но operationally значимых состояний managed-конфига, которые полезно явно показать оператору. Текущий обязательный `NOTE` — managed profile с `peers=[]`. `NOTE` также не меняет exit code.

### 7.3. Validation scope: не накапливать проверки без причины

Новая runtime validation rule должна иметь явную цель:

1. runtime projection невозможно однозначно построить;
2. managed runtime state становится неоднозначным или небезопасным.

Потенциальная проблема только unmanaged definition — offline lint, а не startup error.

Безвредная избыточность set-like input не является fatal error и нормализуется (`managed_vpns`, exact duplicate routes одного managed-профиля, ACL duplicates).

`peers` — сознательное исключение внутри managed definition: порядок peers задаёт route metrics, поэтому duplicate не является просто set-like redundancy.

Отдельной фазы `preflight()` нет. Kernel-dependent safety checks входят в build/validate initial reconciliation plan. В частности, `_validate_plan()` запрещает удаление `proto kernel`; exact protected prefix, совпадающий с host connected `proto kernel` route, поэтому приводит к fatal startup error до route side effects.


## 8. Применение и runtime-согласование

Bootstrap и runtime используют одну policy (политику) и binding model (модель привязки), но
разную error semantics: при запуске действует жёсткий отказ; RUN способен переходить в
DEGRADED/ISOLATED. В плотных технических блоках этого раздела после первого употребления
сохраняются краткие формы binding (привязка), concrete binding (жесткая привязка),
reconciliation (согласование), materialize (применить) и verify (проверить).

### 8.1. Неизменяемый snapshot согласования

Каждый completed pass использует один daemon-level immutable snapshot, концептуально:

```text
ReconciliationSnapshot
    interfaces
    resolutions_by_profile
    readiness_by_profile
    desired_routes_by_profile
    desired_full_policy
```

Точное имя/type является implementation-level, но семантика обязательна: это одна
зафиксированная интерпретация одного fresh interface inventory + immutable config.

Selector каждого managed profile разрешается в:

```text
ABSENT
BOUND(name, ifindex)
AMBIGUOUS(matches...)
```

Readiness вычисляется поверх того же interface snapshot:

```text
ready = BOUND
        AND expected local_address присутствует на bound interface
```

Из config + этого immutable binding/readiness snapshot daemon один раз строит full desired
firewall/NAT policy и desired routes. Selector/readiness/DESIRED не пересчитываются между
build/apply/verify фазами pass.

Это **не** означает atomic kernel transaction между отдельными route/interface/firewall
syscalls. Snapshot гарантирует только внутреннюю консистентность orchestration pass.

### 8.2. Bootstrap apply

После успешного cleanup + config validation:

1. прочитать interface/address snapshot;
2. разрешить selectors и проверить runtime ambiguity;
3. startup ambiguity -> fatal до `ip_forward=1`;
4. построить desired firewall/NAT policy:
   - structural chains/jumps/guards;
   - binding-specific exact INPUT/FORWARD allow rules только для ready profiles;
   - binding-specific exact MASQUERADE только для ready profiles;
5. materialize filter, затем nat, atomic per table/COMMIT;
6. verify firewall/NAT относительно того же binding snapshot;
7. прочитать full strict route snapshot;
8. построить/validate desired route plan:
   - BLACKHOLE всегда;
   - UNICAST только для ready profile и только с exact bound interface name;
9. apply route plan; missing BLACKHOLE guards идут первой фазой;
10. fresh route verify относительно того же desired snapshot;
11. commit process-local OWNED routes и committed binding snapshot;
12. read-before-write включить `ip_forward=1` самым последним и подтвердить.

Если любой этап до последнего подтверждения неуспешен, startup fatal и forwarding не должен
оставаться включённым.

### 8.3. Desired routes

Blackhole RouteSpec выводится только из config:

```text
destination = profile.route
type        = BLACKHOLE
proto       = 201
metric      = 65536
interface   = None
```

UNICAST RouteSpec выводится из config **и concrete ready binding**:

```text
destination = profile.route
via         = peer
interface   = binding.name
proto       = 202
metric      = 10,20,30...
onlink      = true
```

Prefix selector никогда не попадает в RouteSpec.

### 8.4. Runtime-согласование

Runtime pass сериализован одним event loop и запускается по relevant Netlink event,
periodic tick, full resync или administrative trigger.

#### Interface inventory failure

Fresh interface inventory является policy-critical: без него daemon не может достоверно
вычислить binding-specific INPUT/FORWARD/NAT state.

Если interface inventory/read/parse/resolution не завершён:

1. best-effort привести `ip_forward=0`;
2. state = `ISOLATED`;
3. не выполнять blind repair binding-specific NAT/allow policy;
4. если firewall inventory читаем, daemon **может и должен предпочитать** безопасное
   config-only isolation filter (§8.6), не требующее concrete binding;
5. retry на следующем serialized reconciliation pass.

Такой failure не классифицируется как обычный route/profile `DEGRADED`.

#### Normal pass

После успешного interface inventory:

1. построить один immutable `ReconciliationSnapshot`;
2. сравнить current binding identity/cardinality с последним committed binding snapshot;
3. при binding transition best-effort привести `ip_forward=0`;
4. inventory current firewall/NAT;
5. если inventory/canonical interpretation `UNKNOWN`:
   - best-effort forwarding OFF;
   - `ISOLATED`;
   - blind repair не выполнять;
6. если current policy `UNSAFE` либо binding transition требует rematerialization:
   выполнить deny-first repair sequence (§8.6);
7. только после full desired firewall/NAT `SAFE` читать strict full route snapshot;
8. build/validate/apply/verify route plan из того же `ReconciliationSnapshot`;
9. commit OWNED + binding snapshot только после verify;
10. после completed SAFE policy + route pass привести exclusive-owned `ip_forward` к
    требуемому состоянию.

Binding transition, включая BOUND -> ABSENT, ABSENT -> BOUND, BOUND(name/ifindex A) ->
BOUND(name/ifindex B) и переход в/из AMBIGUOUS, считается policy transition.

### 8.5. Runtime ambiguity

Для AMBIGUOUS profile desired state является fail-closed:

- binding-specific INPUT allow отсутствует;
- binding-specific FORWARD allow отсутствует;
- binding-specific MASQUERADE отсутствует;
- proto-202 UNICAST отсутствуют;
- BLACKHOLE guards остаются;
- protected destinations продолжают получать terminal REJECT;
- selector INPUT guard остаётся.

После materialization/verify этого состояния daemon может снова включить global forwarding
для остальных profiles, но overall lifecycle state остаётся DEGRADED с profile FAIL до
устранения ambiguity.

### 8.6. Состояние безопасности firewall и восстановление с первоначальным запретом

Firewall/NAT state использует именованные состояния:

```text
SAFE     -> безопасно
UNSAFE   -> небезопасно
UNKNOWN  -> состояние неизвестно
```

Полное ожидаемое состояние зависит от immutable `ReconciliationSnapshot`.

Отдельно слой policy (политики) обязан уметь построить config-only **изолирующий фильтр**:

```text
desired_isolation_filter(config)
```

Он не содержит ACCEPT rules, зависящих от binding, и не требует interface inventory. Он
сохраняет только структурную политику фильтрации с отказом с запретом:

- защитные правила INPUT управляемых селекторов;
- rejects транспортных сетей VPN;
- безусловные rejects защищаемых назначений;
- окончательный `VPNG-FORWARD-DENY`;
- необходимые structural chains/jumps.

Состояние `UNKNOWN` никогда не восстанавливается вслепую. Daemon best-effort выключает
forwarding и остаётся ISOLATED.

Для подтверждённого `UNSAFE` либо смены binding применяется последовательность с
первоначальным запретом:

```text
1. best-effort ip_forward=0

2. применить изолирующий фильтр как полное daemon-owned filter desired state
   для этой промежуточной стадии; stale ACCEPT rules, зависящие от binding,
   должны быть удалены
3. проверить изолирующий фильтр
   - эта проверка подтверждает только защитный барьер
   - она НЕ означает full-policy SAFE

4. применить desired NAT для текущего immutable binding snapshot
5. проверить desired NAT

6. применить full desired filter с точными ACCEPT rules, зависящими от binding
7. проверить full desired filter
   - только после проверки NAT + full filter полное firewall/NAT state может быть SAFE

8. согласовать и проверить routes

9. только после полной успешной проверки:
       включить/подтвердить forwarding согласно требуемому состоянию
```

Этот порядок обязателен даже если `set_ip_forward(False)` завершился ошибкой. Благодаря
этому полный FORWARD ACCEPT не появляется раньше проверенного NAT.

Если изолирующий фильтр не удалось применить или проверить, daemon остаётся ISOLATED и не
переходит к NAT/full-filter/routes.

Простая глобальная перестановка `nat -> filter` запрещена: при уже небезопасном/open
filter она оставила бы разрешающий forwarding активным дольше. Защитным барьером является
именно фильтр с первоначальным запретом.

Если forwarding подтверждён OFF, реализация может оптимизировать технические детали
транзакций только при сохранении той же наблюдаемой семантики безопасности.

### 8.7. Route executor

Порядок route mutations сохраняется:

```text
1. missing BLACKHOLE adds
2. competing exact deletes
3. authoritative replaces
4. remaining adds
```

Route plan validation сохраняет authoritative exact-prefix semantics и запрет mutation
`proto kernel`.

### 8.8. OWNED и фиксация binding

Process-local OWNED routes и committed binding snapshot изменяются только после completed
verify соответствующего pass.

Bootstrap ordering остаётся:

```text
route/policy verify
-> commit process-local OWNED/binding
-> enable + confirm ip_forward
```

Commit после forwarding запрещён: неожиданная process-local commit ошибка не должна оставлять
failed apply при уже включённом forwarding.

### 8.9. Lifecycle state

```text
interface/policy observability insufficient -> ISOLATED
firewall != SAFE                            -> ISOLATED
firewall == SAFE
  AND all managed profiles SUCCESS
  AND ip_forward == 1                       -> ACTIVE
firewall == SAFE, остальные completed
profile/policy passes                        -> DEGRADED
```

ABSENT/not-ready профиль не является ошибкой сам по себе, если его blackhole/deny desired
state успешно materialized. AMBIGUOUS является profile FAIL.

`ACTIVE` означает, что **желаемое kernel policy-state полностью реализовано**, а не что VPN
peer/tunnel connectivity доказана. Поэтому operational status обязан отдельно показывать
для каждого profile selector, binding, readiness и route result.

Ручной `sysctl -w net.ipv4.ip_forward=0` не является administrative pause; clean completed
pass восстанавливает exclusive-owned value.


## 9. Firewall и blackhole

В этом разделе guard (защитное правило) и ingress (входящий трафик) после первого
употребления могут сохраняться в английской краткой форме внутри описаний iptables.

Daemon-owned filter policy состоит из structural и binding-specific частей.

Structural часть существует для всех managed profiles независимо от readiness:

- reserved `VPNG-*` chains;
- deterministic built-in jump prefix;
- `VPNG-RESERVED`;
- profile protected-destination terminal rejects;
- `VPNG-INPUT-GUARD`;
- `VPNG-FORWARD-DENY`.

Binding-specific часть строится только из exact concrete ready interfaces.

### 9.1. Built-in jump layout

`INPUT`:

```text
1..N   -> VPNG-<PROFILE>-INPUT, sorted profile ID
N+1    -> VPNG-INPUT-GUARD
далее  -> foreign INPUT rules
```

`FORWARD`:

```text
1      -> VPNG-INGRESS
2      -> VPNG-RESERVED
3..    -> VPNG-<PROFILE>-FORWARD, sorted profile ID
last   -> VPNG-FORWARD-DENY
далее  -> foreign FORWARD rules, физически сохранённые, но недостижимые при ip_forward=1
```

`POSTROUTING`:

```text
1..N   -> VPNG-<PROFILE>-NAT
далее  -> foreign rules
```

Каждый daemon jump существует ровно один раз и использует plain `-j`.

### 9.2. INPUT semantics

Profile INPUT chain содержит exact binding-specific rules только когда profile ready:

```text
-i concrete
ctstate INVALID
    DROP

-i concrete
ctstate ESTABLISHED,RELATED
    ACCEPT

-i concrete
-s profile.network
-d profile.local_address
ctstate NEW
    ACCEPT

-i concrete
    REJECT --reject-with icmp-host-prohibited

RETURN
```

Если profile not ready/ambiguous, exact allow/reject block отсутствует и chain возвращает.

После profile chains `VPNG-INPUT-GUARD` fail-closed блокирует traffic от всех configured
managed interface selectors, не завершённый более ранней exact profile chain.

Для exact selector guard использует exact ifname. Для prefix-family selector guard
использует тот же deny-only `-i prefix+` contract, что подтверждён EXP-005.
Wildcard/prefix matching никогда не используется для ACCEPT или NAT.

Traffic, не относящийся ни к одному managed selector, после daemon INPUT prefix продолжает
обрабатываться базовым host firewall.

### 9.3. FORWARD semantics

`VPNG-INGRESS` для каждого **ready concrete binding**:

```text
-i concrete
ctstate INVALID
    DROP

-i concrete
ctstate ESTABLISHED,RELATED
    ACCEPT

-i concrete
    REJECT --reject-with icmp-host-prohibited

RETURN
```

Unbound/new selector-family ingress, не совпавший с exact block, всё равно не может
провалиться в foreign FORWARD: его завершит `VPNG-FORWARD-DENY`.

`VPNG-RESERVED` всегда REJECT'ит destination в любой managed `vpn.network`.

Profile FORWARD chain для каждого protected destination:

```text
если profile ready:
    -d route -o concrete ctstate INVALID
        DROP

    для каждого effective_source:
        -s source -d route -o concrete
            ACCEPT

всегда:
    -d route
        REJECT --reject-with icmp-host-prohibited

RETURN
```

То есть protected destination terminally closed даже когда profile absent/ambiguous.

После всех profile chains `VPNG-FORWARD-DENY` делает complete global forwarding ownership:

```text
ctstate INVALID
    DROP

everything else
    REJECT --reject-with icmp-host-prohibited
```

Ни один forwarded IPv4 packet при daemon-owned `ip_forward=1` не достигает foreign
FORWARD rules или built-in policy.

### 9.4. Fail2ban

Fail2ban может существовать как отдельный более ранний nftables INPUT hook. Он не участвует
в FORWARD policy и не меняет deterministic layout VPNG jumps внутри iptables INPUT.

### 9.5. Blackhole

Blackhole устанавливаются для всех protected routes managed profiles:

```text
proto 201
metric 65536
type blackhole
```

Blackhole не зависит от binding/readiness.

EXP-004.2 подтвердил: при исчезновении interface-dependent `proto 202` unicast blackhole
остаётся и не даёт protected destination уйти через default route.

Blackhole не заменяет firewall: complete FORWARD policy остаётся независимым fail-closed
слоем.

## 10. VPN-маршруты

Все VPN-маршруты, создаваемые сервисом, должны иметь:

```text
proto 202
```

Это обязательный ownership marker.

Он позволяет `cleanup()` обнаруживать VPN-маршруты после:

- `kill -9`;
- OOM;
- аварийного завершения процесса;
- изменения конфигурации между запусками.

Cleanup удаляет только маршруты `proto 202`, принадлежащие сервису.


## 11. NAT

В этом разделе egress (исходящий трафик / выходной интерфейс) может сохраняться как
краткий технический термин внутри описаний правил.

Для каждого managed profile существует structural chain:

```text
VPNG-<PROFILE>-NAT
```

и deterministic `POSTROUTING` jump к ней.

MASQUERADE больше не является static config-only rule.

Если profile ready и имеет exact concrete binding, desired chain:

```text
-o <concrete-interface>
-m addrtype ! --src-type LOCAL
-j MASQUERADE

RETURN
```

Если profile absent/not-ready/ambiguous:

```text
RETURN
```

Prefix selector string никогда не используется как NAT interface operand.

При binding transition daemon отключает forwarding до rematerialization/verify binding-specific
filter/NAT policy. NAT должен быть verified до добавления/восстановления proto-202 routes
через новый concrete interface.

Это возвращает safety dependency:

```text
binding resolved
-> filter/NAT exact policy materialized + verified
-> route materialization
-> forwarding enabled/restored
```

Foreign route через managed concrete interface не даёт обход daemon policy, потому что
complete FORWARD ownership допускает egress только explicit profile ACCEPT.

### 11.1. Event gap

Старая static NAT model имела красивое свойство «rule уже существует до появления
interface». Для prefix-family selector это невозможно без permissive wildcard, который
архитектура запрещает.

Поэтому binding-specific NAT следует за discovery concrete interface.

Между kernel event и reconciliation существует bounded reaction window (§4.4). До
reconciliation новый interface не получает profile proto-202 route или exact FORWARD allow;
blackhole + terminal FORWARD deny предотвращают managed transit через него.

Быстрый reuse прежнего exact ifname является residual trusted-host race и должен быть
обнаружен через ifindex change на ближайшем Netlink/full-resync pass.

## 12. Конфигурация

Конфигурационный файл по умолчанию:

```text
/etc/vpn-gateway/vpn-gateway.toml
```


Формат конфигурации — TOML.

Конфигурационный файл должен принадлежать `root` и не быть writable для group/other. Нарушение этого требования является фатальной ошибкой и проверяется как при обычном старте, так и в `--check-config`.

Final path component config-файла должен быть **обычным regular file, не symlink**. Проверка выполняется через `lstat` до чтения. Причина та же, что у проверки parent directory: защищённый symlink внутри `/etc/vpn-gateway` мог бы указывать на target, чей содержащий каталог имеет иные права replacement/rename и тем самым обходить intended path-security model.

Родительский каталог `/etc/vpn-gateway` также должен принадлежать `root` и не быть writable для group/other. Проверка каталога обязательна, потому что writable directory позволил бы подменить защищённый config file через atomic rename.

Причины выбора TOML:

- есть штатный `tomllib` в Python 3.13;
- нет исполняемого shell-конфига;
- есть нормальные массивы и таблицы;
- формат пригоден для будущей Rust-реализации.

Пример:

```toml
reconcile_interval = 10.0

managed_vpns = [
    "primary",
    "backup",
]

common_allowed_sources = [
    "10.200.200.8",
    "10.200.200.9",
]

[vpn.primary]
interface = "vpns+"
network = "172.20.130.0/29"
local_address = "172.20.130.1"
peers = [
    "172.20.130.6",
]
routes = [
    "10.0.0.0/8",
]
allowed_sources = [
    "10.200.201.0/24",
]

[vpn.backup]
interface = "wg0"
network = "172.20.126.0/29"
local_address = "172.20.126.1"
peers = [
    "172.20.126.2",
]
routes = [
    "100.64.0.0/10",
    "192.168.0.0/16",
]
allowed_sources = []
```

Каждый `[vpn.<profile>]` является **definition** VPN-профиля. Наличие definition само по себе не создаёт runtime resources.

Top-level `managed_vpns` выбирает definitions, которыми daemon управляет в текущем запуске. Профиль, отсутствующий в `managed_vpns`, является unmanaged: daemon не отслеживает его interface и не создаёт для него firewall/routes/blackhole.

`managed_vpns` имеет set-семантику; порядок элементов не задаёт priority. Ссылки разрешаются case-insensitive к уникальным profile IDs и нормализуются к spelling definition.

Если case-insensitive одинаковые `[vpn.*]` definitions существуют только среди unmanaged entries, обычный startup их не валидирует; `--check-config` выдаёт WARNING. Если ссылка из `managed_vpns` разрешается неоднозначно, runtime projection построить нельзя — это fatal startup ERROR.

## 13. Закрытая схема конфигурации

Неизвестные ключи и секции являются фатальной ошибкой.

Базовая схема:

```text
reconcile_interval          float, optional, default 10.0, range [1.0, 60.0]
managed_vpns                 array[string], required, non-empty selection
common_allowed_sources       array[string], required

[vpn.<profile>]              profile definition sections
interface                    string selector, required
network                      string, required
local_address                string, required
peers                        array[string], required
routes                       array[string], required
allowed_sources              array[string], required
```

Profile-field schema выше является обязательным runtime contract для definitions, выбранных в `managed_vpns`. Для unmanaged sections этот же contract используется только `--check-config` linter'ом и не блокирует ordinary startup.

`reconcile_interval` — optional top-level поле. `managed_vpns` и `common_allowed_sources` обязательны. Полная profile schema/value validation применяется только к definitions, выбранным в `managed_vpns`; unmanaged profile bodies являются offline-lint input.

Имя `<profile>` является административным идентификатором VPN-профиля и не имеет протокольной семантики для `vpn-gatewayd`.

Допустимый формат имени профиля:

```text
[A-Za-z][A-Za-z0-9_-]{0,14}
```

То есть имя:

- имеет длину 1..15 символов;
- начинается с ASCII-буквы;
- далее содержит только ASCII-буквы, цифры, `_` и `-`;
- не содержит пробелов, точек, `/`, `@`, `*` и иной TOML-экзотики.

Количество VPN-профилей произвольно. Сервис не содержит whitelist известных VPN-протоколов и не интерпретирует имена профилей как `OpenConnect`, `WireGuard`, `OpenVPN`, `L2TP` и т. п.

Имена профилей уникальны case-insensitive: например, `primary` и `PRIMARY` одновременно запрещены.

`managed_vpns`:

- должен после нормализации содержать хотя бы один profile ID;
- каждая ссылка обязана разрешаться к существующему `[vpn.<profile>]`;
- порядок не имеет семантики;
- точные/case-insensitive дубли не меняют selection, нормализуются runtime без ошибки; `--check-config` выдаёт lint warning.

Kernel-chain names строятся детерминированно из uppercase profile ID:

```text
VPNG-<PROFILE>-INPUT
VPNG-<PROFILE>-FORWARD
VPNG-<PROFILE>-NAT
```

Ограничение имени профиля в 15 символов выведено из проверенного ограничения `iptables-nft`: chain name должен быть короче 29 символов. Самая длинная форма `VPNG-<PROFILE>-FORWARD` при profile ID длиной 15 имеет длину 28 символов.

Неизвестные ключи внутри каждого `[vpn.<profile>]` являются фатальной ошибкой.

При разборе TOML различаются:

- `[vpn."foo.bar"]` — профиль с недопустимым именем; ошибка формата имени профиля;
- `[vpn.foo.bar]` — неожиданная вложенная структура; ошибка схемы конфигурации.

## 14. Пустые списки и количество профилей

Принято для managed runtime set:

```text
managed_vpns = []               -> запрещено
managed profile.routes = []     -> запрещено
common_allowed_sources = []     -> разрешено
profile.allowed_sources = []    -> разрешено
peers = []                      -> разрешено
```

Отдельная проверка `profiles total count > 0` не нужна: non-empty `managed_vpns` уже требует существования хотя бы одной definition.


## 15. Селекторы интерфейсов

Поле `interface` runtime-валидируется только для управляемых definitions;
`--check-config` проверяет также неуправляемые definitions.

### 15.1. Точный селектор

Разрешено:

```text
1..15 символов
первый символ: ASCII-буква
остальные: ASCII-буквы, цифры, _, ., -
```

Regex:

```text
[A-Za-z][A-Za-z0-9_.-]{0,14}
```

Символ `+` целиком зарезервирован грамматикой селектора для префиксной формы и поэтому
не поддерживается в точном селекторе ни в какой позиции.

Для завершающего `+` есть и прямое техническое основание: vpn-gateway использует iptables,
а iptables трактует завершающий `+` в interface operand как сопоставление по префиксу, а
не как буквальное точное имя.

Запрещённые точные имена без учёта регистра:

```text
lo
any
default
all
```

### 15.2. Префиксный селектор

Форма:

```text
<prefix>+
```

Префикс соответствует тем же допустимым символам точного имени, начинается с ASCII-буквы и
имеет длину 1..14. Завершающий `+` является оператором селектора и не входит в конкретное
имя интерфейса.

Семантика:

```text
prefix+ -> все имена интерфейсов, начинающиеся с prefix,
           включая bare name prefix
```

Эта семантика намеренно совпадает с проверенным на целевой системе
`iptables -i prefix+`.

`+` разрешён только один раз и только последним символом селектора.

Literal exact interface name, содержащее `+`, vpn-gateway не поддерживает. Это проектное
ограничение следует из выбранной грамматики; для trailing `+` дополнительно действует
прямое ограничение iptables: такой operand означает сопоставление по префиксу, а не exact
match.

Префиксный селектор резервирует на выделенном gateway **всё текстовое пространство имён
интерфейсов с данным префиксом** для одного управляемого профиля. Любой посторонний
интерфейс внутри этого пространства участвует в подсчёте совпадений и может намеренно
перевести профиль в состояние AMBIGUOUS с отказом с запретом.

### 15.3. Взаимная исключительность управляемых селекторов

Управляемые селекторы должны быть попарно непересекающимися по множеству возможных
конкретных имён.

Проверяется не только строковое равенство.

Примеры фатальных конфликтов:

```text
vpns+ + vpns0
vpns+ + vpns1+
vpns+ + vpns+
```

Для префиксных семейств наложение означает пересечение текстовых пространств имён.
Например:

```text
vpns+   + vpns1+   -> overlap
vpns1+  + vpns12+  -> overlap
vpns1+  + vpns2+   -> disjoint
```

Если один селектор когда-либо может классифицировать тот же конкретный Linux interface, что
и другой управляемый селектор, runtime projection недопустима.

Администратор обязан использовать разные пространства имён интерфейсов для разных
управляемых VPN instances и не создавать посторонние netdevs внутри зарезервированного
пространства имён префикса.

## 16. VPN-сети и адреса

IPv4/CIDR и внутренние address/peer contracts проверяются runtime только для managed definitions. `--check-config` lint'ит те же contracts для unmanaged definitions как WARNING. Selection-dependent conflicts fatal только внутри managed set.

Для каждого VPN-профиля:

- `interface` selectors обязаны быть pairwise disjoint среди managed-профилей; overlap с unmanaged definition не влияет на startup и является lint warning в `--check-config`;
- `network` — канонический IPv4 CIDR;
- `/32` для `network` запрещён: VPN-сеть должна содержать как минимум две точки;
- минимально допустимая сеть — `/31`;
- `local_address` — IPv4 внутри `network`;
- каждый `peer` — IPv4 внутри `network`;
- `peer` не может совпадать с `local_address`;
- peers внутри managed-профиля не дублируются: `peers` order-significant и duplicate меняет route-priority model; unmanaged duplicate анализируется только `--check-config` и даёт WARNING;
- порядок `peers` значим и однозначно задаёт приоритет маршрутов;
- `peers = []` разрешён и означает лишь отсутствие обслуживаемых peer-адресов в конфигурации.

Для managed-профиля `--check-config` при `peers=[]` выводит информационный `NOTE`: UNICAST VPN routes не будут созданы, protected routes останутся под BLACKHOLE. Это не `WARNING` и не ошибка.

Если `peers = []` у managed-профиля, конфигурация остаётся валидной: profile VPN UNICAST
routes не устанавливаются, а защищаемые `routes` остаются под blackhole. Binding-specific
MASQUERADE существует только если profile ready и имеет concrete binding; сам `peers=[]`
на NAT readiness не влияет.

Network address и broadcast address не считаются запрещёнными адресами внутри VPN-сети. Для tunnel/point-to-point семантики нижний и верхний адрес диапазона могут использоваться как обычные адреса `local_address` или `peer`.

Поэтому валидатор не должен навязывать Ethernet-семантику network/broadcast address и не должен применять отдельные запреты к `/31`, кроме общих правил членства в сети и `peer != local_address`.

`vpn.network` является **transport network** профиля: она предназначена только для local/peer tunnel addresses и не входит в remote protected address space.

Для managed runtime set любое пересечение `profile.routes` любого managed-профиля с `vpn.network` любого managed-профиля является fatal config error. Проверяются exact match, containment в обе стороны и частичное overlap.

Для conflicts, где хотя бы одна сторона относится к unmanaged definition, обычный startup их не анализирует; `--check-config` выдаёт lint warning о том, что соответствующий набор definitions нельзя одновременно добавить в `managed_vpns`.

Секции `[vpn.<profile>]` являются независимыми описаниями способов добраться до удалённой стороны, возможно, одной и той же.

Поэтому одинаковые peer-адреса в разных VPN-профилях разрешены и ожидаемы.

## 17. ACL источников

ACL имеет два уровня:

```text
common_allowed_sources
vpn.<profile>.allowed_sources
```

Оба списка разрешают:

- одиночный IPv4;
- IPv4 CIDR.

Одиночный адрес внутри модели нормализуется в `/32`.

CIDR должен быть каноническим network prefix. Неканонический CIDR, например `10.200.200.8/24`, является ошибкой и не нормализуется молча в более широкую сеть.

Списки ACL имеют set-семантику: точные дубликаты после нормализации удаляются. `--check-config` сообщает их как lint warning; runtime error не требуется, потому что policy от дубликата не меняется.

Пересечения разрешены. Например, допустимо одновременно иметь:

```text
10.200.200.8/32
10.200.200.9/32
10.200.200.0/24
```

Эффективный ACL конкретного VPN-профиля:

```text
effective_allowed_sources(profile)
    = common_allowed_sources
      ∪ profile.allowed_sources
```

Профильный ACL только расширяет общий. Отрицательных правил, исключений и deny-семантики нет.

Эта семантика намеренно отличается от `routes`: ACL является набором разрешающих predicates, а не описанием маршрутного пространства.

## 18. routes

`routes` принадлежит конкретному VPN-профилю и описывает защищаемые сети, направляемые через его интерфейс.

Правила для managed runtime set:

- только IPv4 CIDR;
- только канонические network prefixes;
- `0.0.0.0/0` запрещён;
- `routes = []` для managed-профиля запрещён;
- `routes` имеет set-семантику и не задаёт priority: exact duplicates внутри одного профиля нормализуются, `--check-config` выдаёт lint warning;
- любые **нетождественные** пересечения/вложения routes внутри одного managed-профиля или между managed-профилями запрещены;
- exact один и тот же protected prefix в разных managed-профилях запрещён как ownership conflict;
- любое пересечение managed `routes` с любой managed `vpn.network` запрещено (§16).

Конфликты routes, где хотя бы один профиль unmanaged, обычным startup не анализируются и выдаются только `--check-config` как lint warnings о потенциальной несовместимости при будущем выборе `managed_vpns`.

Например, недопустимо:

```text
primary:   10.0.0.0/8
backup:    10.20.0.0/16
```

и также:

```text
primary:   10.0.0.0/8
backup:    10.0.0.0/8
```

Хотя Linux routing умеет longest-prefix match, проект намеренно требует непересекающегося защищаемого маршрутного пространства.

Каждый managed защищаемый prefix принадлежит ровно одному managed VPN-профилю.

Для каждого `profile.route` создаётся фиксированный набор маршрутов через все peers профиля:

```text
peer[0] -> metric 10
peer[1] -> metric 20
peer[2] -> metric 30
...
```

Порядок peers в TOML тем самым определяет приоритет одновременно доступных путей. `vpn-gatewayd` не отслеживает доступность peer и не меняет метрики динамически.
Валидатор проверяет, что вычисленная metric `(index + 1) * 10` представима допустимым типом route metric. Искусственный лимит числа peers не вводится.

## 19. Состояние VPN и сетевых правил

Structural deny policy и blackhole не зависят от VPN connectivity.

Binding-specific resources зависят только от resolved concrete interface + expected local IPv4,
а не от handshake/peer reachability:

- exact INPUT/FORWARD allow rules;
- exact MASQUERADE;
- proto-202 UNICAST routes.

Временная недоступность удалённой стороны при сохранении того же ready concrete binding не
должна вызывать churn firewall/NAT/routes.

Исчезновение/recreate concrete interface, изменение ifindex, изменение local IPv4 либо
selector cardinality является binding/readiness transition и инициирует reconciliation.

При not-ready/ambiguous состоянии остаются structural deny policy + blackhole, а
binding-specific allow/NAT/unicast state отсутствует.

## 20. Проверка конфигурации без запуска

Сервис обязан поддерживать режим:

```bash
vpn-gatewayd --check-config
```

Он:

- читает TOML;
- проверяет права и владельца конфигурационного файла;
- проверяет закрытую схему;
- выполняет ту же runtime validation для `managed_vpns`;
- отдельно lint'ит schema/value/semantic correctness unmanaged definitions и их потенциальные cross-conflicts;
- агрегирует доступные `ERROR`, `WARNING` и `NOTE` за один прогон;
- не берёт runtime lock;
- не изменяет routes;
- не изменяет iptables;
- не изменяет `ip_forward`;
- не выполняет `cleanup()`;
- завершает работу с `0`, если нет `ERROR`; наличие только `WARNING` не меняет exit code. При `ERROR` код ненулевой.

`--check-config` читает файл без синхронизации с работающим сервисом. Для консистентного административного обновления конфигурация должна публиковаться атомарной заменой готового файла (`rename`/`mv` из временного файла).

Рекомендуемый административный workflow:

```bash
vpn-gatewayd --check-config &&
systemctl restart vpn-gateway.service
```

Настоящий старт сервиса всё равно повторно валидирует конфигурацию.

CLI поддерживает:

```text
--config PATH
```

По умолчанию используется `/etc/vpn-gateway/vpn-gateway.toml`.

`--check-config` проверяет выбранный config path и не затрагивает kernel-state.

## 21. Административный интерфейс

Отдельный IPC может использоваться для простых локальных административных команд, например:

```text
status
shutdown
```

`reload-config` отсутствует по архитектурному решению.

IPC не должен позволять клиенту напрямую изменять kernel-state; команды исполняет сам `vpn-gatewayd`.

## 22. Что сознательно исключено

На текущем этапе не реализуются:

- automatic failover между VPN-профилями;
- live reload конфигурации;
- rollback на старую конфигурацию;
- runtime snapshot конфигурации;
- persistent runtime-state как источник истины;
- проверка VPN peer через ping;
- проверка WireGuard handshake;
- IPv6 forwarding;
- сторонние Python-библиотеки.

Неперсистентный runtime inventory (`OWNED`) не относится ни к persistent runtime-state, ни к runtime snapshot конфигурации.


## 23. Внутренняя модель реализации

Python-реализация больше не обязана помещаться в один source file.

Допустим и предпочтителен небольшой package/directory, если это улучшает аудит и снижает
связность кода. Deployment при этом имеет один daemon entry point, например:

```text
vpn-gatewayd
vpn_gateway/
    config.py
    model.py
    kernel.py
    policy.py
    daemon.py
```

Точные имена/разбиение не являются архитектурным API. Не следует дробить код на
микромодули без смысловой границы.

Будущая Rust-реализация по-прежнему ориентируется на единый исполняемый binary. Поэтому
domain boundaries должны естественно переноситься в Rust `struct`/`enum`/modules и не
зависеть от dynamic monkey-patching или Python-specific metaprogramming.

### 23.1. Config/domain model

Immutable runtime config содержит только managed typed profiles.

Поле TOML `interface` разбирается в typed selector:

```text
InterfaceSelector:
    EXACT(name)
    PREFIX_FAMILY(prefix)
```

Raw selector string `vpns+` не должен распространяться дальше config/domain boundary как
allow/NAT/route operand; после resolution kernel resources используют concrete exact name.

Interface inventory представлен typed snapshot, содержащим как минимум:

```text
InterfaceRecord:
    name: str
    ifindex: int
    ipv4: frozenset[IPv4Address]
```

Если один inventory payload содержит одно имя с несовместимыми ifindex identities, adapter
не merge'ит их молча и возвращает `KernelError`.

Resolution одного profile selector даёт:

```text
InterfaceResolution:
    ABSENT
    BOUND(name, ifindex)
    AMBIGUOUS(matches...)
```

Readiness вычисляет daemon из resolution + expected local IPv4.

`VpnProfile` хранит immutable config и process-local OWNED routes. Он не выполняет
kernel reads/writes и не выбирает runtime interface.

Старая идея `CONFIGURED routes` как полного набора готовых `RouteSpec` больше не
является корректной: BLACKHOLE config-only, но UNICAST требует concrete binding.

Daemon создаёт один immutable pass-level `ReconciliationSnapshot`, который содержит как
минимум interface inventory, resolutions/readiness, desired routes и full desired policy.
Он строится один раз и переиспользуется всеми build/apply/verify фазами pass.

### 23.2. Route model

`RouteSpec` остаётся self-contained immutable value object:

```python
@dataclass(slots=True, frozen=True)
class RouteSpec:
    destination: IPv4Network
    route_type: RouteType
    via: IPv4Address | None
    interface: str | None
    metric: int | None
    proto: int | None
    onlink: bool
```

Для BLACKHOLE `interface=None`.

Для UNICAST `interface` всегда exact concrete runtime name. Selector sentinel в RouteSpec
запрещён.

Daemon-level plan:

```text
route_adds
route_deletes
route_replaces
```

сохраняет существующую authoritative exact-prefix semantics.

### 23.3. OWNED runtime state

Process-local runtime state daemon/profile хранит:

- confirmed OWNED routes;
- последний committed concrete binding snapshot;
- diagnostic overlap cache.

Binding snapshot не является persistent state и не считается kernel truth. Каждый pass
получает fresh interface inventory.

OWNED routes и binding commit'ятся только после успешного verify соответствующего desired
snapshot.

### 23.4. Kernel boundary

`KernelInterface` остаётся thin physical boundary и не принимает policy decisions.

Normal reconciliation:

```text
list_routes() -> strict full main IPv4 snapshot
list_interfaces() -> interface records including name/ifindex/IPv4
add_route(RouteSpec)
delete_route(RouteSpec)
replace_route(RouteSpec)
read/write ip_forward
iptables-save / iptables-restore
```

Cleanup дополнительно использует marker-selective route inventory:

```text
list_routes_by_proto(201)
list_routes_by_proto(202)
```

Точное имя метода implementation-level; semantic contract — filtered query не парсит unrelated
foreign routes.

Debian subprocess adapter использует:

```text
ip -j -N -4 route show table main
ip -j addr show
ip -j -N -4 route show table main proto <N>
```

Full route inventory по-прежнему reject'ит непредставимые multipath/nexthop/nhid forms.

Filtered cleanup inventory получает protocol identity из query context, потому что iproute2
может не печатать `protocol` в selected output.

Protocol-selective inventory остаётся strict **внутри reserved marker namespace**:
непредставимый `proto 201/202` multipath/nhid/structured route не пропускается молча и
является cleanup failure. Для `proto 201` owned cleanup resource обязан дополнительно
соответствовать `type=BLACKHOLE metric=65536`; иная форма с reserved proto 201 является
marker conflict, а не кандидатом на silent delete.

Address/interface parser учитывает только `addr_info[].family == "inet"` и поле
`local`; ifindex сохраняется в InterfaceRecord. Duplicate records одного имени могут
объединяться только при согласованном ifindex identity.

### 23.5. Модель политики firewall

Слой policy строит из immutable config + snapshot текущего цикла две явные формы:

```text
desired_full_policy(snapshot)
desired_isolation_filter(config)
```

Точные имена функций и классов относятся к уровню реализации.

Полная политика содержит structural resources и точные rules, зависящие от binding.

Изолирующий фильтр:

- не зависит от interface inventory;
- не содержит ACCEPT, зависящих от binding;
- не содержит разрешающего сопоставления по префиксу;
- сохраняет защитные правила INPUT селекторов, rejects транспортных сетей VPN,
  rejects защищаемых назначений и окончательный FORWARD deny.

При применении изолирующий фильтр является **полным daemon-owned filter desired state** для
этой промежуточной стадии. Он не добавляется поверх текущего filter: stale daemon ACCEPT
rules, которых нет в desired state изолирующей стадии, должны быть удалены или заменены в
той же операции применения.

Успешная проверка изолирующего фильтра означает только:

```text
isolation filter verified
```

и **никогда не эквивалентна**:

```text
full desired firewall/NAT SAFE
```

Только full desired firewall/NAT SAFE после проверки desired NAT и full filter может открыть
путь к завершению согласования маршрутов и последующему включению forwarding.

Обе формы выводятся из одной модели policy, чтобы compare/restore не имели независимых
источников истины. Оркестрация восстановления с первоначальным запретом не выполняет
ad-hoc surgery над отдельными rules.

Префиксный селектор никогда не применяется в allow/NAT rule; там используется только точное
имя жесткой привязки.

Защитное правило INPUT селектора только с запретом является отдельным structural safety
mechanism.

### 23.6. Routing ownership policy

Daemon authoritative только для exact protected destination prefixes managed profiles.

Для каждого exact protected prefix:

```text
desired owned RouteSpec               -> keep
owned non-desired                     -> delete
foreign non-desired exact route       -> delete
exact desired but not OWNED           -> replace/canonicalize, then verify
configured blackhole guard            -> always desired
```

`proto kernel` никогда не delete/replace. Exact protected prefix, совпавший с connected
kernel route, fatal на startup.

More-specific/less-specific overlaps автоматически не удаляются и остаются diagnostic.

Fail-closed теперь обеспечивается тремя независимыми слоями:

1. BLACKHOLE для protected prefix;
2. unconditional protected-destination REJECT внутри profile FORWARD chain;
3. global terminal `VPNG-FORWARD-DENY`.

### 23.7. Цикл обработки событий

Один `VpnGatewayDaemon` владеет:

- одним Netlink listener;
- periodic reconciliation timer;
- signal wakeup;
- IPC/admin events.

Все события сериализованы. Одновременно выполняется не более одного reconciliation pass.

Netlink event используется как wakeup/dirty signal, а не как authoritative delta state:
reconciliation читает fresh full interface snapshot.

Unknown interface events могут быть проигнорированы только если имя не может соответствовать
ни одному managed selector. Событие имени, которое **может** match managed selector, должно
инициировать resync даже если concrete binding ещё не известен.


## 24. Замечания по реализации, уже зафиксированные архитектурой

- EXP-001 подтвердил canonical `iptables-save` representation для tested Debian 13 /
  iptables-nft backend; daemon использует minimal structural parser + canonical rule strings.
- Firewall apply/repair/cleanup использует memory-only `iptables-save` stdout и
  `iptables-restore --noflush` stdin; temporary rules files не нужны.
- EXP-002/002A подтвердили `ip -j addr show`, `addr_info[].local`, numeric route types и
  сохранение addressless interfaces.
- EXP-003 подтвердил bootstrap happy path RC2.5.1.
- EXP-004.1 подтвердил необходимость complete IPv4 FORWARD ownership.
- EXP-004.2 подтвердил fail-closed coexistence `proto 201` blackhole +
  preferred `proto 202` unicast и отсутствие default fallback после VPN loss.
- EXP-004.3 подтвердил, что ocserv создаёт runtime interface family, а не гарантированный
  exact ifname.
- EXP-005 подтвердил target iptables prefix contract: `-i vpns+` принимается и
  канонически сохраняется как `-i vpns+`; он матчится на `vpns`, `vpns0`, `vpns1`,
  `vpnsX`, но не на `other0`; более ранний exact `-i vpns0` ACCEPT обходит последующий
  deny-only `-i vpns+` guard.
- Поэтому config prefix selector использует тот же trailing `+` contract; kernel
  allow/NAT/routes используют только concrete resolved exact name.
- EXP-004.4 подтвердил per-table cleanup transaction `-D -> -F -> -X -> COMMIT`.
- EXP-004.5 подтвердил marker-selective `proto 201/202` route inventory для cleanup.
- External CLI forms, влияющие на safety contract, должны вручную проверяться на target
  Debian до кодирования в subprocess adapter.
- Deny-only selector-family INPUT guard target-validated EXP-005; prefix wildcard
  запрещён для ACCEPT/NAT.
- `ip_forward` изменяется read-before-write и результат подтверждается.
- Subprocess calls имеют bounded timeout и stable `LC_ALL=C`/`LANG=C`.
- Netfilter notifications остаются optional enhancement; correctness опирается на
  Netlink-route events + periodic full reconciliation.
- Binding-sensitive repair использует deny-first barrier:
  isolation filter -> verify -> desired NAT -> verify -> full desired filter -> verify ->
  routes -> verify. Это ordering сохраняется даже если forwarding OFF не удалось подтвердить.
- Interface inventory failure является isolation-class failure: binding-specific blind repair
  запрещён, config-only isolation filter может использоваться как безопасный barrier при
  читаемом firewall boundary.
- Route/address/interface snapshots не являются атомарной kernel transaction. Архитектура
  требует один fresh snapshot каждого типа, reused consistently within pass, а не
  псевдо-atomic wrapper.
- Config security: regular non-symlink config, root-owned, parent protected from group/other
  writes.
- Runtime directory security отдельно проверяет type/symlink/owner/mode перед lock.
- Python implementation может быть package с несколькими файлами; один daemon entry point
  сохраняется. Будущий Rust — один binary.


## 25. Открытые решения

Следующие implementation/research details требуют подтверждения:

1. Точный механизм сериализованного цикла обработки событий и debounce/coalesce Netlink bursts.
2. Стратегия полной пересверки после Netlink `ENOBUFS`.
3. Финальный systemd privilege model: root либо отдельный service user + минимальные
   capabilities/permissions.
4. Точный минимальный IPC/admin command set.
5. Foreign exact route metric/key collision edge case, ранее отложенный до отдельного target
   experiment.
6. Пороги repair-storm/latching не вводятся без наблюдаемых данных.

## 26. Ключевые инварианты

Ниже используется компактная техническая запись. В пределах этого блока: selector
(селектор), binding (привязка), concrete binding (жесткая привязка), reconciliation
(согласование), policy (политика), guard (защитное правило), verify (проверить), cleanup
(очистка), overlap (наложение), marker (маркер владения). Именованные состояния и
идентификаторы сохраняются без перевода.

```text
1. Один daemon process владеет всеми VPN-GATE kernel resources.

2. Config читается один раз за process lifetime; изменения применяются только restart.

3. Startup: handlers -> runtime-dir/LOCK -> CLEANUP -> LOAD/VALIDATE -> APPLY -> RUN.

4. Startup failure никогда не переходит в DEGRADED; forwarding не должен остаться enabled.

5. cleanup config-independent и marker-based.

6. BLACKHOLE ownership marker: proto 201 + type BLACKHOLE + metric 65536.

7. VPN UNICAST ownership marker: proto 202.

8. Cleanup route inventory использует protocol-selective queries 201/202, не полный main.

9. Full reconciliation route inventory остаётся strict и не silently omits unsupported
   multipath/nhid state.

10. ip_forward exclusive-owned daemon'ом и изменяется read-before-write с verify.

11. Exclusive ownership ip_forward означает terminal verdict для каждого IPv4 FORWARD packet.

12. Foreign FORWARD rules физически сохраняются, но недостижимы при ip_forward=1 из-за
    VPNG-FORWARD-DENY.

13. INPUT foreign host-firewall rules сохраняют значение для traffic вне managed selectors.

14. Interface config value является selector: exact name либо prefix family `prefix+`.

15. Trailing `+` является prefix-selector operator и использует target-validated iptables
    interface-prefix semantics.

16. Prefix family `prefix+` означает весь textual ifname namespace, начинающийся с
    `prefix`, включая bare name `prefix`.

17. Prefix selector никогда не попадает в RouteSpec/iptables ACCEPT/NAT kernel operand;
    эти ресурсы используют только resolved concrete exact ifname.

18. Managed selectors pairwise disjoint по множеству возможных concrete names; overlap fatal.

19. 0 selector matches = absent/not-ready; 1 = concrete binding; >1 = ambiguous.

20. Startup runtime ambiguity fatal; RUN ambiguity -> profile FAIL/DEGRADED fail-closed state.

21. Concrete binding identity включает exact name + ifindex; same-name recreate считается
    binding transition.

22. Readiness = unique concrete binding + expected local IPv4.

23. operstate/LOWER_UP/peer reachability/ping/handshake не входят в readiness.

24. Binding-specific allow/NAT/unicast policy существует только для ready concrete binding.

25. BLACKHOLE и protected-destination reject не зависят от binding/readiness.

26. Profile INPUT exact chain завершает managed ready-interface traffic; unconsumed selector
    traffic закрывает deny-only VPNG-INPUT-GUARD.

27. Family wildcard/prefix match допустим только как deny-only guard после target validation;
    wildcard ACCEPT/NAT запрещён.

28. FORWARD order: VPNG-INGRESS -> VPNG-RESERVED -> profile chains ->
    VPNG-FORWARD-DENY -> foreign rules.

29. Profile FORWARD dynamic ACCEPT требует source + protected destination + exact concrete
    egress.

30. Для каждого protected destination после dynamic ACCEPT всегда существует unconditional
    REJECT.

31. VPNG-FORWARD-DENY делает terminal DROP/REJECT для всего оставшегося IPv4 transit.

32. FORWARD к managed transport vpn.network REJECT'ится до profile ACL.

33. New ingress из ready managed VPN interface не разрешает reverse forwarding:
    INVALID DROP, ESTABLISHED/RELATED ACCEPT, остальное REJECT.

34. NAT chain существует structural для каждого managed profile; MASQUERADE exact concrete
    egress существует только при ready binding.

35. NAT policy verified раньше proto-202 route restoration через новый binding.

36. Binding transition detected -> best-effort ip_forward=0 before binding-sensitive policy
    mutation.

37. Residual kernel-event -> daemon-reaction window существует и документирован; architecture
    не изображает его как атомарный.

38. Netlink event является wakeup/dirty signal; authoritative state читается fresh snapshot.

39. Event имени, потенциально matching managed selector, инициирует resync.

40. Periodic reconciliation обязателен как safety net; reconcile_interval нельзя отключить 0.

41. One immutable binding/readiness snapshot reused through build/apply/verify pass.

42. Desired BLACKHOLE RouteSpec config-only; desired UNICAST RouteSpec config + concrete binding.

43. UNICAST RouteSpec.interface всегда exact concrete ifname.

44. Missing BLACKHOLE adds выполняются раньше destructive route operations.

45. Route executor: blackhole adds -> exact deletes -> replaces -> remaining adds.

46. Daemon authoritative только для exact protected prefixes profile.routes.

47. Competing foreign exact routes могут удаляться; proto kernel никогда не delete/replace.

48. More-/less-specific overlaps автоматически не удаляются.

49. Default route не считается overlap diagnostic resource.

50. OWNED routes и committed binding state меняются только после verify.

51. Process-local OWNED/binding commit происходит до final forwarding enable, не после.

52. Kernel actual-state само по себе не означает ownership adoption.

53. Fixed/structural и binding-specific firewall rules имеют единый desired policy builder;
    compare и restore не имеют независимых policy sources.

54. Firewall safety = SAFE/UNSAFE/UNKNOWN; UNKNOWN не repair'ится blind.

55. UNSAFE/binding repair использует deny-first ordering:
    isolation filter -> verify -> desired NAT -> verify -> full desired filter -> verify ->
    routes -> verify.

56. Failure подтвердить ip_forward=0 не разрешает full ACCEPT раньше verified NAT; deny-first
    barrier всё равно применяется.

57. Interface inventory/read/parse/resolution failure -> ISOLATED, не обычный DEGRADED.

58. При interface inventory failure binding-specific blind repair запрещён; config-only
    isolation filter допустим как безопасный barrier при читаемом firewall boundary.

59. After isolation forwarding возвращается только после SAFE full policy + completed fresh route pass.

60. Runtime ambiguity desired policy удаляет/не создаёт exact allow/NAT/unicast, сохраняя
    blackhole/deny.

61. ABSENT/not-ready profile сам по себе не FAIL, если fail-closed desired state успешно verified.

62. AMBIGUOUS profile является FAIL до восстановления uniqueness.

63. ACTIVE = policy SAFE + all profile results SUCCESS + ip_forward=1; ACTIVE не означает
    доказанную VPN connectivity.

64. SAFE с profile FAIL -> DEGRADED; non-SAFE или insufficient policy observability -> ISOLATED.

65. cleanup order: forwarding OFF -> proto202 -> firewall/NAT -> proto201 blackhole -> verify.

66. Blackhole снимается только после подтверждённой очистки остальных owned resources.

67. iptables cleanup exact; никаких global table flush.

68. VPNG-* namespace полностью reserved daemon'ом.

69. Per-table iptables restore atomicity не считается cross-table atomicity.

70. Runtime directory final component non-symlink directory, mode 0700, expected service owner.

71. Missing runtime directory daemon может создать сам при достаточных правах.

72. Existing wrong runtime-dir owner/mode не чинится молча.

73. Lock file O_NOFOLLOW + lifetime nonblocking flock.

74. Config file regular non-symlink, root-owned, parent protected from group/other writes.

75. --check-config не acquires runtime lock и не меняет kernel state.

76. Unknown config keys fatal для managed runtime projection.

77. Unmanaged malformed definitions не блокируют startup; lint gives WARNING.

78. Managed protected routes globally non-overlapping and не пересекают managed vpn.network.

79. peers order задаёт metrics 10,20,30...; peers=[] валиден.

80. common_allowed_sources union profile.allowed_sources; deny/exclude semantics нет.

81. Reverse accessibility не входит в текущий contract и не получается ослаблением ingress deny.

82. Python implementation может быть multi-file package, но имеет один daemon entry point.

83. Domain boundaries должны быть переносимы в future Rust modules/structs/enums; Rust deployment
    ориентирован на один executable binary.

84. Один event loop сериализует Netlink, timer, IPC и shutdown; parallel reconciliation запрещён.

85. Signal handlers не выполняют kernel work; shutdown проходит через serialized lifecycle cleanup.

86. SIGHUP не reload'ит config.

87. External CLI safety contracts проверяются на target Debian до закрепления в adapter.

88. Programming exceptions не маскируются как expected UNKNOWN/DEGRADED.

89. Machine reason identity задаётся stable enum codes, не free-form exception text.

90. Prefix-family selector reserves its entire matching textual runtime ifname namespace for
    the managed profile; unrelated matching netdev can intentionally force AMBIGUOUS
    fail-closed state.

91. Residual event-reaction window is an explicit trusted-host threat-model boundary:
    untrusted processes do not possess CAP_NET_ADMIN/netdev lifecycle control.

92. Same-name/new-ifindex replacement is detectable at snapshot reconciliation but existing
    iptables name matches cannot be retroactively bound to historical ifindex.

93. Interface inventory duplicate name with conflicting ifindex is invalid kernel inventory.

94. Protocol-selective cleanup remains strict for reserved proto 201/202 entries; unsupported
    selected route shapes are fatal, not silently skipped.

95. desired isolation filter is config-only and contains no binding-specific ACCEPT.

96. Isolation filter materialization is replacement/canonicalization of the complete
    daemon-owned filter desired state for that stage; stale daemon binding-specific ACCEPT
    rules may not remain reachable.

97. Isolation-filter verify is a distinct barrier result and never satisfies full desired
    firewall/NAT SAFE.

98. Full-policy SAFE requires desired NAT + full desired filter to be verified for the same
    immutable reconciliation snapshot.

99. Operational status reports selector/binding/readiness separately from lifecycle ACTIVE.

```
