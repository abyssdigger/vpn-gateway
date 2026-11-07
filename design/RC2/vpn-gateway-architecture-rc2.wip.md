# VPN Gateway — архитектурные решения и инварианты

**Статус:** Release Candidate — кандидат на утверждение и реализацию
**Версия:** RC2.4
**Дата:** 2026-11-07

Документ фиксирует принятые архитектурные решения проекта VPN Gateway. Он описывает обязательные инварианты, жизненный цикл сервиса, модель владения kernel-state и правила конфигурации. Нереализованные детали, которые ещё требуют отдельного решения, вынесены в раздел **«Открытые решения»**.

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

### 2.1. Fail hard

При ошибке очистки, валидации или применения конфигурации сервис не переходит в частично рабочее состояние.

Ошибка на старте означает:

- `ip_forward` не включается;
- новая конфигурация не считается применённой;
- процесс завершается с ненулевым кодом;
- systemd переводит сервис в `failed`.

Режим `DEGRADED` на старте не используется.

### 2.2. Fail closed

Защищаемый трафик не должен при отказе VPN или ошибке конфигурации уходить через обычный default route.

Blackhole-маршруты являются одним из защитных механизмов и устанавливаются до разрешения forwarding.

Важно: blackhole обеспечивает fail-closed на уровне выбора маршрута для соответствующего prefix. Он не является универсальной гарантией доставки и не заменяет независимую фильтрацию `FORWARD`.

### 2.3. Один владелец сетевого состояния

Один долгоживущий процесс `vpn-gatewayd` является единственным владельцем ресурсов проекта:

- firewall;
- blackhole;
- VPN-маршрутов;
- NAT;
- `net.ipv4.ip_forward`.

Внешние скрипты и административные клиенты не должны самостоятельно изменять эти ресурсы.

`vpn-gatewayd` предназначен для выделенного VPN-gateway host. Совмещение с Docker, Kubernetes, другими gateway-сервисами или иными компонентами, которым требуется `net.ipv4.ip_forward=1`, не поддерживается: `cleanup()` безусловно выставляет `ip_forward=0`.

`net.ipv4.ip_forward` находится в exclusive ownership daemon'а. Ручное изменение sysctl не является persistent administrative pause/override и будет приведено daemon'ом к требуемому значению на следующем завершённом reconciliation pass.

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

## 4. Мониторинг VPN-интерфейса

Для мониторинга используется Linux Netlink через стандартный Python `socket`:

```text
AF_NETLINK
NETLINK_ROUTE
```

Сервис реагирует на изменения интерфейсов и IPv4-адресов.

Основные типы событий:

- `RTM_NEWLINK`;
- `RTM_DELLINK`;
- `RTM_NEWADDR`;
- `RTM_DELADDR`.

При старте сервис не полагается только на будущие события Netlink: он выполняет начальную полную сверку фактического состояния интерфейсов.

Если обнаружена потеря Netlink-событий, например `ENOBUFS`, сервис обязан выполнить полный resync фактического состояния.

Периодический polling connectivity-сигналов (`operstate`, `LOWER_UP`, peer reachability, ping, handshake) не требуется. Однако `VpnGatewayDaemon` выполняет periodic reconciliation kernel-resources как safety net против resource drift, ручного вмешательства и потери Netlink-событий.

### 4.1. Критерий готовности VPN

VPN-профиль считается подготовленным, если:

- ожидаемый интерфейс существует;
- на нём присутствует ожидаемый локальный IPv4-адрес.

Не используются как критерий готовности:

- `operstate`;
- `LOWER_UP`;
- доступность удалённого peer;
- ping;
- handshake VPN-протокола;
- фактическое прохождение трафика.

Это намеренно.

Правила, маршруты и NAT не должны дёргаться при каждом временном обрыве VPN-соединения.

Под «временным обрывом» понимается недоступность удалённой стороны при сохранении VPN-интерфейса и ожидаемого локального IPv4-адреса. В этом случае VPN-маршруты и NAT остаются без изменений.

Если исчезает сам интерфейс либо ожидаемый локальный IPv4-адрес, VPN-профиль становится `not ready`, и выполняется runtime reconciliation VPN-маршрутов.

Сервис не знает и не проверяет протокол VPN, состояние handshake или внутреннее состояние VPN-клиента/сервера.

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

### 5.2. Блокировка экземпляра

Чтобы одновременно не работали два экземпляра `vpn-gatewayd`, процесс удерживает эксклюзивную блокировку, например:

```text
/run/vpn-gateway/vpn-gatewayd.lock
```

Блокировка удерживается всё время жизни процесса и автоматически освобождается ядром при его завершении.

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

`RuntimeDirectory` создаёт `/run/vpn-gateway` до старта daemon; lifetime lock расположен внутри него. Каталог должен принадлежать service identity и быть недоступен посторонним.

`ExecStopPost` является **вторичным fail-closed safety net** на случай SIGKILL, watchdog timeout или аварии процесса, когда Python cleanup физически не исполнился. Конкретная команда/привилегии unit должны позволять best-effort установить:

```text
net.ipv4.ip_forward = 0
```

например через `sysctl -q -w`. Failure этого safety net не заменяет daemon cleanup и не маскируется как успешная очистка.

Deployment не должен задавать постоянное `net.ipv4.ip_forward=1` через `sysctl.d`: runtime owner этого sysctl — `vpn-gatewayd`. Это административная рекомендация, а не security boundary. Для защиты от случайной ошибки администратора рекомендуется установить заметный README-файл в `/etc/sysctl.d/` и комментарий в управляемой документации/`sysctl.conf`, объясняющие ownership `ip_forward`.

Другие firewall managers/persistence могут однократно изменить filter/NAT state: daemon обнаружит drift на reconciliation pass, залогирует его, fail-closed выключит forwarding и восстановит policy. Конфигурация, в которой внешний сервис **постоянно** переписывает daemon-managed rules, считается unsupported administrative conflict.

Архитектура **не требует `geteuid()==0`**. Предпочтительно сохранить возможность запуска от отдельного service user с минимальным набором Linux capabilities/permissions, если стендовые проверки подтвердят достаточность. Точный privilege model остаётся implementation/deployment решением.

Это совместимо с security contract конфигурации: config и его parent остаются root-owned и не writable group/other. При непривилегированном service user допустим, например, root-owned config с read-доступом через dedicated service group; group write по-прежнему запрещён.

## 6. Универсальный cleanup

`cleanup()` не зависит от того, вызывается ли он:

- при старте;
- после аварийного предыдущего запуска;
- при штатном stop.

Контракт один:

> успешный `cleanup()` означает полное отсутствие всех ресурсов, принадлежащих VPN Gateway.

### 6.1. Обязательная маркировка ресурсов

Runtime inventory не сохраняется между запусками. При restart startup `cleanup()` удаляет все ресурсы по глобальным ownership-маркерам, после чего новый процесс начинает с пустого `owned` и чистого kernel-state для управляемых ресурсов.


`cleanup()` выполняется до чтения конфигурации и не использует persistent runtime-state.

Поэтому каждый создаваемый сервисом kernel-resource обязан иметь однозначный маркер, позволяющий обнаружить его без текущего или предыдущего конфига.

Принятые маркеры:

```text
blackhole routes -> proto 201, metric 65536
VPN routes       -> proto 202
iptables chains  -> весь зарезервированный namespace `VPNG-*`
owned jumps      -> jumps с target `VPNG-*`
```

Префикс chain name `VPNG-` целиком зарезервирован за daemon во всех используемых iptables tables. Администратор и другие firewall managers не должны создавать собственные chains с этим префиксом.

Такой namespace-marker покрывает и глобальные (`VPNG-INGRESS`, `VPNG-RESERVED`), и профильные chains, поэтому `cleanup()` не зависит от перечня chain names старой конфигурации.

Ресурс, который невозможно однозначно идентифицировать без конфигурации или external state, `vpn-gatewayd` создавать не должен.

### 6.2. Порядок cleanup

1. Отключить IPv4 forwarding.
2. Инвентаризировать собственные ресурсы по маркерам.
3. Удалить собственные VPN-маршруты.
4. Удалить owned jumps/chains из reserved `VPNG-*` namespace в NAT/filter tables.
5. Удалить собственные blackhole — только после успешной очистки остальных сетевых ресурсов.
6. Повторно проверить фактическое состояние.

### 6.3. Результаты cleanup

У `cleanup()` только два результата.

**SUCCESS**

- `ip_forward = 0`;
- нет собственных VPN-маршрутов;
- нет собственного NAT;
- нет собственных firewall-правил;
- нет собственных blackhole;
- система свободна от артефактов сервиса.

**FAILURE**

Полная очистка не подтверждена.

В этом случае:

- запуск не продолжается;
- blackhole не снимаются, если очистка других ресурсов не подтверждена;
- ошибка явно журналируется.

### 6.4. Никаких blind flush

Запрещено:

- очищать целые таблицы маршрутизации;
- flush всей `filter`/`nat` таблицы;
- удалять чужие маршруты вне authoritative routing scope;
- удалять чужие правила.

Общее правило: удаляются только ресурсы, однозначно идентифицированные как принадлежащие VPN Gateway.

Исключение: exact destination prefixes из `profile.routes` являются authoritative routing scope (§23.1). Competing foreign routes с тем же exact destination могут удаляться и заменяться каноническими desired routes. More-specific и less-specific overlaps автоматически не удаляются.

Orphaned-ресурсы предыдущей конфигурации, если они имеют наши маркеры, считаются нашими и должны удаляться без обращения к старому конфигу.

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

## 8. Apply

`apply()` вызывается только после:

1. успешного `cleanup()`;
2. успешной загрузки и валидации;

Порядок:

1. прочитать initial route/interface snapshot, построить и `_validate_plan()` initial route plan; это ловит unreconcilable kernel conflicts (`proto kernel`) до новых side effects;
2. установить fixed firewall/NAT infrastructure для managed-профилей
   **атомарно per table/COMMIT, но не как cross-table transaction**:
   `VPNG-INGRESS`, `VPNG-RESERVED`, профильные `INPUT`/`FORWARD`/`NAT` chains,
   jumps и постоянное MASQUERADE rule каждого managed-профиля независимо от readiness/peers;
3. verify firewall/NAT infrastructure как `SAFE`;
4. применить initial route plan через shared route executor; missing BLACKHOLE guards идут первой фазой;
5. verify route state; любой profile `FAIL` на startup фатален;
6. самым последним включить:

```text
net.ipv4.ip_forward = 1
```

Если любой этап завершается ошибкой, `apply()` считается неуспешным, forwarding не должен оставаться включённым.

Partial kernel-state после failed `apply()` не откатывается отдельной rollback-транзакцией. Он остаётся помеченным ownership markers и будет удалён следующим `cleanup()`. Поскольку `ip_forward=1` включается только последним шагом успешного `apply()`, такой partial state не должен разрешать forwarding.



Bootstrap `apply()` и runtime reconciliation — разные orchestration phases, но используют один и тот же route reconciliation engine.

Bootstrap `apply()`:

```text
build + validate initial route plan
fixed firewall + NAT infrastructure
firewall verify
shared route apply
route verify
ip_forward = 1
```

Runtime reconciliation поддерживает routes, обеспечивает наличие всех configured blackhole guards и проверяет daemon-owned firewall infrastructure. Blackhole policy managed-профилей не пересчитывается динамически: daemon только восстанавливает отсутствующие configured guards.

Firewall infrastructure также не пересчитывается как policy на каждом pass, но её фактическое состояние read-only сверяется с ожидаемым. При подтверждённом firewall drift daemon сначала выставляет `ip_forward=0`, затем атомарно восстанавливает owned firewall infrastructure, повторно verify'ит её и только после успешной проверки может снова включить forwarding. Оставлять `ip_forward=1` при подтверждённо повреждённой фильтрации запрещено.

### 8.1. Runtime VPN state reconciliation

После `RUN` runtime reconciliation управляет **только routing state** managed-профилей. MASQUERADE больше не является dynamic profile-state: это fixed firewall/NAT infrastructure, установленная bootstrap'ом и поддерживаемая firewall verification/repair.

При каждом релевантном Netlink-событии и periodic tick daemon выполняет reconciliation managed set.

Shared route engine не меняет `VpnGatewayDaemon.state`. Runtime wrapper отдельно классифицирует firewall safety и route/profile results.

Daemon-level pass:

```text
1. verify fixed firewall/NAT infrastructure;
2. если firewall/NAT state = UNSAFE:
       best-effort ip_forward = 0;
       atomic firewall/NAT repair;
       verify;
       если verify неуспешен -> ISOLATED и завершить pass;
3. если firewall/NAT state = UNKNOWN:
       best-effort ip_forward = 0;
       ISOLATED и завершить pass без blind repair;
4. только после SAFE fixed firewall/NAT:
       прочитать fresh routes + interface/address snapshot;
5. вычислить readiness managed-профилей;
6. получить CONFIGURED routes и текущий OWNED;
7. один раз построить immutable `desired_routes_by_profile` для этого pass:
       configured BLACKHOLE routes -> всегда;
       configured UNICAST routes   -> только если profile ready;
8. выделить related_kernel_routes;
9. построить route-only ReconciliationPlan, используя тот же desired snapshot;
10. `_validate_plan()` до side effects, используя тот же desired snapshot;
11. executor:
       missing BLACKHOLE adds first;
       затем ordinary route deletes/adds;
12. перечитать actual routes и verify относительно **того же**
    `desired_routes_by_profile`; readiness/DESIRED внутри pass повторно не вычислять;
13. сформировать полный per-profile SUCCESS/FAIL mapping;
14. проверить `keys(profile_results) == keys(managed profiles)`;
15. commit OWNED routes только по подтверждённому verify;
16. вернуть результаты runtime wrapper.
```

Transient inventory retry **до fail-closed isolation запрещён**: при невозможности подтвердить firewall safety daemon сначала пытается выключить forwarding и только затем может выполнять дополнительные diagnostic/retry actions. RC2.1 не требует отдельной immediate retry policy; она может быть добавлена позже только после стендовых данных и без ослабления этого ordering.

После `ISOLATED`, когда firewall/NAT снова `SAFE`, forwarding не включается немедленно: сначала должен завершиться fresh route reconciliation/verify pass. Он не обязан быть `SUCCESS` у всех managed-профилей — route failures являются profile-local и остаются fail-closed через BLACKHOLE + FORWARD policy.

Если fresh route pass завершился и firewall/NAT `SAFE`, daemon приводит exclusive-owned `ip_forward` к `1`. Если сам route snapshot/verify не состоялся (`KernelError` до завершённого pass), прежнее `ip_forward=0` после isolation сохраняется до следующей успешной попытки.

Runtime lifecycle:

```text
firewall != SAFE                         -> ISOLATED
firewall == SAFE
  AND all managed profiles == SUCCESS
  AND ip_forward == 1                    -> ACTIVE
firewall == SAFE, остальные завершённые
route reconciliation passes              -> DEGRADED
```

`ACTIVE` требует `ip_forward=1`. Ошибка включения forwarding при остальных успешных условиях даёт `DEGRADED` с причиной `forwarding-off`.

Ручное `sysctl -w net.ipv4.ip_forward=0` не является administrative pause: daemon владеет значением и вернёт `1` после завершённого SAFE reconciliation pass. Если когда-либо понадобится административная пауза, она должна иметь отдельный explicit control/API.

### Executor safety ordering

NAT/route dependency ordering больше не требуется: MASQUERADE уже существует до runtime route operations и удаляется только при shutdown cleanup.

Route executor обязан соблюдать:

```text
1. missing BLACKHOLE route_adds;
2. competing exact route_deletes;
3. authoritative route_replaces;
4. остальные route_adds.
```

`route_replaces` не означает blind adoption. Это активная materialization operation (`ip route replace` или эквивалент), после которой ownership всё равно фиксируется только успешным verify/commit.

Plan validation checks:

```text
1. route_adds, route_deletes и route_replaces попарно disjoint;
2. foreign route delete допустим только на exact protected prefix;
3. `proto kernel` route никогда не может присутствовать в route_deletes или route_replaces;
4. owned non-desired delete должен соответствовать ownership соответствующего managed-профиля;
5. каждый add/replace должен соответствовать runtime DESIRED некоторого managed-профиля;
6. replace допустим только для RouteSpec, уже присутствующего в ACTUAL и отсутствующего в OWNED;
7. add допустим только для RouteSpec, отсутствующего в ACTUAL;
8. два managed-профиля не могут претендовать на один exact protected prefix/resource.
```

Validation failure до side effects:
- startup bootstrap -> fatal;
- runtime reconciliation -> plan не применяется, runtime wrapper переводит daemon в DEGRADED.

Для domain-level validation используется отдельный `PlanValidationError`.

Для нарушения контракта самого reconciliation pass используется `ReconciliationError`. В частности, completed verify обязан вернуть result для **каждого** managed-профиля; partial/empty mapping не может изображать завершённый pass.

После подтверждённого fixed firewall/NAT `SAFE` ошибки route/interface snapshot, plan validation/apply/verify (`KernelError`/`PlanValidationError`/`ReconciliationError`) дают runtime `DEGRADED`, а не завершают процесс. Ошибки самой fixed firewall/NAT safety/inventory path классифицируются отдельно и могут дать `ISOLATED`.

Если apply/verify не дошёл до подтверждённого verify результата, последний подтверждённый OWNED не заменяется.

Это не ACID-транзакция и не гарантирует kernel rollback при частичном отказе. Транзакционность логическая: `snapshot -> plan -> apply -> verify -> commit OWNED`.

Если verify показывает несоответствие только у части managed-профилей, FAIL получают только эти профили; остальные могут получить SUCCESS. Отсутствие после verify configured blackhole guard для exact prefix профиля P является несоответствием именно профиля P и даёт P результат `FAIL`; остальные профили не получают `FAIL` только из-за этой ошибки. Daemon становится DEGRADED при любом FAIL. Итоговый OWNED каждого managed-профиля commit'ится только по подтверждённому verify фактическому состоянию этого профиля; глобального rollback/forget для успешно применённых профилей нет.

Если ресурс находится в `actual ∩ desired`, но отсутствует в `owned`, применяется одно из двух правил:

- для exact-prefix routes из `profile.routes` действует authoritative canonicalization (§23.1): plan содержит `route_replaces` для этого canonical desired `RouteSpec`; после успешной materialization и verify он записывается в `owned`; при успешной канонизации это не является причиной `FAIL`;
- для остальных ресурсов silent adoption запрещён: конфликт журналируется, daemon reconciliation возвращает `FAIL`, а агрегатор переводит daemon в `DEGRADED`.


Runtime reconciliation:

- управляет desired routes managed-профиля;
- в authoritative exact-route scope (§23.1) может удалять competing foreign routes с exact destination;
- не удаляет more-specific/less-specific foreign overlaps;
- не вызывает `cleanup()`;
- не перечитывает конфигурацию;
- read-only проверяет daemon-owned firewall infrastructure на каждом pass;
- при подтверждённом firewall drift best-effort выставляет `ip_forward=0`, затем атомарно восстанавливает owned firewall infrastructure и verify'ит её;
- не пересчитывает firewall policy из runtime-сигналов: восстанавливается только конфигурационно ожидаемая owned infrastructure;
- не модифицирует существующие собственные blackhole guard (`route_type=BLACKHOLE`, `proto 201`, `metric 65536`, `onlink=False`);
- восстанавливает отсутствующие configured blackhole guard;
- в конце завершённого pass приводит daemon-owned `ip_forward` к требуемому значению: после firewall/NAT `SAFE` и завершённого fresh route pass — `1`, при firewall/NAT `UNSAFE|UNKNOWN` — best-effort `0`.

`VPNG-<PROFILE>-NAT`, его `POSTROUTING` jump и MASQUERADE rule являются fixed infrastructure managed-профиля на всё время работы daemon.

Операция идемпотентна: повторное событие при уже корректном kernel-state не должно изменять состояние.


### 8.2. Runtime fixed firewall/NAT verification

Fixed firewall/NAT safety state классифицируется отдельно от daemon lifecycle state:

```text
SAFE
    firewall/NAT inventory прочитан успешно
    и daemon-owned fixed firewall/NAT infrastructure verify прошёл

UNSAFE
    inventory прочитан успешно
    и подтверждён drift daemon-owned fixed firewall/NAT infrastructure

UNKNOWN
    firewall/NAT inventory не удалось надёжно прочитать
```

На каждом reconciliation pass fixed firewall/NAT infrastructure проверяется **до** чтения route/interface snapshot.

Firewall infrastructure verify проверяет:

- существование и fixed contents `VPNG-INGRESS`, `VPNG-RESERVED` и всех managed `VPNG-<PROFILE>-INPUT/FORWARD`;
- существование и fixed MASQUERADE contents всех managed `VPNG-<PROFILE>-NAT`;
- точный layout owned jumps в `INPUT`, `FORWARD` и `POSTROUTING`.

Для `UNSAFE`:

```text
best-effort ip_forward = 0
    -> atomic repair
    -> firewall verify
    -> success: продолжить pass с fresh route/interface snapshot
    -> failure: ISOLATED
```

Для `UNKNOWN` blind repair не выполняется:

```text
best-effort ip_forward = 0
    -> ISOLATED
    -> retry на следующем reconciliation pass
```

Если попытка `set_ip_forward(False)` сама завершается ошибкой, daemon **не завершается добровольно** и не прекращает firewall repair. Для `UNSAFE` он всё равно восстанавливает сначала `filter`, затем `nat`, после чего verify'ит firewall. Ошибка отключения forwarding сохраняется как high-severity факт текущего pass, но восстановление ACL/изоляции полезнее, чем отказ от ремонта.

Expected failure canonical comparison/parsing/normalization daemon-owned firewall snapshot классифицируется как `UNKNOWN`, а не выбрасывается из reconciliation: observability недостаточна для подтверждения `SAFE`/`UNSAFE`. Он получает стабильный reason code и не разрешает blind repair. Programming errors не маскируются широким `except Exception`.

Для `UNKNOWN` blind repair по-прежнему не выполняется: daemon пытается выключить forwarding, остаётся в `ISOLATED` и повторяет inventory на следующем pass. Общая обработка failure `set_ip_forward(False)` для `UNSAFE` и `UNKNOWN` зафиксирована ниже.

#### 8.2.1. Failure to disable forwarding during isolation

`set_ip_forward(False)` является best-effort safety action. Его failure **никогда сам по себе не является основанием добровольно завершить daemon**.

Поведение зависит от уже известной firewall/NAT safety:

```text
UNSAFE:
    daemon остаётся жив
    sysctl failure -> high-severity fact текущего pass
    repair fixed firewall/NAT всё равно выполняется
    filter восстанавливается раньше nat
    затем verify продолжается

UNKNOWN:
    daemon остаётся жив
    state = ISOLATED
    sysctl failure -> high-severity fact текущего pass
    blind repair не выполняется
    следующий pass снова начинается с firewall/NAT inventory
```

Различие принципиально: при `UNSAFE` drift подтверждён и repair улучшает известное плохое состояние; при `UNKNOWN` daemon не имеет достаточной observability для безопасного blind repair.

После firewall/NAT repair `ip_forward=1` не возвращается немедленно. Сначала fixed infrastructure должна перейти в `SAFE`, затем daemon читает fresh route/interface snapshot и завершает profile route reconciliation + verify/commit.

Возобновление forwarding после isolation требует:

```text
fixed firewall/NAT SAFE
AND fresh route reconciliation/verify pass завершён
```

`iptables-restore` atomic только внутри отдельной table/`COMMIT`, а не как единая cross-table transaction для `filter` + `nat`. Нормальный repair выполняется при `ip_forward=0`. Cross-table repair остаётся `filter` -> `nat`; failure отключения forwarding трактуется по §8.2.1.


Если после firewall/NAT repair (`SAFE`) не удалось получить fresh routes/interface snapshot или route pass не дошёл до завершённого verify, forwarding не возобновляется. Предыдущее `ip_forward=0` сохраняется до следующего завершённого fresh route pass.

### 8.3. Runtime ACTIVE / DEGRADED / ISOLATED

Fail-hard относится к старту сервиса. После успешного входа в `RUN` локальная ошибка runtime reconciliation не должна автоматически останавливать сервис.

Если при подтверждённом `SAFE` fixed firewall/NAT не удалось полностью привести VPN-маршруты к желаемому состоянию:

- успешно работающие ресурсы сохраняются;
- неисправные или отсутствующие маршруты остаются защищены соответствующими blackhole;
- сервис переходит из `ACTIVE` в `DEGRADED`;
- фактическое значение `ip_forward` является отдельной operational axis и показывается в `status`;
- причина и конкретные несогласованные ресурсы журналируются.

Если firewall/NAT safety не подтверждена (`UNSAFE`/`UNKNOWN`) или repair/verify не завершён успешно, daemon находится в `ISOLATED`, а не в `DEGRADED`.

`DEGRADED` и `ISOLATED` являются эксплуатационными, а не стартовыми состояниями.

`ACTIVE` определяется строго:

```text
firewall SAFE
AND all managed profiles SUCCESS
AND ip_forward == 1
```

Если firewall `SAFE` и все managed-профили `SUCCESS`, но `ip_forward=1` установить/подтвердить не удалось, daemon остаётся/переходит в `DEGRADED` с причиной `forwarding-off`.

`net.ipv4.ip_forward` находится в exclusive ownership daemon'а. Ручное `sysctl -w net.ipv4.ip_forward=0` не является persistent administrative pause: следующий завершённый pass с fixed firewall/NAT `SAFE` и fresh route verify снова приводит значение к `1`. Отдельная административная пауза, если она понадобится, должна иметь явный control/API, а не использовать прямую запись sysctl.

Последующие Netlink-события и full resync повторяют reconciliation. Если firewall снова `SAFE`, а все managed-профили полностью соответствуют желаемому состоянию, сервис автоматически возвращается в `ACTIVE`; при SAFE firewall и частичной profile-деградации остаётся `DEGRADED`.

Команда `status` должна различать `ACTIVE`, `DEGRADED` и `ISOLATED`, отдельно показывать фактическое значение `ip_forward` и для каждого managed-профиля показывать как минимум:

```text
result: SUCCESS | FAIL
reason: <RuntimeReasonCode + human description, or none>
```

Если выводятся несогласованные ресурсы, они определяются текущей сверкой с kernel-state на момент запроса, а не берутся из кэша прошлого reconciliation.

Во время `STARTING`/`STOPPING`, если IPC уже/ещё доступен, `status` может отвечать `daemon is not ready`; отсутствие IPC socket в эти фазы также допустимо.

## 9. Firewall и blackhole

Firewall является эксклюзивным владельцем IPv4-фильтрации VPN-потоков проекта.

Для каждого managed VPN-профиля создаются отдельные цепочки:

```text
VPNG-<PROFILE>-INPUT
VPNG-<PROFILE>-FORWARD
```

где `<PROFILE>` — uppercase profile ID.

Managed profile jumps образуют детерминированные contiguous blocks:

```text
INPUT
  1..N -> VPNG-<PROFILE>-INPUT, sorted by case-insensitive profile ID
  далее -> чужие правила...

FORWARD
  1     -> VPNG-INGRESS
  2     -> VPNG-RESERVED
  3..   -> VPNG-<PROFILE>-FORWARD, sorted by case-insensitive profile ID
  далее -> чужие правила...

POSTROUTING
  1..N -> VPNG-<PROFILE>-NAT, sorted by case-insensitive profile ID
  далее -> чужие правила...
```

`VPNG-INGRESS` и `VPNG-RESERVED` — глобальные owned chains. Profile ordering не зависит от порядка `[vpn.*]` или `managed_vpns` в TOML.

Каждый jump:

- существует ровно в одном экземпляре;
- является обычным `-j`;
- не использует `-g`.

Порядок managed-профилей детерминирован: они сортируются по case-insensitive profile ID; порядок в `managed_vpns` является только selection и не задаёт priority.

Механика `iptables -I` не является частью policy: implementation может вставлять rules в обратном порядке или по явным позициям, если итоговый layout совпадает с указанным выше.

### 9.1. INPUT semantics

`effective_allowed_sources` в INPUT не используется. Профильный ACL относится исключительно к FORWARD.

Каждая `VPNG-<PROFILE>-INPUT` обрабатывает только трафик, пришедший с интерфейса своего VPN-профиля.

Порядок правил:

```text
-i profile.interface
ctstate INVALID
    DROP

-i profile.interface
ctstate ESTABLISHED,RELATED
    ACCEPT

-i profile.interface
-s profile.network
-d profile.local_address
ctstate NEW
    ACCEPT

-i profile.interface
    REJECT --reject-with icmp-host-prohibited

всё остальное
    RETURN
```

Таким образом:

- INVALID-пакеты с VPN-интерфейса молча отбрасываются;
- established/related трафик принимается;
- новые обращения из VPN-сети к локальному VPN-адресу gateway разрешаются;
- остальной трафик с VPN-интерфейса отклоняется;
- FORWARD ACL здесь не участвует.

### 9.2. FORWARD semantics

Отдельного понятия `LAN_IF` в модели нет.

Перед всеми профильными FORWARD chains демон создаёт глобальную цепочку:

```text
VPNG-INGRESS
```

и ставит jump к ней первым в built-in `FORWARD`.

Назначение `VPNG-INGRESS` — абсолютная изоляция нового трафика, пришедшего с любого managed VPN interface.

Для каждого профильного интерфейса логика:

```text
-i profile.interface
ctstate INVALID
    DROP

-i profile.interface
ctstate ESTABLISHED,RELATED
    ACCEPT

-i profile.interface
    REJECT --reject-with icmp-host-prohibited

RETURN
```

Следовательно, любой новый трафик, пришедший с managed VPN interface, завершается в `VPNG-INGRESS` и не доходит до профильных destination ACL.

Это гарантирует, что даже если VPN peer IP присутствует в `common_allowed_sources`, это не разрешает cross-profile VPN -> VPN forwarding.

Вторым глобальным guard является `VPNG-RESERVED`. Он запрещает FORWARD **к transport networks всех managed-профилей**:

```text
for each managed profile.network:
    -d profile.network
        REJECT --reject-with icmp-host-prohibited

RETURN
```

`vpn.network` предназначена только для local/peer tunnel addresses. Доступ gateway к peer выполняется через локальный OUTPUT/INPUT path и не требует FORWARD к transport network.

Runtime validation дополнительно запрещает пересечение managed protected `routes` с managed `vpn.network`; `VPNG-RESERVED` является defense-in-depth и фиксирует transport semantics в firewall.

После `VPNG-INGRESS` и `VPNG-RESERVED` идут профильные FORWARD chains managed-профилей в детерминированном порядке.

В каждой `VPNG-<PROFILE>-FORWARD` перед разрешающими ACCEPT для каждого protected destination действует:

```text
-d profile.route
-o profile.interface
ctstate INVALID
    DROP
```

Затем применяются разрешающие `source + destination + -o profile.interface -> ACCEPT`, после чего оставшийся трафик к protected destination получает `REJECT --reject-with icmp-host-prohibited`.

Это не даёт `INVALID` packet из разрешённого source пройти в VPN без корректной conntrack/NAT semantics.

Эффективный ACL профиля:

```text
effective_sources(profile)
    = common_allowed_sources
      ∪ profile.allowed_sources
```

`effective_sources(profile)`:

- удаляет только точные дубликаты;
- сохраняет разрешённые пересечения, например `/24` + `/32`;
- возвращает детерминированный immutable tuple;
- сортируется по `(network_address, prefix_length)`.

Порядок правил внутри `VPNG-<PROFILE>-FORWARD`:

```text
1. для каждого profile.route:
       для каждого effective_source:
           -s effective_source -d profile.route -o profile.interface
               ACCEPT

2. для каждого profile.route:
       -d profile.route
           REJECT --reject-with icmp-host-prohibited

3. всё остальное
       RETURN
```

Таким образом:

- ACL применяется к `source + destination route + expected egress interface` конкретного профиля;
- ACL одного профиля не даёт доступ к routes другого профиля;
- новый ingress с managed VPN interfaces блокируется глобально до профильных ACL;
- физический входной интерфейс разрешённого не-VPN источника не имеет значения;
- если kernel выбрал для protected destination чужой more-specific/less-specific route через другой egress interface, профильная chain не ACCEPT'ит такой пакет и завершается REJECT;
- ACL профиля расширяет `common_allowed_sources`, но не переопределяет и не сужает его.

Количество правил порядка `sources × routes` является допустимым и не считается проблемой производительности для целевого масштаба проекта.

### 9.3. Fail2ban

Текущая архитектура допускает Fail2ban как отдельный более ранний nftables-слой.

Проверенная модель:

```text
packet
  ↓
Fail2ban nft base chain, hook input priority -1
  ↓
iptables-nft filter INPUT
  ↓
prefix of VPNG-<PROFILE>-INPUT jumps
```

Это является требованием к внешней конфигурации Fail2ban: его nftables base chain должен иметь priority строго меньше priority iptables-nft filter chain. `vpn-gatewayd` не управляет и не проверяет priority чужих nftables base chains.

`vpn-gatewayd` не должен вычислять позицию jump относительно произвольных правил Fail2ban.

Fail2ban в данной модели применяется только к INPUT. FORWARD-трафик фильтруется без участия Fail2ban.

Fail2ban в этой архитектуре относится к защите сервисов самого host на INPUT. FORWARD имеет собственную явную policy и не использует Fail2ban.

### 9.4. Blackhole

Blackhole устанавливаются для всех защищаемых сетей managed-профилей.

Идентификация:

```text
proto 201
metric 65536
```

Blind `ip route replace blackhole ...` не используется: существующее состояние сначала проверяется.

После `cleanup()` VPN-специфичная фильтрация `VPNG-*` отсутствует. Оставшийся трафик обрабатывается прочими firewall-правилами и policy хоста. Forwarding при этом отключён.

`vpn-gatewayd` не является общим host firewall. Когда сервис остановлен, защита локального `INPUT` и любого трафика, не покрываемого отключённым forwarding, является ответственностью базовой firewall-конфигурации хоста. Сервис не изменяет и не очищает чужие правила.

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

Для каждого managed VPN-профиля NAT является **постоянной firewall infrastructure**, не зависящей от readiness и `peers`.

Во время bootstrap создаётся:

```text
VPNG-<PROFILE>-NAT
```

и постоянное правило:

```text
-o profile.interface
-m addrtype ! --src-type LOCAL
-j MASQUERADE
```

`POSTROUTING` содержит plain jump к каждой managed profile NAT chain в deterministic profile order.

MASQUERADE устанавливается даже при `peers=[]` и даже если interface в момент bootstrap отсутствует. Пока matching egress не существует, правило бездействует. Когда packet реально выходит через managed VPN interface, NAT уже присутствует до любых runtime route changes.

Правило намеренно scoped по **managed egress interface**, а не по `profile.routes`. `! --src-type LOCAL` может совпасть с любым forwarded packet с non-local source, покидающим managed VPN interface, включая traffic, появившийся из-за foreign route. Для выделенного gateway это считается defense-in-depth: лучше замаскировать такой egress, чем допустить утечку private source address.

Daemon считает весь managed VPN interface своим NAT egress scope. Совместное использование того же interface сторонней routing policy, которой NAT не нужен, не поддерживается.

MASQUERADE rule:

- создаётся bootstrap'ом;
- полностью проверяется как fixed firewall/NAT policy на каждом firewall verification pass;
- при drift восстанавливается тем же atomic firewall repair;
- не входит в route reconciliation;
- не имеет отдельного runtime OWNED state;
- удаляется только `cleanup()`/shutdown вместе с `VPNG-*` infrastructure.

Это возвращает исходный принцип: **маршрут создаётся только когда он нужен; NAT на managed egress присутствует заранее и постоянно**.

### 11.1. Принципиальная достаточность static NAT

Для текущей архитектуры static NAT считается **принципиально достаточным** механизмом source-NAT safety на managed VPN egress.

Основания:

- daemon управляет dedicated gateway host и явно владеет NAT-scope каждого managed VPN interface;
- каждый forwarded packet, реально покидающий managed VPN interface и имеющий non-local source, должен быть маскирован независимо от того, каким route он туда попал;
- MASQUERADE rule не требует знания readiness, peers или текущего набора VPN routes;
- отсутствие interface делает правило бездействующим, но не опасным;
- появление interface или foreign route не создаёт временного окна без NAT, потому что правило уже существует;
- исчезновение или изменение MASQUERADE является обычным fixed firewall/NAT drift и обнаруживается до route reconciliation.

Поэтому более сложная dynamic NAT model не даёт дополнительных safety guarantees для текущего use-case, но требует отдельного NAT runtime-state, ordering dependencies, remediation и дополнительных failure paths. Такая сложность сознательно не используется.

Это решение может быть пересмотрено только если изменится ownership model самого VPN egress interface, например появится поддерживаемый сценарий совместного использования одного interface трафиком, который **не должен** NAT'иться. В текущей архитектуре такой сценарий не поддерживается.

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
interface = "vpns0"
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
interface                    string, required
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

## 15. Имена интерфейсов

Формат/значение interface проверяется runtime только для managed definitions. `--check-config` lint'ит unmanaged definitions. Уникальность interface — runtime semantic constraint только managed set.

Используется намеренно более строгий контракт, чем допускает Linux kernel.

Разрешено:

```text
1..15 символов
первый символ: ASCII-буква
остальные: ASCII-буквы, цифры, _, ., -
```

Регулярное выражение:

```text
[A-Za-z][A-Za-z0-9_.-]{0,14}
```

Запрещённые имена:

```text
lo
any
default
all
```

Сравнение запрещённых имён — case-insensitive.

Символ `+` запрещён, в частности чтобы исключить wildcard-семантику интерфейсов в `iptables`.

## 16. VPN-сети и адреса

IPv4/CIDR и внутренние address/peer contracts проверяются runtime только для managed definitions. `--check-config` lint'ит те же contracts для unmanaged definitions как WARNING. Selection-dependent conflicts fatal только внутри managed set.

Для каждого VPN-профиля:

- `interface` обязан быть уникален среди managed-профилей; совпадение с unmanaged definition не влияет на startup и является lint warning в `--check-config`;
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

Если `peers = []` у managed-профиля, конфигурация остаётся валидной: profile VPN UNICAST routes не устанавливаются, а защищаемые `routes` остаются под blackhole. Постоянный MASQUERADE managed interface всё равно существует как fixed infrastructure.

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

Firewall, static NAT и blackhole не зависят от фактического состояния VPN-соединения.

VPN **UNICAST routes** привязаны к readiness соответствующего managed VPN-профиля.

Fixed NAT infrastructure существует для каждого managed-профиля от bootstrap до cleanup и от readiness не зависит.

Временный обрыв удалённой стороны не должен приводить к постоянному удалению/созданию fixed firewall/NAT rules.

Критерием готовности любого VPN-профиля является интерфейс + ожидаемый локальный адрес, а не connectivity или тип VPN-протокола.

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

## 23. Внутренняя модель Python-реализации

По умолчанию реализация должна оставаться в одном основном Python-файле:

```text
vpn-gatewayd.py
```

Это deployment/maintenance preference, а не абсолютный запрет на модули. Разбиение допускается только если размер или связность кода реально ухудшат аудит, развёртывание или сопровождение.


Этот раздел фиксирует форму модели данных, а не привязку архитектуры к конкретным Python-механизмам. Выбранные средства должны иметь прямое и простое соответствие будущим Rust `struct`/`enum` и immutable collections.

Структуры с заранее известными полями представляются через `@dataclass(slots=True)`.

Конфигурационные структуры дополнительно используют `frozen=True`.

Для фактической неизменяемости конфигурации:

- поля-коллекции имеют тип `tuple[...]`, а не `list[...]`;
- mapping VPN-профилей хранится через read-only `MappingProxyType`;
- mutable collections внутри immutable-конфига не допускаются.

Закрытые наборы состояний представляются через `Enum`.

Минимальный lifecycle enum:

```text
DaemonState:
    STARTING
    ACTIVE
    DEGRADED
    ISOLATED
    STOPPING
```

`DEGRADED` и `ISOLATED` допустимы только после успешного старта; стартовая ошибка приводит к завершению процесса, а не к переходу в одно из runtime degradation states.

`VpnGatewayDaemon` хранит lifecycle/orchestration state, immutable loaded config/profile objects и process-local runtime structures (ownership/diagnostic caches). `status` отдельно показывает фактический `ip_forward`; forwarding state не кодируется внутри `DaemonState`.

Runtime `GatewayConfig` является validated projection и содержит только managed typed profiles:

```text
vpns: Mapping[str, VpnProfileConfig]   # только managed profiles
```

Raw TOML/catalog definitions нужны только config loader и `--check-config` linter; daemon их не хранит после построения runtime projection. Это позволяет malformed unmanaged definition не влиять на runtime startup.

Минимальное lifecycle state хранится как `state: DaemonState`, но daemon также содержит immutable loaded config/profile objects и process-local runtime structures, описанные ниже.

Каждый managed VPN-профиль представлен отдельным runtime-объектом с собственной immutable-конфигурацией и runtime ownership state.

`VpnProfile` не применяет kernel-state самостоятельно. Он предоставляет daemon:

- immutable profile config;
- CONFIGURED resource sets, целиком выводимые из config и не зависящие от readiness;
- текущий OWNED resource state;
- atomic `update_owned_state(...)`.

Readiness, ACTUAL kernel-state и diagnostic overlap analysis являются daemon-scoped.

`VpnGatewayDaemon` является единственным orchestration owner reconciliation и единственным уровнем, который строит и применяет multi-profile kernel plan.

Работающий профиль хранит runtime inventory ресурсов, которые были успешно созданы текущим процессом. Этот inventory не является persistent state и теряется при завершении процесса.

Маршрут представлен самодостаточным immutable value-object. Владелец формирует ресурс полностью; kernel adapter не подставляет скрытые defaults.

```text
RouteType:
    UNICAST
    BLACKHOLE
    UNREACHABLE
    PROHIBIT
    THROW
```

`BLACKHOLE` не является отдельной сущностью вне routing model: blackhole guard — это обычный `RouteSpec` с `route_type=BLACKHOLE`. Благодаря этому ownership, plan, add/delete и verify используют ту же typed-модель маршрута.

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

`default` не является отдельным признаком: он однозначно представлен `destination = 0.0.0.0/0`.

`scope` сознательно не входит в `RouteSpec`: в текущей модели он не является частью desired identity и может нормализоваться kernel'ом.

Полный identity route в reconciliation определяется всем `RouteSpec`, а не только `destination`.


Daemon-level route plan представлен отдельным immutable typed value-object:

```python
@dataclass(slots=True, frozen=True)
class ReconciliationPlan:
    route_adds: frozenset[RouteSpec]
    route_deletes: frozenset[RouteSpec]
    route_replaces: frozenset[RouteSpec]
```

`ReconciliationPlan` не содержит итоговых profile results: они появляются только после apply/verify.

`route_replaces` выражает отдельную ownership-canonicalization operation: exact desired `RouteSpec` уже присутствует в ACTUAL, но отсутствует в process-local OWNED. Такая операция не кодируется как одновременный add+delete одного `RouteSpec`, потому что add/delete sets обязаны быть disjoint и имеют другую семантику.

Missing configured blackhole guards включаются в обычный `route_adds` как `RouteSpec(route_type=BLACKHOLE, proto=201, metric=65536, onlink=False)`. Отдельный тип операции для blackhole не нужен: blackhole — это обычный Linux route с типом `BLACKHOLE`, а не отдельный класс kernel-resource.

Runtime state профиля минимально содержит:

```text
owned_routes: set[RouteSpec]
```

Публичный runtime-контракт `VpnProfile` минимален. Профиль не имеет собственного reconciliation-метода и не выполняет kernel side effects.

Профиль предоставляет daemon только route resources:

```text
CONFIGURED routes
OWNED routes
update_owned_state(...)
```

Daemon строит runtime DESIRED routes из CONFIGURED + readiness.

Readiness используется при построении DESIRED, но daemon не просит профиль выполнять kernel side effects.

В рамках одного reconciliation pass daemon строит **один immutable `desired_routes_by_profile` snapshot** после чтения interface/address snapshot. Один и тот же объект/эквивалентный immutable snapshot используется `build -> validate -> apply -> verify`; readiness и DESIRED не пересчитываются между этими фазами.

Kernel add/delete, canonicalization exact-prefix routes, verify и commit ownership выполняет `VpnGatewayDaemon` через общий `KernelInterface`.

### 23.2. Subprocess route/address adapter

Debian 13 implementation `SubprocessKernelInterface` использует iproute2 JSON как
машинный inventory boundary:

```text
ip -j -N -4 route show table main
ip -j -4 addr show
```

Для route inventory опция `-N` обязательна: protocol/scope identifiers выводятся
численно и adapter не зависит от локальных `rt_protos` aliases. Нормализация route
snapshot выполняется детерминированно:

- `default` -> `0.0.0.0/0`;
- bare IPv4 destination -> `/32`;
- отсутствующий route type -> `UNICAST`;
- отсутствующий `protocol` -> `RTPROT_BOOT = 3` (iproute2 штатно может не печатать boot);
- `flags[]` содержит `onlink` -> `RouteSpec.onlink=True`.

Текущий `RouteSpec` является single-next-hop model. Поэтому route entries с
`nexthops`, `nhid`, multipath representation или structured/cross-family `via`
не пропускаются молча: inventory завершается `KernelError`. Неполный ACTUAL snapshot
опаснее отказа reconciliation, потому что может привести к ошибочной authoritative
canonicalization.

Route mutations материализуются только в IPv4 main table и всегда задают представленные
`RouteSpec` поля явно:

```text
ip -4 route {add|del|replace} TYPE PREFIX table main proto N [metric M] [via A] [dev IF] [onlink]
```

`proto=None` не материализуется через скрытый iproute2 default и считается
`KernelError`.

Address inventory использует `addr_info[].local`, а не peer/broadcast fields, поэтому
туннельные и point-to-point interfaces интерпретируются по локальному адресу.
Существующий interface без IPv4 остаётся в mapping с пустым `frozenset`; отсутствие
ключа означает отсутствие interface.

Итоговый ownership передаётся профилю только после verify соответствующего reconciliation результата. Предпочтительно обновлять ownership профиля как единый runtime-state commit, а не мутировать `owned_*` по ходу отдельных kernel-операций.

`reported_route_overlaps` хранится на уровне `VpnGatewayDaemon` как `dict[str, frozenset[RouteSpec]]`, потому что overlaps вычисляются из общего kernel snapshot и используются только для edge-triggered INFO-логирования. Каждый per-profile фрагмент `reported_route_overlaps` заменяется целиком после анализа.

Для runtime reconciliation различаются три множества:

```text
desired  -> что должно существовать по текущему immutable config и readiness
owned    -> что текущий процесс считает созданным им
actual   -> что реально существует в kernel-state
```

daemon reconciliation всегда перечитывает фактический kernel-state; runtime inventory не заменяет проверку `actual`, а используется для определения ownership.

Разрешённые действия:

```text
desired - actual  -> создать недостающее
owned - desired   -> удалить лишнее собственное
owned - actual    -> убрать из runtime inventory
```

### 23.1. Routing ownership policy

Для routing policy `vpn-gatewayd` является authoritative только для exact destination prefixes managed-профилей, перечисленных в их `profile.routes`.

Для каждого exact protected prefix:

```text
desired owned RouteSpec                                      -> keep
owned non-desired on exact protected prefix                    -> delete
foreign non-desired on exact protected prefix                  -> delete
exact desired but not owned                                    -> replace/canonicalize, then verify as owned
configured blackhole guard (BLACKHOLE, proto 201, metric 65536,
onlink=False)                                                   -> keep if owned+present, add if missing,
                                                                  replace if present but not owned
```

На exact protected prefix coexistence с competing routes не допускается: daemon приводит routing table к собственной канонической конфигурации.

Это является явным исключением из общего правила «не удалять чужие маршруты».

Исключение из authoritative canonicalization: daemon никогда не удаляет и не replace'ит `proto kernel` route. Exact protected prefix, совпадающий с host connected `proto kernel` route в main IPv4 table, приводит к fatal startup error через initial `_validate_plan()`, который запрещает `route_delete`/`route_replace` для `proto kernel`.

More-specific и less-specific маршруты, пересекающиеся с `profile.routes`, не входят в authoritative ownership и автоматически не удаляются.

`0.0.0.0/0` не считается overlap и не журналируется как overlap.

Fail-closed для protected address space обеспечивается не только blackhole, но и профильной FORWARD policy: ACCEPT требует `-o profile.interface`, а затем любой оставшийся трафик к `profile.routes` получает REJECT. Поэтому чужой overlapping route через другой egress interface не может увести protected traffic в обход VPN.

Чужой overlapping route через тот же `profile.interface` не считается утечкой через обычную сеть; daemon его не удаляет автоматически, но диагностирует как overlap.

Такие пересечения отслеживаются только диагностически. Для каждого обнаруженного overlap демон журналирует INFO один раз при появлении и INFO один раз при исчезновении. Пока overlap остаётся неизменным, повторные periodic reconciliation не должны засорять journal одинаковыми сообщениями.

Для подавления повторных INFO daemon хранит неперсистентный runtime cache, например:

```text
reported_route_overlaps: dict[str, frozenset[RouteSpec]]
```

Этот cache влияет только на логирование и не является источником истины для reconciliation.

После restart cache пуст; существующие overlaps будут заново залогированы INFO один раз. Это сознательное поведение: новый процесс должен сообщить актуальные overlaps.

Runtime ownership commit выполняется только после verify. Отдельная успешная kernel-операция сама по себе не является основанием для изменения `OWNED`.

Netlink listener существует в единственном экземпляре и принадлежит `VpnGatewayDaemon`. Демон получает событие, по уникальному имени интерфейса определяет затронутый профиль и инициирует daemon-level reconciliation. Per-profile Netlink sockets не используются.

Все runtime-события (`Netlink`, periodic reconciliation, IPC, shutdown) сериализуются одним event loop `VpnGatewayDaemon`. Одновременно выполняется не более одного reconciliation plan; параллельные kernel-операции разных или одного профиля не допускаются.

Periodic reconciliation timer также существует в единственном экземпляре и принадлежит `VpnGatewayDaemon`; профили собственных таймеров и reconciliation loops не создают.

Daemon reconciliation сам вычисляет readiness всех managed-профилей из единого interface/address snapshot. Отдельного `is_ready()`/readiness-запроса к профилю нет.

`ResourceState` больше не используется: после переноса `ACTUAL` и readiness на уровень daemon
абстракция `DESIRED/OWNED` через enum не даёт пользы.

`VpnProfile` предоставляет единый read API для двух локальных наборов ресурсов:

```python
class ProfileResourceSet(Enum):
    CONFIGURED = auto()
    OWNED = auto()
```

```python
def _list_routes(
    self,
    source: ProfileResourceSet,
) -> frozenset[RouteSpec]:
    ...
```

`CONFIGURED` строится только из immutable profile config и не читает kernel-state.

Для routes `CONFIGURED` включает оба вида ресурсов:

```text
BLACKHOLE guard для каждого profile.routes prefix
+
UNICAST route для каждого profile.routes × peers
```

При `peers=[]` configured BLACKHOLE guards всё равно существуют, а UNICAST routes отсутствуют.

`OWNED` читает runtime route ownership текущего процесса и включает blackhole guards на тех же основаниях, что и остальные routes: история операций текущего процесса + последний выполненный verify.

Изменение ownership выполняется отдельно:

```python
def update_owned_state(
    self,
    *,
    routes: set[RouteSpec] | frozenset[RouteSpec],
) -> None:
    ...
```

`update_owned_state()` атомарно заменяет route ownership после daemon verify и делает defensive copy входного `routes` set.

`OWNED` означает ресурсы, ownership которых текущий процесс может обоснованно подтвердить своей историей операций и последним выполненным verify. Между verify текущее ownership считается непрерывным; kernel actual-state само по себе не является достаточным основанием для adoption.

Readiness не является состоянием `VpnProfile`. Его вычисляет `VpnGatewayDaemon` по общему interface/address snapshot.

Runtime DESIRED строится по типу configured resource:

```text
configured BLACKHOLE routes -> DESIRED всегда
configured UNICAST routes   -> DESIRED только если profile ready
```

Сам профиль про readiness не знает.

`ACTUAL` намеренно отсутствует в `ProfileResourceSet`: фактическое kernel-state является daemon-scoped snapshot. Это тонкая boundary-прослойка между предметной моделью и Linux kernel/userspace tools.

Контракт `KernelInterface` логически делится на две части.

Runtime reconciliation:

```text
list_routes() -> set[RouteSpec]
add_route(RouteSpec)
delete_route(RouteSpec)
replace_route(RouteSpec)

list_interface_ipv4() -> Mapping[str, frozenset[IPv4Address]]
```

Bootstrap/cleanup/firewall boundary также обязан покрывать:

```text
read/write net.ipv4.ip_forward
inventory daemon-owned firewall chains/jumps/rules
atomic apply/repair daemon-owned firewall infrastructure
exact cleanup daemon-owned firewall infrastructure
marker-based inventory/cleanup owned routes
```

Точная форма firewall API/value-object'ов определяется на implementation/research phase. Универсальный firewall AST заранее не вводится; concrete adapter не должен скрывать daemon firewall policy или подставлять неявные policy defaults.

`list_interface_ipv4()` возвращает все существующие интерфейсы. Интерфейс без IPv4 присутствует в mapping с пустым `frozenset()`. Отсутствие ключа означает, что интерфейс не существует.

`KernelInterface`:

- не хранит authoritative cache kernel-state;
- не знает про `CONFIGURED / OWNED / DESIRED`;
- не принимает policy-решений;
- только читает фактическое состояние и выполняет конкретные kernel/userspace-операции;
- может хранить только технические ресурсы реализации, например открытый Netlink socket.

Все предметно обрабатываемые ошибки `KernelInterface` наследуются от:

```python
class KernelError(Exception):
    pass
```

Специализированные подклассы вводятся только по мере реализации конкретных физических методов, когда действительно требуется различать причины ошибки.

Один экземпляр `KernelInterface` принадлежит `VpnGatewayDaemon`.

Глобальные read-операции kernel-state выполняет daemon. В частности:

```python
all_kernel_routes = kernel.list_routes()

related_kernel_routes = daemon._routes_for_profile(
    profile,
    all_kernel_routes,
)
```

`related_kernel_routes` включает exact protected prefixes, их competing exact routes, relevant blackhole guards и more-/less-specific overlaps; `0.0.0.0/0` не включается как overlap.

NAT не имеет отдельного runtime snapshot API: fixed NAT chains/rules читаются и verify'ятся вместе с firewall infrastructure.

`VpnProfile` не инициирует глобальный `list_routes()` самостоятельно. `KernelInterface.list_routes()` возвращает полный нормализованный snapshot основной IPv4 routing table; для целевого gateway-хоста стоимость такого snapshot считается приемлемой.

Конкретные add/delete операции также выполняет daemon через `KernelInterface` согласно заранее построенному plan.

`VpnGatewayDaemon` предоставляет общий helper:

```text
effective_sources(profile)
```

который вычисляет `common_allowed_sources ∪ profile.allowed_sources` и возвращает детерминированный immutable tuple без точных дублей.

Фактическое состояние интерфейсов, маршрутов, NAT, firewall и blackhole не кэшируется как второй источник истины: при необходимости оно сверяется с kernel-state.

Результат применения runtime-state профиля также представлен закрытым enum:

```text
ApplyStateResult:
    SUCCESS
    FAIL
```

Profile result aggregation остаётся простым (`all SUCCESS` / `any non-SUCCESS`), но сам `DaemonState` определяется шире:

```text
firewall != SAFE                         -> ISOLATED
firewall == SAFE
  AND all managed profiles == SUCCESS
  AND ip_forward == 1                    -> ACTIVE
firewall == SAFE, остальные случаи       -> DEGRADED
```

Причины runtime-состояний имеют стабильные машинные коды `Enum` и отдельный immutable каталог человекочитаемых описаний:

```text
RuntimeReasonCode
ERROR_CODE -> "Long human-readable description"
```

Конкретный факт представлен typed value-object:

```python
@dataclass(slots=True, frozen=True)
class DiagnosticFact:
    code: RuntimeReasonCode
    detail: str | None
```

`code` является стабильной machine identity причины и участвует в edge-triggered reason signature/dedupe. `detail` предназначен только для human-readable диагностики (например, текст `KernelError`) и **не определяет identity причины**.

`ProfileResult` не дублирует profile ID внутри value-object: identity задаётся ключом полного mapping `profile_id -> ProfileResult`. После completed verify набор ключей этого mapping обязан точно совпадать с managed profile set. `SUCCESS` не несёт reason; `FAIL` обязан иметь `DiagnosticFact`.

Для `FirewallCheck` состояния `UNSAFE`/`UNKNOWN` сопровождаются `DiagnosticFact`; `SAFE` не требует причины. Expected inventory/canonical-parse failure даёт `UNKNOWN` с соответствующим reason code. Значение `FirewallCheck(UNSAFE|UNKNOWN, reason=None)` невалидно; `FirewallCheck(SAFE, reason!=None)` также невалидно.

Активный набор `degraded_reasons` в памяти не хранится. Конкретные причины runtime-сбоев журналируются по итоговой reason signature pass; `state = DEGRADED` отражает только факт неполного последнего reconciliation.


## 24. Implementation notes, уже зафиксированные архитектурой

- Route/address inventory следует читать через JSON output `ip -j`, а не через fragile text parsing.
- Именованные route protocol values из `ip -j` нормализуются adapter'ом в numeric kernel protocol ID; в частности `kernel` = `RTPROT_KERNEL` = `2`.
- `ip -j route` destination нормализуется: `default` -> `0.0.0.0/0`, bare host address без prefix -> `/32`. Поэтому `RouteSpec.proto` остаётся `int | None`.
- При разборе interface addresses для point-to-point/tun semantics используется поле `local`, а не peer-oriented `address`.
- Route flags, влияющие на identity/materialization, включая `onlink`, должны отражаться в `RouteSpec`.
- Firewall apply/repair выполняется через `iptables-restore --noflush`; atomicity существует per table/`COMMIT`, но не между `filter` и `nat`. Cleanup формирует точные удаления daemon-owned resources без global flush.
- **EXP-001 (2026-11-07) завершён PASS** на Debian 13.7 / kernel 6.12.115+deb13.1 / iptables 1.8.11 `nf_tables`: три materialization одного payload и `iptables-save -> restore -> save` дали идентичный canonical comparison view после удаления только comment lines/blank lines. Полный протокол и artifacts: `vpn-gateway-experiments.md`, EXP-001.
- EXP-001 показал, что исходный restore payload не равен canonical save text: backend детерминированно переупорядочивает chain declarations/rules и некоторые rule options. Поэтому direct comparison `restore payload == iptables-save stdout` запрещён.
- Runtime firewall inventory остаётся **memory-only**: `iptables-save` читается из stdout в память; `iptables-restore` получает generated payload через stdin. Временные rules-файлы не используются.
- `_compare_fixed_firewall_nat()` использует минимальный structural parser/extractor `iptables-save`: tables, chain declarations, ordered chain contents и позиции/uniqueness daemon jumps. Для individual rule strings используется canonical syntax, выдаваемый `iptables-save`; semantic universal firewall AST/normalizer для протестированного backend не требуется.
- Expected comparison state и restore payload выводятся из одной policy model; implementation не должна поддерживать два независимых источника истины. Если future backend создаёт ранее неизвестную canonicalization, невозможность надёжно сравнить state -> `UNKNOWN`, после чего требуется новый эксперимент перед расширением parser/normalizer.
- Netfilter change notifications (`NETLINK_NETFILTER` / nftables groups) являются optional implementation enhancement; базовая correctness не зависит от них.
- Repair-storm/latching policy относится к implementation/research. Не вводить произвольные N/M thresholds до стендовых измерений; конфликтующий внешний firewall manager считается административной ошибкой выделенного gateway.
- Все subprocess-вызовы имеют bounded timeout; применимые iptables operations используют ограниченный `-w`. Adapter задаёт `LC_ALL=C`/`LANG=C`, а `KernelError` сохраняет argv/return code/stderr/timeout context без превращения human stderr в machine reason identity.
- Final reconciliation log severity отражает **текущее функциональное состояние**: `ISOLATED` -> ERROR; `DEGRADED` с `ip_forward` OFF/unknown -> ERROR; `DEGRADED` с confirmed ON -> WARNING; clean `ACTIVE` -> INFO; `ACTIVE` после полностью закрытого incident -> WARNING + `recovered from: ...`.
- `recovered from:` используется только после финального `ACTIVE`. Firewall drift, успешно repair'нутый в этом pass, является recovered incident даже если best-effort `ip_forward=0` не дал отдельной ошибки.
- `ip_forward` управляется read-before-write: daemon сначала читает текущее значение и пишет только при расхождении. Если на чистом SAFE pass обнаружен неожиданный `ip_forward=0` и daemon успешно восстановил `1`, это recovered incident (`FORWARDING_RESTORED`) и итоговый ACTIVE pass логируется WARNING. Если OFF был выставлен самим daemon из-за уже зафиксированного firewall incident, отдельный `FORWARDING_RESTORED` не дублирует исходную причину.
- Edge-triggered dedupe строится по stable `RuntimeReasonCode`/state/resource identity; свободный human-readable exception text не должен менять machine reason signature.
- При `Type=notify` + `WatchdogSec=N` event loop обязан просыпаться и посылать `WATCHDOG=1` чаще, чем раз в `N/2`, даже при полном отсутствии внешних событий. Timeout ожидания event loop должен учитывать watchdog deadline.
- Минимальные stdlib `unittest` state-machine tests обязательны до kernel implementation: SAFE/all-success; SAFE/profile route FAIL; UNKNOWN; UNSAFE/repair-success; `set_ip_forward(True)` failure; managed `peers=[]`; ISOLATED -> DEGRADED/ACTIVE transitions.
- Firewall tests отдельно покрывают исчезновение/изменение MASQUERADE: fixed firewall/NAT verify должен дать UNSAFE, repair обязан восстановить правило до route reconciliation.
- Route-plan tests отдельно покрывают **exact** conflict: managed protected prefix точно совпадает с main-table connected `proto kernel` route -> initial `_validate_plan()` fatal. More-specific/less-specific overlap этим тестом не считается fatal.
- State-machine tests покрывают полный recovery path: `ISOLATED -> firewall/NAT repair -> fresh route pass с profile FAIL -> ip_forward=1 -> DEGRADED -> последующий успешный pass -> ACTIVE`.
- Lifecycle tests покрывают `SIGTERM` во время каждой startup phase, особенно после успешного `APPLY`/`ip_forward=1` и до `READY=1`; ожидается cleanup и отсутствие RUN.
- Signal tests подтверждают, что `SIGHUP` не завершает daemon, а wakeup fd немедленно будит blocking event loop при `SIGTERM`/`SIGINT`.
- `ip_forward` tests покрывают read-before-write и восстановление неожиданного external `0`: successful restore логируется как recovered incident, но OFF, выставленный daemon из-за firewall drift, не создаёт дублирующий recovery reason.
- Logging tests покрывают periodic reminder неизменившегося WARNING/ERROR и отсутствие periodic повторов clean INFO.
- Config tests отдельно покрывают `managed_vpns`, malformed unmanaged definition (startup игнорирует, `--check-config` WARNING), managed `peers=[]` (`NOTE`, exit 0), managed route <-> managed transport-network overlap (ERROR), те же conflicts с unmanaged definition (WARNING), и duplicate normalization set-like lists.
- Config security tests покрывают regular-file requirement, запрет final symlink, root ownership и отсутствие group/other write у config file и его parent.
- Netlink events coalesce/debounce внутри единого event loop; конкретное debounce window определяется стендовыми тестами.
- Emergency `VPNG-PANIC` first-rule DROP для случая «sysctl write unavailable, firewall operational» оставлен как implementation/research option на случай необходимости усиления fail-closed.
- Runtime recovery из `DEGRADED` повторяется на каждом configured reconciliation tick; отдельный exponential backoff не является обязательной архитектурной политикой.
- Runtime logging остаётся edge-triggered для INFO. Для неизменившегося WARNING/ERROR допускается periodic reminder; RC2.1 фиксирует default не чаще одного повторного сообщения примерно раз в 5 минут, чтобы длительный DEGRADED/ISOLATED не исчезал из operational visibility и при этом не спамил каждый tick.

## 25. Открытые решения

Следующие implementation-level детали ещё требуют отдельного подтверждения:

1. Точный формат и минимальный набор IPC-команд.
2. Конкретный механизм единого сериализованного event loop; сама семантика сериализации уже зафиксирована.
3. Точный механизм full resync после Netlink `ENOBUFS`.
4. Финальный systemd privilege model: отдельный service user + минимальные capabilities/permissions предпочтительнее root, если стенд подтвердит достаточность; `geteuid()==0` не является runtime contract.



### Возможное будущее развитие: controlled reverse accessibility

Текущая архитектура намеренно однонаправленная: managed VPN profiles используются для доступа **из локальной стороны к remote protected routes**; новый ingress из managed VPN interfaces блокируется `VPNG-INGRESS`.

В будущем может понадобиться отдельная opt-in модель обратной доступности: для конкретного VPN-профиля явно перечислять локальные подсети/сервисы, к которым разрешён доступ **с удалённой стороны через VPN**.

Если такая возможность появится, она должна проектироваться как отдельная policy axis, а не как ослабление текущего `VPNG-INGRESS` по умолчанию. Вероятная форма — per-profile allow-list локальных destinations с отдельными INPUT/FORWARD rules, независимой validation и явным fail-closed default.

Это **не является частью текущей RC2.3 архитектуры**, не влияет на текущий config schema и не должно учитываться при реализации первой версии daemon.

## 26. Ключевые инварианты

К реализации относятся как обязательные следующие инварианты:

```text
1. Один процесс владеет всеми ресурсами VPN Gateway.

2. Конфигурация читается ровно один раз за жизнь процесса.

3. Изменение конфигурации применяется только restart'ом сервиса.

4. Новый старт всегда начинается с cleanup().

5. cleanup() не зависит от текущего конфига и persistent state.

6. Каждый создаваемый kernel-resource имеет однозначный ownership marker.

7. Blackhole routes имеют proto 201 и metric 65536.

8. VPN routes имеют proto 202.

9. Каждый managed-профиль имеет собственные chains VPNG-<PROFILE>-INPUT,
   VPNG-<PROFILE>-FORWARD и VPNG-<PROFILE>-NAT.

10. INPUT/NAT jumps managed-профилей образуют contiguous blocks с позиции 1;
    FORWARD имеет VPNG-INGRESS на позиции 1, VPNG-RESERVED на позиции 2,
    затем contiguous block managed profile FORWARD jumps.

11. cleanup() либо подтверждает полную чистоту, либо возвращает fatal error.

12. apply() выполняется только после успешного cleanup() и runtime config validation; initial route plan проходит `_validate_plan()` до новых route side effects.

13. ip_forward=1 включается самым последним после успешного apply().

14. Каждый managed profile INPUT/FORWARD/NAT jump существует ровно один раз и является plain `-j`; глобальные VPNG-INGRESS/VPNG-RESERVED jumps также существуют ровно по одному.

15. Fail2ban может находиться раньше только как отдельный nftables hook,
    не меняющий позицию VPNG-* внутри iptables chains.

16. VPN connectivity не является условием существования firewall и blackhole.

17. VPN routes зависят только от наличия ожидаемого интерфейса
    и ожидаемого локального IPv4-адреса.

18. Никаких hidden fallback, degraded startup или молчаливого игнорирования
    неизвестной конфигурации.

19. Никаких сторонних Python-зависимостей.

20. Любые пересечения protected routes managed-профилей запрещены; exact duplicates внутри одного профиля нормализуются как set-like redundancy.

21. После потери Netlink-событий выполняется full reconciliation.

22. --check-config никогда не изменяет kernel-state.

23. vpn-gatewayd рассчитан на выделенный gateway host и эксклюзивно управляет ip_forward.

24. Конфигурационный файл принадлежит root и не writable для group/other.

25. vpn.network не может быть /32; минимально допустимый prefix — /31.

26. Network/broadcast addresses внутри vpn.network могут использоваться
    как обычные tunnel addresses.

27. Partial state после failed apply() не откатывается отдельно и
    очищается следующим cleanup().

28. После входа в RUN полный apply() по Netlink-событиям не вызывается.

29. Runtime reconciliation управляет desired proto-202 routes managed-профиля и,
    в authoritative exact-route scope, может удалять competing foreign routes с тем же exact destination.
    MASQUERADE является fixed firewall/NAT infrastructure.

30. Runtime profile/route reconciliation failure при SAFE fixed firewall/NAT не останавливает
    сервис автоматически: сервис переходит в DEGRADED и сохраняет работоспособные ресурсы.

31. Firewall safety failure переводит daemon в ISOLATED. DEGRADED и ISOLATED существуют
    только после успешного старта; дальнейшие reconciliation passes продолжают recovery.

32. Managed profile NAT jumps образуют непрерывный префикс POSTROUTING с позиции 1 и следуют в детерминированном порядке profile ID.

33. Неканонические CIDR в allowed_sources являются ошибкой; молчаливое
    расширение сети запрещено.

34. Пустой peers у managed-профиля допустим; proto-202 routes отсутствуют, но fixed MASQUERADE managed interface остаётся установленным.

35. vpn-gatewayd не знает VPN-протоколы; он работает только с именованными
    профилями interface/network/local address/peers/routes/allowed_sources.

36. Runtime отслеживает только profiles из `managed_vpns`; остальные `[vpn.*]` являются unmanaged definitions без kernel resources.

37. Каждый managed protected route принадлежит ровно одному managed-профилю; managed routes образуют глобально непересекающееся пространство.

38. Эффективный ACL профиля равен common_allowed_sources плюс его собственный
    allowed_sources; deny/exclude-семантика отсутствует.

39. Имя vpn-профиля соответствует [A-Za-z][A-Za-z0-9_-]{0,14}.

40. Закрытые runtime-состояния и коды ошибок представлены Enum;
    человекочитаемые тексты отделены от машинных кодов.

41. Immutable config использует tuple для последовательностей и read-only
    MappingProxyType для mapping профилей; mutable collections запрещены.

42. Причины DEGRADED не хранятся как runtime-набор: ошибки журналируются,
    а state хранит только текущее состояние жизненного цикла.

43. Profile ID уникален case-insensitive, имеет длину 1..15 и соответствует
    [A-Za-z][A-Za-z0-9_-]{0,14}.

44. Interface каждого managed-профиля уникален внутри managed runtime set; conflicts с unmanaged definitions являются lint warnings.

45. ACL применяется к source + destination routes конкретного профиля;
    ACL одного профиля не даёт доступ к routes другого.

46. Профили и их jumps обрабатываются в детерминированном порядке,
    независимом от порядка секций TOML.

47. `managed_vpns` после нормализации обязан содержать как минимум один существующий profile ID; отдельная проверка общего числа definitions не требуется.

48. NAT chains/jumps/MASQUERADE создаются как fixed infrastructure только для managed profiles и не меняются до cleanup, кроме repair после drift.

49. Весь новый трафик, пришедший с interface профиля, REJECT'ится независимо
    от destination; разрешается только ESTABLISHED,RELATED.

50. DaemonState = STARTING, ACTIVE, DEGRADED, ISOLATED, STOPPING;
    DEGRADED и ISOLATED не являются допустимыми результатами старта.

51. Итоговый порядок jumps соответствует возрастающей сортировке profile ID,
    независимо от механики вставки правил.

52. Отдельного LAN_IF в модели нет; FORWARD ACL применяется по source +
    destination route независимо от физического входного не-VPN интерфейса.

53. effective_sources(profile) = common_allowed_sources ∪ profile.allowed_sources,
    с удалением только точных дублей и сохранением разрешённых пересечений.

54. INPUT не использует effective_sources; профильный ACL относится только
    к FORWARD.

55. Внутри профильной FORWARD-chain ingress с собственного VPN interface
    классифицируется раньше destination ACL.

56. Netlink events неизвестных интерфейсов игнорируются без warning.

57. Managed profile results агрегируются как all SUCCESS / any non-SUCCESS, но DaemonState также
    зависит от firewall safety и фактического ip_forward: non-SAFE -> ISOLATED;
    SAFE + all managed SUCCESS + ip_forward=1 -> ACTIVE; остальные SAFE cases -> DEGRADED.

58. FORWARD начинается с `VPNG-INGRESS`, затем `VPNG-RESERVED`, затем managed profile FORWARD jumps. `VPNG-RESERVED` REJECT'ит destination в managed transport networks.

59. INPUT сначала DROP'ит INVALID, затем ACCEPT'ит ESTABLISHED,RELATED,
    затем разрешает NEW из profile.network к profile.local_address.

60. Netlink listener существует в одном экземпляре и принадлежит daemon;
    профили не создают собственных Netlink sockets.

61. Порядок peers в TOML задаёт route priority: metric 10, 20, 30...;
    динамическая проверка доступности peer не выполняется.

62. Работающий daemon хранит неперсистентный runtime inventory успешно
    созданных им ресурсов; после restart ownership восстанавливается не из
    памяти, а через глобальный marker-based cleanup.

63. Kernel actual-state читается daemon из единого snapshot; profile runtime inventory
    не считается источником фактического kernel-state.

64. Periodic reconciliation инициируется одним timer в VpnGatewayDaemon;
    профили не имеют собственных timers или reconciliation loops.

65. Ресурс `actual ∩ desired`, отсутствующий в `owned`, не присваивается silent.
    Для exact destination из `profile.routes` применяется authoritative canonicalization:
    plan содержит `route_replaces` для canonical desired RouteSpec; ownership появляется
    только после successful materialization + verify/commit.

66. Runtime inventory профиля commit'ится daemon только после kernel apply + verify
    соответствующего reconciliation результата.

67. Все runtime-события daemon сериализуются одним event loop; одновременно
    выполняется не более одного reconciliation plan.

68. Для ресурсов вне authoritative exact-route scope обнаруженный ownership conflict
    приводит к profile result FAIL и daemon DEGRADED; silent adoption запрещён.
    Для exact routes из profile.routes действует canonicalization по инварианту 65.

69. reconcile_interval является top-level float в секундах, default 10.0,
    допустимый диапазон 1.0..60.0; periodic reconciliation нельзя отключить
    значением 0.

70. Readiness участвует в построении DESIRED profile state; профиль не выполняет
    самостоятельный kernel reconciliation.

71. vpn-gatewayd authoritative только для exact destination prefixes из profile.routes;
    foreign routes с тем же exact destination удаляются.

72. More-specific и less-specific overlapping routes автоматически не удаляются.

73. Route overlaps журналируются edge-triggered: INFO один раз при появлении и
    INFO один раз при исчезновении; повторные reconciliation при неизменном overlap
    не создают повторных INFO.

74. Runtime cache overlap-состояния используется только для подавления логов и
    не влияет на desired/owned/actual reconciliation.

75. Профильный FORWARD ACCEPT для managed protected destination требует `-o profile.interface`; оставшийся трафик к profile.routes REJECT'ится.

76. Exact destination prefixes из profile.routes являются authoritative routing scope:
    competing foreign routes с тем же exact destination удаляются; при необходимости
    создаётся канонический desired RouteSpec.

77. `0.0.0.0/0` не считается route overlap для diagnostic logging.

78. После restart overlap-log cache пуст; существующие overlaps журналируются заново
    одним INFO на overlap.

79. RouteSpec является самодостаточным immutable value-object и включает destination,
    route_type, via, interface, metric, proto и onlink; kernel adapter не подставляет скрытые defaults.

80. default route представляется как destination 0.0.0.0/0; отдельный default-флаг
    отсутствует.

81. scope не входит в RouteSpec и не участвует в route identity текущей модели.

82. reported_route_overlaps хранится в VpnGatewayDaemon как profile-keyed immutable snapshot cache (`dict[str, frozenset[RouteSpec]]`) и используется только для подавления повторных INFO. Daemon заменяет snapshot целиком после каждого overlap-analysis pass.

83. Собственный blackhole guard определяется полным marker'ом proto 201 + metric 65536;
    foreign blackhole на exact protected prefix не защищён этим исключением.

84. VpnProfile использует ProfileResourceSet(CONFIGURED/OWNED) для единого read API;
    ACTUAL и readiness являются daemon-scoped.

85. KernelInterface не хранит authoritative kernel-state и является thin boundary
    к Linux kernel/userspace tools; readiness snapshot читается через list_interface_ipv4().

86. Все предметно обрабатываемые ошибки KernelInterface наследуются от KernelError;
    специализированные подклассы вводятся только по фактической необходимости.

87. Один экземпляр KernelInterface принадлежит VpnGatewayDaemon. Глобальные
    list/read операции kernel-state выполняет daemon; профили не инициируют их сами.

88. Основная Python-реализация по умолчанию остаётся в одном vpn-gatewayd.py;
    разбиение на модули допускается только при реальном ухудшении поддерживаемости.

89. NAT не имеет отдельного runtime value-object: MASQUERADE является fixed config-derived firewall rule; concrete firewall builder не подставляет скрытые policy defaults.

90. Runtime reconciliation выполняется daemon по фазам:
    fixed firewall/NAT verify/repair -> только при SAFE fresh snapshot(routes + interfaces) ->
    derive readiness/DESIRED -> build route plan -> validate -> apply -> verify -> commit OWNED.
    После isolation ip_forward возвращается только после завершённого fresh route pass.

91. VpnProfile не имеет публичного apply_state() и не выполняет kernel side effects.

92. Итоговый OWNED сообщается профилям daemon'ом только после verify. До первой mutation
    daemon проверяет, что `owned_routes_by_profile` содержит ровно весь managed profile key set;
    partial mapping приводит к ReconciliationError и не изменяет ни один profile OWNED.
    Входные routes sets копируются defensively.

93. Один fresh route/interface snapshot и один immutable desired_routes_by_profile snapshot
    используются согласованно всеми build/validate/verify фазами одного reconciliation pass;
    readiness/DESIRED внутри pass повторно не вычисляются.

94. `_routes_for_profile(profile, all_kernel_routes)` формирует related_kernel_routes
    из общего snapshot; профиль не читает глобальную routing table самостоятельно.

95. Readiness вычисляется VpnGatewayDaemon из единого interface/address snapshot;
    VpnProfile не выполняет kernel readiness queries.

96. ReconciliationPlan является immutable typed route-plan и содержит только
    route_adds/route_deletes/route_replaces.

97. Plan validation failure на startup является fatal; в runtime plan не применяется
    и daemon переходит в DEGRADED.

98. Bootstrap и runtime используют один route reconciliation engine. Fixed firewall/NAT policy
    устанавливается bootstrap'ом и снимается cleanup'ом; runtime verification repair'ит drift.
    BLACKHOLE guards входят в shared route engine и восстанавливаются runtime reconciliation.

99. Completed verify возвращает полный mapping ровно по всем managed-профилям;
    partial/empty result считается incomplete pass (`ReconciliationError`). Успешные профили
    не теряют подтверждённый OWNED из-за FAIL другого профиля.

100. Отдельного NAT runtime-state/snapshot API нет: fixed profile NAT chains и MASQUERADE verify'ятся как часть fixed firewall/NAT infrastructure.

101. ProfileResourceSet содержит только CONFIGURED и OWNED; ACTUAL в него не входит.

102. `_list_routes()` возвращает immutable frozenset snapshot CONFIGURED/OWNED routes.

103. Runtime reconciliation обеспечивает наличие configured blackhole guards, но не
     перестраивает blackhole policy динамически.

104. list_interface_ipv4() возвращает все существующие interfaces; interface без IPv4
     представлен пустым frozenset, отсутствие ключа означает отсутствие interface.

105. Profile предоставляет CONFIGURED/OWNED; runtime DESIRED строит daemon из CONFIGURED
     + readiness.

106. OWNED подтверждается историей операций текущего процесса и последним выполненным verify;
     actual kernel-state само по себе не даёт права на adoption.

107. onlink является частью RouteSpec identity и задаётся владельцем явно.

108. Missing blackhole guards представлены обычными RouteSpec в route_adds; executor
     применяет их раньше остальных route operations. Canonical guard, уже присутствующий
     в ACTUAL, но не OWNED, выражается через route_replaces.

109. BLACKHOLE является обычным RouteType; отдельный BlackholeOperation/resource type
     не вводится.

110. Если configured blackhole guard профиля отсутствует после verify, FAIL получает
     именно этот профиль; остальные профили не fail'ятся автоматически.

111. reported_route_overlaps хранится как dict[str, frozenset[RouteSpec]] и заменяется
     snapshot'ом целиком после overlap analysis.

112. Значимые поля value-object'ов, влияющие на identity/materialization/policy,
     по возможности задаются явно; неявных defaults следует избегать.

113. NAT/route dependency executor не нужен: fixed MASQUERADE verified как infrastructure до runtime route operations и удаляется только cleanup'ом.

114. Fixed firewall/NAT infrastructure проверяется в начале каждого reconciliation pass, до route/interface snapshot.
     UNSAFE и UNKNOWN требуют best-effort ip_forward=0; UNKNOWN не repair'ится вслепую.

115. Daemon никогда не удаляет и не replace'ит `proto kernel` route; exact protected-prefix
     conflict с host connected route является fatal initial-plan validation conflict.

116. Profile FORWARD отбрасывает INVALID для protected destination + expected VPN egress
     до разрешающих ACCEPT.

117. Shared reconciliation engine не меняет lifecycle state; bootstrap/runtime wrappers
     интерпретируют его result/error по-разному.

118. После fixed firewall/NAT SAFE runtime route plan строится по fresh routes/interfaces snapshot.

119. После fixed firewall/NAT SAFE route `KernelError`, `PlanValidationError` и `ReconciliationError`
     приводят к DEGRADED; fixed-infrastructure safety failures классифицируются отдельно как ISOLATED.
     Без завершённого verify последний подтверждённый OWNED не заменяется.

120. CONFIGURED routes включают BLACKHOLE guards и UNICAST peer routes; runtime DESIRED всегда
     сохраняет configured BLACKHOLE, readiness gating применяется только к UNICAST routes.
     Static NAT от readiness не зависит.

121. Blackhole guards входят в OWNED на общих основаниях.

122. Config security validation проверяет root ownership и отсутствие group/other write
     как у TOML-файла, так и у `/etc/vpn-gateway`.

123. KernelInterface охватывает runtime reconciliation и bootstrap/cleanup/firewall side effects;
     конкретная firewall API/value-object форма определяется при реализации без скрытой policy.

124. Именованные kernel route protocols нормализуются adapter'ом в numeric protocol IDs;
     `RTPROT_KERNEL` представлен как `proto=2`.

125. ISOLATED является отдельным runtime lifecycle state: fixed firewall/NAT safety не подтверждена,
     daemon остаётся жив и продолжает recovery attempts; требуемый ip_forward=0.

126. Ошибка set_ip_forward(False) во время UNSAFE firewall не завершает daemon и не блокирует
     repair: filter/nat всё равно восстанавливаются и verify'ятся; ошибка остаётся high-severity
     фактом pass.

127. После firewall/NAT repair forwarding возвращается только после SAFE fixed infrastructure и завершённого fresh route reconciliation/verify pass.

128. Source-NAT safety обеспечивается fixed verified MASQUERADE каждого managed egress interface; отдельный per-profile NAT safety predicate не требуется.

129. Отдельный NAT-remediation route plan не используется; исчезновение/изменение MASQUERADE является firewall/NAT drift и repair'ится до route reconciliation.

130. FAIL отдельного managed-профиля при SAFE fixed firewall/NAT не блокирует forwarding остальных; profile route failures остаются fail-closed через BLACKHOLE/FORWARD policy.

131. ACTIVE требует fixed firewall/NAT SAFE + all managed profiles SUCCESS + ip_forward=1. Ошибка включения
     forwarding при остальном SUCCESS даёт DEGRADED/forwarding-off, не ACTIVE.

132. DaemonState и фактический forwarding state являются ортогональными operational axes;
     status показывает lifecycle state и фактический ip_forward. Daemon является exclusive owner net.ipv4.ip_forward.

133. Если после firewall/NAT repair не получен fresh route/interface snapshot или не завершён route verify,
     forwarding остаётся выключенным до следующего завершённого fresh route pass.

134. iptables-restore не считается cross-table atomic transaction; normal repair выполняется
     при ip_forward=0, но отказ sysctl не запрещает repair: filter восстанавливается раньше nat,
     а невозможность подтвердить fail-closed isolation журналируется отдельно.

135. Firewall safety/result logging выполняется один раз на reconciliation pass по итоговой
     reason signature, а не внутри отдельных шагов проверки/ремонта. Machine identity signature
     строится по stable RuntimeReasonCode/state/resource identity, а не по свободному exception text.

136. Netlink events coalesce/debounce перед full reconciliation; subprocess calls имеют
     bounded timeout, чтобы serialized event loop не зависал бесконечно.

137. Route executor ставит missing BLACKHOLE guards раньше ordinary route operations; NAT operations в route plan отсутствуют.

138. `managed_vpns` отделяет catalog definitions от runtime-managed profiles; list order не задаёт priority.

139. Runtime semantic conflicts проверяются только внутри managed set. `--check-config` lint'ит unmanaged definitions и cross-conflicts involving unmanaged как WARNING.

140. Managed protected routes не могут пересекаться ни с одной managed `vpn.network`; transport networks предназначены только для tunnel local/peer addresses.

141. Exact duplicates в set-like lists (`managed_vpns`, routes внутри одного профиля, ACL lists) нормализуются runtime; `--check-config` может выдать lint warning. `peers` остаётся order-significant; duplicate peers является definition error.

142. Fixed firewall verification полностью проверяет filter и NAT chains, включая постоянный MASQUERADE каждого managed-профиля.

143. Отдельной NAT remediation phase нет: fixed NAT drift относится к firewall repair; route reconciliation остаётся одним typed plan/pass.

144. Отдельной preflight-фазы нет: cleanup отвечает за owned orphaned resources, а initial `_validate_plan()` — за unreconcilable route conflicts.

145. Bootstrap не имеет отдельного blackhole installer: shared route engine materializes missing BLACKHOLE RouteSpec первой executor-фазой.

146. Новая runtime validation rule добавляется только с явной целью однозначно построить managed projection либо защитить managed runtime safety; проблемы только unmanaged definitions относятся к offline lint.

147. `VPNG-RESERVED` является fixed managed firewall policy: FORWARD к любой managed transport `vpn.network` REJECT'ится до profile destination ACL.

148. MASQUERADE является частью fixed firewall/NAT template и verify'ится вместе с остальной owned infrastructure; его drift классифицируется как `UNSAFE` до route reconciliation.

149. Static NAT считается принципиально достаточным для current managed egress ownership model:
     MASQUERADE каждого managed interface существует от bootstrap до cleanup, не зависит от readiness/peers
     и его drift является fixed firewall/NAT UNSAFE.

150. `peers=[]` в managed profile является валидным состоянием и даёт `--check-config` NOTE,
     а не WARNING/ERROR; UNICAST routes не создаются, BLACKHOLE guards и static NAT остаются.

151. Reverse accessibility с remote VPN side к локальным сетям не входит в текущую архитектуру;
     возможное будущее расширение должно быть explicit opt-in policy с fail-closed default.

152. Failure `set_ip_forward(False)` никогда сам по себе не завершает daemon:
     при `UNSAFE` repair продолжается; при `UNKNOWN` daemon остаётся ISOLATED без blind repair.
     В обоих случаях sysctl failure является high-severity fact текущего pass.

153. Expected failure firewall inventory/canonical parse/normalization классифицируется как UNKNOWN
     с stable RuntimeReasonCode; blind repair запрещён. Programming exceptions не скрываются широким catch.

154. ProfileResult identity задаётся ключом полного `profile_id -> ProfileResult` mapping;
     value-object не дублирует profile ID. Completed pass обязан вернуть ровно managed profile key set;
     SUCCESS не имеет reason, FAIL обязан иметь DiagnosticFact.

155. Final log severity отражает current functional state: ISOLATED и DEGRADED без confirmed
     forwarding -> ERROR; DEGRADED с forwarding ON -> WARNING; clean ACTIVE -> INFO;
     ACTIVE после recovered incident -> WARNING с `recovered from:`.

156. `DiagnosticFact.detail` не входит в machine identity/dedupe причины; machine identity
     задаётся stable RuntimeReasonCode. Firewall drift, успешно восстановленный до ACTIVE,
     считается recovered incident pass.

157. Firewall inventory/materialization не использует временные rules-файлы:
     `iptables-save` -> stdout/memory, generated `iptables-restore` payload -> stdin/memory.

158. EXP-001 подтверждает стабильный canonical `iptables-save` rule representation для протестированного
     Debian 13/iptables-nft backend после удаления comments/blank lines. Direct comparison restore payload
     с save output запрещён; daemon использует minimal structural parser/extractor + canonical rule strings.

159. Signal handlers устанавливаются до startup phases. SIGTERM/SIGINT только взводят shutdown flag;
     startup проверяет его на phase boundaries, а после APPLY до RUN обязательно выполняет cleanup при shutdown.

160. SIGHUP не завершает daemon и не инициирует reload; blocking event loop использует signal wakeup fd
     или семантически эквивалентный mechanism для немедленного graceful shutdown.

161. `/run/vpn-gateway` создаётся deployment'ом как private runtime directory; lock failure из-за уже
     удерживаемого flock диагностируется как explicit "another instance is running".

162. `ip_forward` изменяется read-before-write. Неожиданный OFF, восстановленный на clean SAFE pass,
     является recovered incident; OFF, намеренно установленный daemon для isolation, не создаёт
     дублирующий recovery reason.

163. Невозможность подтвердить firewall safety не разрешает retry при продолжающемся forwarding:
     сначала best-effort `ip_forward=0`, затем diagnosis/retry/recovery.

164. Архитектура не требует root EUID. Deployment должен стремиться к минимальным privileges/capabilities,
     сохраняя root-owned non-writable config/path security contract.

165. Неизменившиеся WARNING/ERROR outcomes периодически напоминаются с bounded interval (default около 5 минут);
     clean INFO остаётся purely edge-triggered.


166. Final config path component обязан быть regular file и проверяется через `lstat`; symlink
     запрещён, чтобы path-security parent directory нельзя было обойти redirect'ом на target
     с иными replacement permissions.


167. `route_replaces` является активной authoritative materialization operation, а не silent adoption:
     RouteSpec должен одновременно принадлежать current DESIRED и ACTUAL, отсутствовать в OWNED,
     а ownership фиксируется только после verify/commit.

168. route_adds, route_deletes и route_replaces попарно disjoint. `proto kernel` запрещён
     как в route_deletes, так и в route_replaces.

169. Route executor применяет missing BLACKHOLE adds до потенциально разрушающих операций;
     затем competing exact deletes, authoritative replaces и остальные adds.

170. Main IPv4 route inventory выполняется через `ip -j -N -4 route show table main`;
     adapter нормализует default/bare-host destinations и отсутствующий RTPROT_BOOT в numeric `proto=3`.

171. Route form, которую текущий single-next-hop `RouteSpec` не может представить
     (multipath/nexthops/nhid/structured cross-family via), приводит к `KernelError`;
     silent omission из ACTUAL запрещён.

172. Route add/delete/replace явно работают с `table main` и materialize'ят все поля,
     представленные `RouteSpec`; `proto=None` не заменяется скрытым iproute2 default.

173. Interface IPv4 inventory использует `ip -j -4 addr show` и `addr_info[].local`;
     существующий interface без IPv4 возвращается как empty frozenset.

```
