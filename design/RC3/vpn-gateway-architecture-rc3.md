# VPN Gateway — архитектурные решения и инварианты

**Статус:** принят к реализации
**Версия:** RC3
**Дата:** 2026-11-10

Документ фиксирует принятые архитектурные решения проекта VPN Gateway. Он описывает обязательные инварианты, жизненный цикл сервиса, модель владения состоянием ядра и правила конфигурации. Нереализованные детали, которые еще требуют отдельного решения, вынесены в раздел **«Открытые решения»**.

Нормативная терминология проекта определена в [«Терминах и определениях»](terms-and-definitions.md).

## 1. Назначение

VPN Gateway — локальный IPv4-шлюз, который:

- направляет заданные сети через один или несколько VPN-профилей;
- не зависит от конкретной VPN-реализации;
- применяет собственную фильтрацию `INPUT`/`FORWARD`;
- применяет NAT;
- использует защитные blackhole-маршруты для отказа с запретом;
- отслеживает появление и исчезновение VPN-интерфейсов через Netlink.

Конфигурация содержит именованные VPN-профили. В исполнение попадают только профили с
`enabled=true` (значение по умолчанию); профиль с `enabled=false` отбрасывается до
разбора его содержимого. Верхнеуровневый `enabled=false` отключает gateway целиком:
после startup cleanup daemon не разбирает профили, не materialize сетевые ресурсы и
оставляет `ip_forward=0`. Автоматического failover между разными профилями нет;
primary/secondary/fallback bindings одного routing profile задаются внутри его `bindings[]`.

IPv6-маршрутизация проектом не поддерживается.

## 2. Общие принципы

### 2.1. Жесткий отказ

При ошибке очистки, проверки или применения конфигурации сервис не переходит в частично
рабочее состояние.

Ошибка при запуске означает:

- `ip_forward` не включается;
- новая конфигурация не считается примененной;
- процесс завершается с ненулевым кодом;
- systemd переводит сервис в `failed`.

Startup error никогда не маскируется переходом в `DEGRADED`: ошибка очистки,
конфигурации, обязательной проверки или применения приводит к жесткому отказу.

Недоступность VPN path при однозначном binding state не является startup error. Если
fail-closed desired state полностью применено и проверено, daemon может успешно завершить
startup и впервые войти в `RUN` как `DEGRADED`. Таким образом, после успешного startup
первым рабочим состоянием может быть `ACTIVE` или `DEGRADED`; `failed` означает
именно неуспешный startup.

### 2.2. Отказ с запретом

Защищаемый трафик не должен при отказе VPN или ошибке конфигурации уходить через обычный
маршрут по умолчанию.

Blackhole-маршруты являются одним из защитных механизмов и устанавливаются до разрешения
пересылки.

Blackhole обеспечивает отказ с запретом на уровне выбора маршрута для соответствующего
префикса. Он не является универсальной гарантией доставки и не заменяет независимую
фильтрацию `FORWARD`.

### 2.3. Один владелец сетевого состояния

Один долгоживущий процесс `vpn-gatewayd` является единственным владельцем ресурсов
проекта:

- daemon-owned firewall;
- blackhole-маршрутов;
- VPN-маршрутов;
- NAT;
- `net.ipv4.ip_forward`.

IPv6-пересылка не относится к управляемым ресурсам daemon: для него действует отдельное
обязательное условие среды (§2.6).

Внешние скрипты и административные клиенты не должны самостоятельно изменять эти ресурсы.

`vpn-gatewayd` предназначен для выделенного хоста VPN-шлюза. Совмещение с Docker,
Kubernetes, другими сервисами-шлюзами или компонентами, которым требуется
`net.ipv4.ip_forward=1`, не поддерживается.

Эксклюзивное владение глобальным `net.ipv4.ip_forward` и эксклюзивная ответственность за
окончательное решение для всего IPv4-трафика `FORWARD` являются двумя связанными
архитектурными обязательствами daemon. Пока `ip_forward=1`, в **проверенном требуемом
состоянии** каждый пересылаемый IPv4-пакет обязан получить окончательное решение внутри
daemon-owned префикса правил; пакет не должен доходить до сторонних правил или встроенной
политики `FORWARD ACCEPT`.

В проверенном состоянии daemon-owned префикс физически начинается с позиции 1, а сторонние
правила `FORWARD` сохраняются после `VPNG-FORWARD-DENY` и поэтому недостижимы при
включенной пересылке.

Рассогласование daemon-owned firewall/NAT классифицируется по области влияния.

Если подтвержденное рассогласование ограничено только `INPUT`-частью таблицы `filter`,
оно не влияет на транзитный путь `FORWARD` и восстанавливается точечно: daemon одной
транзакцией возвращает свою `INPUT`-политику в требуемое состояние и проверяет результат,
не изменяя `ip_forward`, `FORWARD`, NAT или маршруты.

Штатные изменения binding-specific ресурсов выполняются локальными процедурами `ADD`
и `REMOVE` (§8.6) без глобального выключения forwarding. Рассогласование `FORWARD`
или NAT, состояние `UNKNOWN`, ошибка локальной процедуры либо случай, когда изменение
нельзя безопасно представить как `ADD`/`REMOVE`, используют глобальную процедуру
`INIT/PANIC` (§8.6).

До следующего цикла согласования после внешнего изменения существует окно реакции.
Постоянное конкурентное переписывание daemon-owned ресурсов внешним менеджером остается
неподдерживаемой конфигурацией.

После `cleanup()` daemon-owned переходы и цепочки исчезают, а `ip_forward=0`; базовая
фильтрация хоста снова полностью принадлежит администратору.

`net.ipv4.ip_forward` находится под исключительным управлением daemon. Ручное изменение
sysctl не является постоянной административной паузой или переопределением и будет
приведено daemon к требуемому значению на следующем завершенном цикле согласования.

### 2.4. Никакого скрытого fallback на старую конфигурацию

Конфигурация читается только при запуске процесса.

Изменения применяются только через:

```bash
systemctl restart vpn-gateway.service
```

`reload-config` отсутствует.

После изменения файла допустимы только два состояния:

1. сервис успешно запустился с новой конфигурацией;
2. сервис не запустился и находится в `failed`.

Работа на старой конфигурации при уже измененном файле не допускается.

### 2.5. Никаких сторонних Python-зависимостей

Python-реализация использует только:

- стандартную библиотеку Python;
- штатные системные утилиты Debian 13.

Запрещены:

- `pip`;
- PyPI;
- `apt install python3-*` ради дополнительных библиотек.

Python рассматривается как промежуточная реализация; архитектура должна оставаться
пригодной для последующего переноса на Rust.

### 2.6. IPv6-пересылка и IPv6 на управляемых VPN-интерфейсах

VPN Gateway управляет только IPv4 и не строит политику фильтрации или маршрутизации для
IPv6. Поэтому фактическая IPv6-пересылка на хосте должна быть отключена, а IPv6 на
управляемых VPN-интерфейсах — выключен.

Для целевой системы Debian 13 / Linux 6.12 до чтения snapshot интерфейсов daemon обязан
проверить глобальные обязательные условия хоста:

```text
net.ipv6.conf.all.forwarding       = 0
net.ipv6.conf.default.forwarding   = 0
net.ipv6.conf.default.disable_ipv6 = 1
```

Эти значения читаются непосредственно как sysctl и не требуют знания имен интерфейсов.

В Linux 6.12 `net.ipv6.conf.<interface>.forwarding` задает режим
хоста/маршрутизатора интерфейса, но не является независимым разрешением фактической
IPv6-пересылки при `net.ipv6.conf.all.forwarding=0`. Поэтому для целевой системы не
требуется проверять `forwarding` каждого существующего интерфейса.

После чтения snapshot интерфейсов и адресов daemon обязан проверить
`disable_ipv6=1` для **каждого** уже существующего интерфейса, попадающего в защитное
пространство имен хотя бы одного управляемого селектора:

```text
net.ipv6.conf.<interface>.disable_ipv6 = 1
```

Проверяется именно защитное пространство имен, а не только множество active bindings.
Для каждого exact BindingSpec проверяется его exact name; для prefix BindingSpec —
весь textual prefix, закрываемый deny-only правилом `-i prefix+`. Только после этой
проверки строятся candidates, active bindings и policy.

Значение `default.disable_ipv6=1` обеспечивает выключенный IPv6 для создаваемых позднее
интерфейсов по умолчанию.

Если будущее поддерживаемое ядро предоставляет отдельный механизм для конкретного
интерфейса, который может разрешить фактическую IPv6-пересылку при
`all.forwarding=0` (например, `force_forwarding` или эквивалент), daemon после чтения
snapshot обязан подтвердить, что такие переопределения выключены для всех существующих
совпадающих интерфейсов, а до snapshot — что выключено соответствующее значение по
умолчанию для новых интерфейсов, если ядро его предоставляет.

Daemon не изменяет перечисленные IPv6 sysctl: они являются обязательными условиями
конфигурации выделенного доверенного хоста. Несоответствие при запуске является фатальной
ошибкой до любых действий, которые могут разрешить IPv4-пересылку.

Все перечисленные IPv6-условия должны сохраняться и во время `RUN`. Каждый полный
reconciliation pass после свежей interface inventory и **до построения allowing policy**
повторно проверяет глобальные IPv6 prerequisites и `disable_ipv6=1` для всех текущих
interfaces guard namespaces.

Нарушение во время `RUN` является host-prerequisite breach: daemon не исправляет IPv6
sysctl, не продолжает ordinary materialization, best-effort выключает IPv4 forwarding и
применяет config-derived isolation filter, если состояние filter читаемо, после чего
остается `ISOLATED` с high-severity diagnostic до исправления хоста и restart.

`ISOLATED` при этом описывает только управляемое daemon IPv4-состояние и **не является
гарантией IPv6 protection**, потому что daemon не владеет IPv6 firewall/forwarding.
Оператор обязан устранить prerequisite violation; автоматическое возвращение в
`ACTIVE` после такого нарушения без restart не поддерживается.

## 3. Процессная модель

Основной компонент:

```text
vpn-gatewayd
```

Это постоянно работающий процесс под управлением systemd.

Он:

- читает и проверяет конфигурацию;
- хранит разобранную конфигурацию в памяти;
- отслеживает состояние VPN-интерфейсов управляемых профилей;
- применяет фильтрацию;
- применяет blackhole-маршруты;
- применяет VPN-маршруты;
- применяет NAT;
- управляет пересылкой IPv4;
- выполняет полную очистку своих ресурсов при запуске и штатном завершении.

Отдельный событийный `vpn-monitor` после перехода на эту архитектуру не требуется.

Daemon пишет обычные текстовые сообщения в `stderr`; при запуске под systemd они попадают
в journal. Структурированное логирование/JSON не требуется.



## 4. Мониторинг VPN-интерфейсов и привязки во время исполнения

Сервис реагирует как минимум на `RTM_NEWLINK`, `RTM_DELLINK`, `RTM_NEWADDR` и
`RTM_DELADDR`. Netlink-событие является только wakeup hint; решение всегда выводится
из заново прочитанного полного snapshot. При `ENOBUFS` и периодически по
`reconcile_interval` выполняется полная пересверка.

### 4.1. BindingSpec и защитное пространство имен

Enabled profile содержит непустой ordered `bindings[]`. Каждый элемент — отдельный
`BindingSpec`:

```text
BindingSpec:
    interface = exact-name | prefix+
    network   = canonical IPv4 CIDR
```

Пример:

```toml
bindings = [
    { interface = "wg0",    network = "172.20.126.0/29" },
    { interface = "wg1",    network = "172.20.127.0/29" },
    { interface = "ocvpn+", network = "172.20.130.0/29" },
]
```

`network` является свойством конкретного BindingSpec, а не профиля. Поэтому один
routing profile может объединять independent VPN interfaces с разными transport
address spaces.

Поле `interface` BindingSpec имеет только две формы:

- exact: `wg0`;
- textual prefix: `ocvpn+`.

Старая форма «массив exact names как один selector» отсутствует: ordered
`bindings[]` полностью заменяет её.

Каждый enabled BindingSpec резервирует selector namespace для deny-only firewall guard.
Selector namespaces **всех enabled BindingSpec** попарно не пересекаются, в том числе
между profiles. Поэтому любой kernel interface может принадлежать не более чем одному
enabled BindingSpec.

Завершающий `+` использует подтвержденную EXP-005 textual-prefix семантику iptables.
`%`, glob и regex не поддерживаются.

Selector никогда не используется как разрешающее условие `ACCEPT`, NAT или route.
Разрешающие ресурсы всегда содержат exact interface name active concrete binding.

### 4.2. Инвентаризация и concrete identity

Один snapshot интерфейсов сохраняет как минимум:

```text
name
ifindex
IPv4 local addresses
```

Point-to-point remote endpoint может сохраняться для диагностики, но не участвует в
binding applicability, route derivation или transport-peer association. EXP-009 показал,
что transport peer не является универсальной Linux route-next-hop abstraction.

Идентичность concrete binding:

```text
ConcreteBinding = exact name + ifindex
```

Повторное создание того же имени с новым ifindex является новой concrete binding.
Если один inventory содержит одно exact name с несовместимыми ifindex, snapshot
некорректен; daemon не выбирает запись произвольно.

### 4.3. Candidates, applicability и active order

Candidate определяется конкретным BindingSpec:

- exact BindingSpec дает существующий interface с этим exact name;
- prefix BindingSpec дает все существующие interfaces с textual prefix.

Candidate становится active concrete binding только если на нем есть хотя бы один
local IPv4 address, принадлежащий **network owning BindingSpec**.

Candidate без подходящего local IPv4:

- остается видимым в status вместе с owning BindingSpec;
- не получает binding-specific `ACCEPT`, NAT или `proto 202` route;
- остается закрыт selector guard.

Это явная trust boundary: daemon не доказывает происхождение адреса. Администратор и
transport configuration обязаны не назначать address из BindingSpec.network постороннему
interface внутри selector namespace этого BindingSpec.

`operstate`, `LOWER_UP`, ping, handshake, transport peer и endpoint reachability не
являются binding truth.

Profile-level order active bindings состоит из двух классов:

1. active exact bindings — в порядке exact BindingSpec в config, игнорируя prefix entries;
2. active prefix bindings — в process-local порядке первого принятия текущим daemon.

Для prefix класса непрерывно active binding сохраняет relative order. Новая binding
добавляется в конец, исчезнувшая удаляется без перестановки survivors. Если несколько
новых prefix bindings впервые обнаружены в одном snapshot, они принимаются в порядке
interface inventory этого snapshot; дополнительная сортировка имен запрещена.

Этот порядок используется для binding-specific firewall/NAT/status serialization.
Появление exact binding может вставить ее block в fixed exact position без удаления или
повторного создания survivor blocks. Prefix order диагностический и не является
route-priority contract.

### 4.4. Метрики и materialization маршрутов

Для каждого protected destination профиля всегда существует config-derived BLACKHOLE.

Для каждого active concrete binding materialize direct UNICAST route:

```text
destination = profile.route
via         = None
interface   = active_binding.name
proto       = 202
onlink      = false
```

Общие constants:

```text
FIRST_UNICAST_METRIC = 10
ROUTE_METRIC_STEP    = 10
BLACKHOLE_METRIC     = 65536
0 < UNICAST metric < BLACKHOLE_METRIC
```

Пусть `E` — количество **exact BindingSpec** профиля. Exact rank — позиция exact entry
среди exact entries, а не абсолютная позиция в `bindings[]`.

```text
exact_metric(rank) = FIRST_UNICAST_METRIC + rank * ROUTE_METRIC_STEP
rank = 0 .. E-1
```

Отсутствующий exact interface не сдвигает metrics следующих exact BindingSpec.
Повторное создание exact name с новым ifindex получает ту же config-derived metric:
это обеспечивает failback к fixed primary/secondary priority.

Все prefix BindingSpec профиля используют **один общий dynamic allocator**:

```text
dynamic_metric_min =
    FIRST_UNICAST_METRIC + E * ROUTE_METRIC_STEP
```

Следовательно все exact routes профиля имеют меньшую metric, чем любой dynamic prefix
route. Положение prefix entry внутри `bindings[]` route priority не задает.

Dynamic allocator рассматривает только значения:

```text
dynamic_metric_min + N * ROUTE_METRIC_STEP < BLACKHOLE_METRIC
```

и работает циклически:

1. непрерывно active prefix binding сохраняет metric;
2. исчезнувшая binding освобождает metric только после verified-state commit;
3. новая prefix binding получает следующее свободное значение от cursor;
4. занятые значения пропускаются;
5. при верхней границе поиск возвращается к `dynamic_metric_min`;
6. ранняя свободная «дырка» не заполняется специально;
7. полный цикл без свободного slot завершает snapshot projection ошибкой;
8. same-name/new-ifindex prefix binding является новой и проходит обычное allocation;
9. allocator mapping/cursor process-local и после restart строятся заново.

При текущих constants существует 6553 допустимых UNICAST slots: 10..65530.
Если профиль содержит хотя бы один prefix BindingSpec, config validation должна оставить
минимум один dynamic slot. Если prefix BindingSpec нет, exact BindingSpec могут занимать
все допустимые slots.

Появление/исчезновение prefix binding не переметрирует exact routes и prefix survivors.
Порядок перечисления RouteSpec не является desired semantics и не вызывает churn.

Provisional allocator mapping/cursor входит в immutable reconciliation snapshot, но
process-local state меняется только после successful verification.

EXP-009 подтверждает direct-`dev` routing для OpenConnect и WireGuard. WireGuard peer
selection внутри одного WG interface принадлежит `AllowedIPs`; VPN-GATE не реализует
failover между peers одного interface. Управляемый VPN-GATE failover/failback строится
из нескольких independent concrete interfaces/BindingSpec.

### 4.5. Смена привязок и остаточное окно реакции

Policy-changing transition возникает при появлении/исчезновении active concrete binding,
same-name/new-ifindex replacement или изменении address membership относительно owning
BindingSpec.network.

Штатный transition раскладывается на локальные `ADD`/`REMOVE` §8.6; replacement —
`REMOVE old -> ADD new`. Exact binding возвращается со своей config-derived metric.
Prefix binding проходит dynamic allocation.

Candidate-only change без изменения active resources не требует глобальной процедуры
после successful IPv6 prerequisite verification.

Selector guard существует из config независимо от активности candidate. Exact active
blocks выполняются раньше guard; prefix syntax разрешен только в deny-only guard rules.

Между kernel event и reconciliation остается остаточное окно реакции. Потерянное событие
компенсируется периодической пересверкой. Threat model неизменен: недоверенные процессы
не имеют `CAP_NET_ADMIN`; interface lifecycle принадлежит доверенному VPN-ПО, ядру и
администратору.

## 5. Жизненный цикл сервиса


### 5.1. Запуск

Базовая модель:

```text
START -> LOCK -> CLEANUP -> LOAD TOP-LEVEL ENVELOPE
```

После cleanup TOML syntactically parses и читается top-level `enabled`.

Если `enabled=false`:

- profile bodies не разбираются и не валидируются;
- daemon не materialize firewall/NAT/routes;
- `ip_forward` остается 0;
- daemon входит в штатное состояние `DISABLED` и может сообщить READY;
- изменение режима требует restart, как и любое изменение config.

Если `enabled=true`:

```text
PARSE ENABLED PROFILES
  -> VALIDATE
  -> BUILD SNAPSHOT
  -> APPLY FAIL-CLOSED STATE
  -> VERIFY
  -> COMMIT
  -> ip_forward=1
  -> ACTIVE | DEGRADED
```

Startup error до завершенного verified apply оставляет `ip_forward=0` и завершает
процесс ненулевым кодом. Verified zero-path profile не является startup error:
структурно корректный fail-closed state commit-ится и дает `DEGRADED`.

### 5.2. Runtime-каталог и блокировка экземпляра

Runtime-каталог по умолчанию:

```text
/run/vpn-gateway
```

Файл блокировки, удерживаемой в течение всего времени жизни процесса, по умолчанию:

```text
/run/vpn-gateway/vpn-gatewayd.lock
```

Перед открытием файла блокировки daemon безопасно создает при необходимости и проверяет
runtime-каталог:

- последний компонент пути не должен быть символической ссылкой;
- существующий объект обязан быть каталогом;
- режим доступа обязан быть `0700`;
- владелец обязан совпадать с ожидаемой учетной записью сервиса для текущего способа
  развертывания;
- если каталог отсутствует и процесс имеет право его создать, он создается с режимом
  `0700`;
- неправильные владелец или режим существующего каталога не исправляются молча через
  `chmod`/`chown`, а считаются фатальной ошибкой.

При текущем запуске от root ожидаемый владелец — UID 0. При будущем запуске systemd от
отдельного служебного пользователя ожидается владелец, соответствующий этой учетной записи.

Файл блокировки открывается с `O_NOFOLLOW`, режимом `0600`; daemon удерживает эксклюзивную
блокировку `flock` в течение всего времени жизни процесса, а попытка ее получения выполняется
без ожидания. Занятая блокировка
диагностируется отдельной ошибкой о том, что другой экземпляр уже запущен.

Отдельный настраиваемый общий путь блокировки не вводится без реального сценария
одновременного запуска нескольких экземпляров.

### 5.3. Штатное завершение и сигналы

Обработчики сигналов `SIGTERM`/`SIGINT` устанавливаются **до первой фазы запуска**.
Обработчик не выполняет операций с ядром и только устанавливает признак завершения.

Во время `STARTING` этот признак проверяется на границах фаз:

```text
установить обработчики сигналов
  ↓
LOCK
  ↓ контрольная точка
CLEANUP
  ↓ контрольная точка
LOAD + VALIDATE CONFIG
  ↓ контрольная точка
APPLY
  ↓ контрольная точка
RUN
```

Если сигнал пришел до получения блокировки экземпляра, процесс выходит без очистки: он
еще не владеет ресурсами шлюза.

Если сигнал пришел после получения блокировки:

- завершить текущую ограниченную по времени фазу;
- на ближайшей границе не начинать следующую;
- если завершенная фаза могла создать состояние в ядре (`APPLY`), выполнить
  универсальную `cleanup()`;
- если после уже успешной начальной `cleanup()` запуск еще не создавал состояние в ядре,
  дополнительная очистка не обязательна;
- выйти без перехода в `RUN`.

Критическая контрольная точка существует после успешного `APPLY` и **до перехода в `RUN`**.
Если используется `Type=notify`, она также находится до отправки `READY=1`: сигнал в окне
после `ip_forward=1` не должен оставлять управляемую daemon'ом пересылку без очистки.

После входа в `RUN`:

```text
SIGTERM/SIGINT
 ↓
признак завершения + пробуждение сериализованного цикла обработки событий
 ↓
CLEANUP
 ↓
EXIT
```

Для пробуждения блокирующего цикла обработки событий обработчик сигнала использует
`signal.set_wakeup_fd()` или эквивалент self-pipe, чтобы штатное завершение не ожидало
периодического тайм-аута.

`SIGHUP` игнорируется: перезагрузка конфигурации архитектурой не предусмотрена, журнал
пишется в `stderr`/systemd journal, а повторное открытие файлов по HUP не требуется.

Если финальная `cleanup()` не смогла подтвердить полную очистку, процесс завершается с
ошибкой.

Для развертывания под systemd предпочтителен `Type=notify` с `WatchdogSec`, если
реализация поддерживает `sd_notify`. Это не меняет семантику жизненного цикла: `READY=1`
может отправляться только после успешного `APPLY` и прохождения последней контрольной точки,
а сторожевой таймер подтверждает живость сериализованного цикла обработки событий.

### 5.4. Рекомендации по развертыванию

Рекомендуемая конфигурация systemd:

```text
RuntimeDirectory=vpn-gateway
RuntimeDirectoryMode=0700
Restart=on-failure
RestartSec=<bounded delay>
StartLimitIntervalSec=<bounded window>
StartLimitBurst=<bounded count>
ExecStopPost=<страховочное отключение ip_forward>
```

`RuntimeDirectory` остается предпочтительным способом развертывания и особенно важен при
будущей работе не от root. Но корректность автономного daemon не зависит от systemd: если
процесс имеет право создать runtime-каталог, он делает это сам и затем применяет ту же
проверку безопасности.

`ExecStopPost` является вторичным механизмом отказа с запретом на случай `SIGKILL`,
тайм-аута сторожевого таймера или аварии процесса, когда Python-очистка физически не выполнилась.
Ошибка этого страховочного механизма не заменяет очистку daemon и не маскируется как
успешная очистка.

Развертывание не должно постоянно задавать `net.ipv4.ip_forward=1` через `sysctl.d`.
Во время исполнения этим sysctl управляет `vpn-gatewayd`.

Другие средства управления фильтрацией могут иметь собственные правила `INPUT`/`OUTPUT`
и физически сохраняемые правила `FORWARD`, но пока daemon включает пересылку, его
окончательный префикс `FORWARD` имеет приоритет. Конфигурация, в которой внешний сервис
постоянно переписывает пространство имен `VPNG-*` или переходы daemon-owned префикса,
не поддерживается.

Архитектура не требует `geteuid()==0`. Предпочтительно сохранить возможность работы от
отдельного служебного пользователя с минимальным набором Linux capabilities и файловых разрешений, если
практическое развертывание подтвердит их достаточность. Контракт безопасности конфигурации
и путей остается под контролем root.

## 6. Универсальная очистка

`cleanup()` не зависит от текущей конфигурации и от состояния daemon, сохраняемого между запусками. Она используется
перед загрузкой конфигурации при запуске, после аварийного предыдущего запуска и при
штатном завершении.

Успешная очистка означает отсутствие всех ресурсов VPN Gateway, определяемых по маркерам
владения, и `ip_forward=0`.

### 6.1. Маркеры владения

Принятые маркеры:

```text
blackhole routes -> proto 201 + type BLACKHOLE + metric 65536
VPN routes       -> proto 202
iptables chains  -> reserved namespace VPNG-*
owned jumps      -> jumps с target VPNG-*
```

Префикс `VPNG-` целиком зарезервирован daemon'ом в используемых таблицах iptables.

### 6.2. Инвентаризация маршрутов для очистки

Не зависящая от конфигурации очистка **не читает полный snapshot основной таблицы
маршрутизации**.

Для поиска маршрутов по маркерам владения используются выборочные запросы:

```text
ip -j -N -4 route show table main proto 202
ip -j -N -4 route show table main proto 201
```

EXP-004.5 подтвердил, что такие запросы не затрагивают несвязанные сторонние
multipath-маршруты.

При запросе с фильтром по протоколу iproute2 может не печатать поле `protocol`; адаптер
назначает известный протокол из контекста запроса. Для `proto 201` очистка дополнительно
требует `type=BLACKHOLE` и `metric=65536`.

Строгая полная `list_routes()` сохраняется для обычного согласования и по-прежнему
считает ошибкой непредставимые формы multipath/nhid, а не пропускает их молча.

### 6.3. Порядок очистки

1. по схеме «прочитать перед записью» привести `ip_forward` к 0 и **подтвердить**
   результат;
2. только после подтвержденного `ip_forward=0` выполнить выборочную инвентаризацию и
   удалить `proto 202`;
3. прочитать состояние firewall/NAT и удалить daemon-owned переходы/цепочки точным
   набором правил очистки;
4. только после успешной очистки firewall/NAT снова выполнить выборочную инвентаризацию и
   удалить daemon-owned маршруты `proto 201 type BLACKHOLE metric 65536`;
5. новая выборочная инвентаризация маршрутов и фильтрации должна подтвердить полную чистоту.

Подтвержденное `ip_forward=0` является защитным барьером очистки. Если daemon не смог
привести значение к 0 или подтвердить его чтением, очистка немедленно завершается ошибкой и
**не переходит к разрушительным операциям** над фильтрацией, NAT или маршрутами. Сохранение
старой запрещающей политики и blackhole в этом случае безопаснее частичного демонтажа при
возможно продолжающейся пересылке.

EXP-004.4 подтвердил используемую транзакцию очистки отдельно для каждой таблицы на
Debian 13 / iptables-nft 1.8.11: повторяющиеся `-D`, затем `-F/-X`, один `COMMIT`.
Ошибка удаления цепочки не оставляет частично примененную транзакцию таблицы на
проверенной реализации.

### 6.4. Результаты очистки

**Успех**

- `ip_forward=0`;
- нет `proto 202`;
- нет daemon-owned `proto 201 BLACKHOLE metric 65536`;
- нет цепочек/переходов `VPNG-*`.

**Ошибка**

Полная очистка не подтверждена. Запуск не продолжается. Если не подтверждено
`ip_forward=0`, дальнейший демонтаж ресурсов вообще не выполняется. Blackhole-маршруты не
снимаются, если очистка остальных daemon-owned ресурсов не подтверждена.

### 6.5. Никаких слепых полных очисток

Запрещено:

- очищать целиком таблицу маршрутизации;
- очищать целиком таблицу `filter` или `nat`;
- удалять сторонние маршруты вне области точных защищаемых префиксов, за которые отвечает
  daemon;
- удалять сторонние правила фильтрации, не являющиеся daemon-owned переходом в
  `VPNG-*`.

Точные защищаемые префиксы остаются отдельной областью ответственности daemon при обычном
согласовании; универсальная очистка этим исключением не пользуется.


## 7. Загрузка и проверка конфигурации

### 7.1. Staged parsing

После cleanup daemon всегда сначала выполняет TOML syntax parse и разбирает минимальный
top-level envelope.

Нормативный порядок:

```text
1. TOML syntax
2. top-level key set + config.enabled
3. if config.enabled=false -> stop profile/body parsing
4. for each profile: inspect profile.enabled
5. discard disabled profiles before body parsing
6. fully parse/validate enabled profile bodies
7. cross-profile validation only over enabled profiles
```

`enabled` на обоих уровнях optional и default=true.

Disabled profile **не участвует в init-time config parsing** кроме чтения его
`enabled=false`. Его `routes`, `bindings`, `allowed_sources`, неизвестные ключи и
значения не проходят schema/value/semantic validation и не создают runtime state.

Если top-level `enabled=false`, profile bodies и ACL не разбираются вообще. Это
intentional administrative off-switch, а не DEGRADED configuration.

Top-level key names остаются closed-schema даже в disabled config; содержимое полей,
кроме необходимого для disabled envelope, не проецируется в runtime.

При top-level `enabled=true` должен существовать хотя бы один enabled profile.

### 7.2. Enabled projection

Runtime config содержит только enabled profiles. Для каждого enabled profile обязательны
валидные non-empty `routes[]` и `bindings[]`; `allowed_sources[]` optional и default
empty. `common_allowed_sources[]` также optional и default empty.

Все selector conflicts, protected-route overlaps, route-vs-binding-network conflicts и
metric capacity checks считаются только по enabled profiles/BindingSpec.

Неизвестный key в enabled profile или BindingSpec является fatal config error.
Disabled profile body не рассматривается как schema instance и потому таких ошибок не
порождает.

### 7.3. `--check-config`

`--check-config` использует ту же staged projection, что normal startup, но не берет
instance lock и не изменяет kernel state.

Следовательно disabled profile намеренно не lint-ится. Чтобы проверить его body,
оператор должен включить профиль в копии config и запустить `--check-config`.

### 7.4. Критерии ограничений

Ограничение вводится только если оно выводится из kernel/tool limit, безопасности либо
конечного пространства метрик. Произвольные лимиты «для удобства» не вводятся.

## 8. Применение и согласование во время исполнения

Запуск и исполнение используют одну модель политики и привязки, но различаются обработкой
ошибок: при запуске действует жесткий отказ, а в `RUN` daemon может переходить в
`DEGRADED` или `ISOLATED`.



### 8.1. Неизменяемый snapshot согласования

Один reconciliation pass строит immutable projection из:

- current interface inventory;
- enabled ProfileConfig/BindingSpec;
- candidates каждого BindingSpec;
- active concrete bindings и owning BindingSpec;
- fixed exact ranks/metrics;
- process-local prefix active_order;
- provisional shared prefix allocator mapping/cursor каждого profile;
- desired routes;
- desired firewall/NAT policy.

Applicability candidate проверяется по network **его owning BindingSpec**.
Один и тот же snapshot используется для policy/routes, локальных delta и verification.
Provisional allocator state не commit-ится до завершенной verification.

### 8.2. Применение при запуске

После успешной очистки и проверки конфигурации:

1. проверить глобальные IPv6 prerequisites §2.6;
2. прочитать один interface/address snapshot;
3. проверить `disable_ipv6=1` на всех существующих interfaces защитных пространств
   имен управляемых селекторов;
4. построить candidates и active concrete bindings по membership local IPv4 в
   owning `BindingSpec.network`, а для `prefix+` также provisional metric allocation/cursor;
5. построить full desired firewall/NAT policy;
6. применить и проверить `filter`, затем `nat`;
7. прочитать строгий route snapshot, построить и проверить route plan;
8. materialize BLACKHOLE и direct `proto 202 dev <exact-interface>` routes;
9. повторно проверить exact protected-prefix route state;
10. подтвердить verification result для desired fail-closed state;
11. сформировать functional `ProfileResult` поверх verified state;
12. зафиксировать OWNED routes, active binding state и prefix allocator mapping/cursor
    после verification независимо от availability SUCCESS/FAIL;
13. установить и повторно подтвердить `ip_forward=1`;
14. перейти в `RUN`.

Отсутствие active concrete binding не является startup error само по себе. Если
fail-closed desired policy и route state полностью применены и проверены, профиль получает
`FAIL` по availability, daemon успешно завершает startup и входит в `RUN/DEGRADED`.

Ошибка inventory, config, firewall/NAT apply/verification, route apply/verification либо
невозможность финально подтвердить `ip_forward=1` остается hard startup failure.
Zero-path `ProfileResult=FAIL` после successful BLACKHOLE-only/direct-route verification
**не является route verification failure** и не превращается в startup error.

На обычном startup forwarding изначально выключен, поэтому первоначальное применение
`filter -> nat -> routes` безопасно без дополнительного runtime barrier.

### 8.3. Требуемые маршруты

Для каждого `profile.route` требуется BLACKHOLE:

```text
destination = profile.route
type        = BLACKHOLE
via         = None
interface   = None
proto       = 201
metric      = 65536
onlink      = false
```

Для каждого active concrete binding требуется direct UNICAST:

```text
destination = profile.route
type        = UNICAST
via         = None
interface   = exact active interface
proto       = 202
metric      = selector/list-derived or allocated prefix metric
onlink      = false
```

Metric rules определены в §4.4 и §18.

BLACKHOLE выводится только из config и существует независимо от availability. UNICAST
выводится только из active binding set текущего snapshot. Transport peer address,
point-to-point remote endpoint, handshake и route next-hop в desired model не входят.

Ни одна форма селектора не попадает в `RouteSpec.interface`; там разрешено только exact
runtime interface name.

### 8.4. Согласование во время исполнения

Каждый цикл согласования сериализован единым event loop и запускается Netlink wakeup,
периодическим таймером, полной пересверкой либо административной командой.

#### Ошибка инвентаризации интерфейсов

Без достоверной inventory daemon не может вычислить binding-specific policy/routes.
Ошибка чтения или разбора interface inventory переводит pass в `ISOLATED`: daemon
пытается выключить forwarding и может применить config-derived isolation filter, но не
угадывает active interfaces.

#### Ошибка построения snapshot / предметной проекции

Если после успешной inventory невозможно построить полный `ReconciliationSnapshot`,
частичное desired state не используется. Это относится в том числе к исчерпанию всех
допустимых prefix metric slots.

Во время `RUN` daemon best-effort выключает forwarding, может применить выводимый только
из config isolation filter и переходит в `ISOLATED`. Provisional allocator mapping/cursor
не commit-ятся. При startup такая ошибка является hard startup failure до открытия
разрешающего пути.

#### Обычный цикл

После успешной inventory:

1. повторно проверить global/per-interface IPv6 prerequisites §2.6 для current guard
   namespaces; violation -> host-prerequisite isolation path без allowing apply;
2. построить один immutable `ReconciliationSnapshot`, включая provisional prefix
   metric allocation/cursor;
3. сравнить candidates и active concrete binding identities с последним verified state;
4. если binding transition отсутствует, сравнить firewall/NAT с current desired policy;
5. если binding transition есть, построить policy/routes последнего committed binding
   state и проверить фактический source state **до первой мутации**; firewall/NAT должны
   соответствовать committed state, а для routes допускается только уже произошедшая
   kernel-side потеря proto-202 ресурсов bindings, входящих в REMOVE; любой посторонний
   exact route, отсутствие route surviving binding или иное расхождение является drift;
6. `UNKNOWN` либо неопределимая область drift -> `INIT/PANIC`;
7. INPUT-only `UNSAFE` без binding transition -> narrow INPUT repair;
8. при verified source state классифицировать binding delta как локальный `ADD`,
   локальный `REMOVE`, композицию `REMOVE -> ADD` либо как неразложимый переход;
9. выполнить локальные `ADD`/`REMOVE` по §8.6 без изменения `ip_forward`;
10. неожиданный `FORWARD`/NAT drift, `UNKNOWN`, неразложимый переход или
    apply/verification failure локальной процедуры -> `INIT/PANIC` §8.6;
11. после `SAFE` полной policy и verified routes зафиксировать OWNED, active binding
    state и prefix allocator mapping/cursor;
12. в завершенном non-ISOLATED `RUN` привести `ip_forward` к 1 и reread;
13. confirmed `ip_forward=0` после failed enable -> `DEGRADED`; unreadable
    `ip_forward` -> `ISOLATED`.

Candidate-only change без изменения active set не требует `ADD`, `REMOVE` или
`INIT/PANIC` **только после successful IPv6 prerequisite verification текущего guard
namespace**. После этой
проверки allowing IPv4 policy действительно не меняется; status обновляется из нового
snapshot.


### 8.5. Частичная доступность bindings профиля

Несколько BindingSpec и несколько concrete bindings являются штатным состоянием.

ProfileResult зависит не от количества candidates, а от verified route availability для
каждого protected destination. Если хотя бы один desired UNICAST path verified для
каждого destination, profile может быть `SUCCESS`; отсутствие всех UNICAST path дает
functional `FAIL` при структурно verified fail-closed state.

Exact BindingSpec реализуют config-defined priority/failback. Prefix BindingSpec дают
dynamic fallback pool без гарантированного взаимного preference. Отдельного
`AMBIGUOUS` state нет.

### 8.6. Три процедуры изменения состояния: ADD, REMOVE и INIT/PANIC

Состояние firewall/NAT использует именованные значения:

```text
SAFE     -> безопасно
UNSAFE   -> небезопасно
UNKNOWN  -> состояние неизвестно
```

Полное ожидаемое состояние зависит от одного неизменяемого
`ReconciliationSnapshot`.

Слой политики также обязан уметь построить `desired_isolation_filter(config)`:
полную config-derived deny-only форму managed `filter`, не содержащую
binding-specific `ACCEPT` и не зависящую от interface inventory. Она используется
только внутри `INIT/PANIC`.

Подтвержденное рассогласование, ограниченное только `INPUT` и не сопровождаемое
binding transition, сохраняет отдельный narrow repair EXP-006. Это не lifecycle-процедура
binding state: она одной транзакцией восстанавливает только daemon-owned `INPUT` и
`VPNG-INPUT-GUARD`, не изменяя `ip_forward`, `FORWARD`, NAT или routes. Если
точечный repair не применился или не verified, дальнейшее восстановление идет через
`INIT/PANIC`.

#### ADD

`ADD` применяется, когда относительно последнего verified state требуются только новые
binding-specific contributions, а все непрерывно существующие bindings сохраняют identity,
metric и relative order. Перед локальной мутацией daemon обязан подтвердить, что
фактическое source state соответствует последнему committed state; отсутствие именно тех
ресурсов, которые новая binding должна добавить, не считается drift. Процедура не зависит от selector class owning BindingSpec: появление exact либо prefix
concrete binding использует тот же протокол, если изменение доказуемо insertion-only.

`ip_forward` не изменяется. Старые verified paths продолжают работать.

Порядок:

```text
1. добавить только новый NAT contribution
2. проверить требуемый NAT
3. добавить только новый exact INPUT/FORWARD contribution
4. проверить полный требуемый filter
5. добавить только новые direct proto-202 routes
6. проверить exact protected-prefix route state
7. проверить full firewall/NAT policy
8. commit verified binding/allocator/OWNED state
```

Существующие binding-specific rules не удаляются, не пересоздаются и не меняют
relative order. Существующие desired routes не удаляются, не заменяются и не получают
новые metrics. Новые rules могут быть вставлены перед terminal `RETURN`/`REJECT`,
из-за чего меняются только числовые позиции последующих terminal rules.

Порядок `NAT -> filter -> route` обязателен: разрешающий route для новой binding не
создается раньше verified NAT и verified filtering contribution.

#### REMOVE

`REMOVE` применяется, когда относительно последнего verified state исчезает один или
несколько binding-specific contributions, а surviving bindings сохраняют identity,
metric и relative order. Перед локальной мутацией daemon подтверждает отсутствие
постороннего drift. Ресурс исчезнувшей binding, уже автоматически удаленный ядром
(например, direct route после удаления interface), считается допустимой частью ожидаемой
REMOVE-delta, а не drift.

`ip_forward` не изменяется. Безопасность обеспечивается порядком удаления:

```text
1. удалить только allowing INPUT/FORWARD contribution удаляемой binding
2. проверить filter: удаляемая binding больше не имеет forwarding permission
3. удалить ее direct proto-202 routes
4. проверить exact protected-prefix route state
5. удалить ее NAT contribution
6. проверить требуемый NAT и full firewall/NAT policy
7. commit verified binding/allocator/OWNED state
```

После шага 2 оставшийся stale route/NAT уже находится за verified deny filter и не может
дать transit path. После шага 4 допускается временное состояние «NAT без route».
Обратное состояние «route без NAT» для удаляемой binding намеренно не создается.

Surviving binding-specific rules/routes не удаляются, не пересоздаются, не
переметрируются и не переставляются.

Replacement одной concrete binding, включая `same name + new ifindex`, не является
четвертым протоколом:

```text
REMOVE old binding
-> verify remove phase
-> ADD new binding
-> verify add phase
```

Остаточное окно до обнаружения same-name/new-ifindex остается границей модели §4.5:
iptables сопоставляет имя, а не исторический ifindex.

Если изменение одновременно содержит additions/removals, daemon сначала выполняет все
необходимые `REMOVE`, затем `ADD`, только если можно доказать, что surviving
contributions остаются неизменными. Изменение metric/order существующей surviving binding,
неразложимое изменение policy либо невозможность доказать локальную delta переводят
операцию в `INIT/PANIC`.

#### INIT/PANIC

`INIT/PANIC` — единственная глобальная процедура. Она используется:

- на startup;
- при `FORWARD`/NAT drift либо `UNKNOWN`;
- при ошибке inventory/snapshot, когда binding-specific state нельзя достоверно вывести
  (в этом случае PANIC может завершиться verified isolation и ожиданием следующего
  достоверного snapshot без попытки построить full binding-specific state);
- при ошибке или verification failure `ADD`/`REMOVE`;
- при transition, который нельзя безопасно разложить на локальные `REMOVE` и `ADD`;
- при иных нарушениях, после которых прежний full managed state нельзя считать verified.

Процедура начинается с попытки установить и reread `ip_forward=0`.

Если `ip_forward=0` подтвержден, forwarding уже является глобально закрытым барьером и
daemon может полностью пересобрать managed `filter`, NAT и routes из одного snapshot.

Если подтвердить `ip_forward=0` не удалось, daemon **не** начинает разрешающую
пересборку. Сначала он применяет и проверяет `desired_isolation_filter(config)`; только
verified deny-only filter может заменить не подтвержденный sysctl как защитный барьер.

После наличия одного из этих подтвержденных барьеров:

```text
1. полностью привести managed filter/NAT к desired state текущего snapshot
   с правилом: полный allowing filter не считается безопасным раньше verified NAT
2. полностью привести managed routes к desired state
3. повторно проверить full firewall/NAT и exact protected-prefix routes
4. commit verified binding/allocator/OWNED state
5. установить и reread ip_forward=1
```

На startup, где `ip_forward=0` подтвержден до применения allowing state, допустим
прямой полный apply `filter -> NAT -> routes` с verification каждой стадии. При PANIC,
если защитой служит isolation filter из-за неподтвержденного sysctl, сначала
применяется/проверяется NAT, затем full filter, затем routes: allowing `FORWARD` не
появляется раньше verified NAT.

`INIT/PANIC` намеренно может удалить и пересоздать все daemon-owned rules/routes:
это аварийно-инициализационный механизм, а не штатная обработка lifecycle интерфейсов.
Сторонние rules/chains вне daemon-owned namespace сохраняются по общим правилам
ownership.

Состояние `UNKNOWN` никогда не чинится слепой локальной delta. Если защитный барьер
`INIT/PANIC` не удалось подтвердить, daemon остается `ISOLATED` и не применяет
allowing state.

### 8.7. Исполнитель маршрутов

Порядок изменений маршрутов сохраняется:

```text
1. добавить отсутствующие BLACKHOLE
2. удалить конкурирующие точные маршруты
3. выполнить определяющие замены
4. добавить оставшиеся маршруты
```

Проверка плана маршрутов сохраняет определяющую семантику точного префикса и запрет
изменения `proto kernel`.

Route-only drift при уже verified `SAFE` firewall/NAT не требует глобального
`INIT/PANIC` до попытки исправления. Verified filter разрешает protected destination
только через exact active egress, а исполнитель маршрутов сначала materialize недостающий
BLACKHOLE и лишь затем выполняет разрушительные route operations.

Если обычный route repair/apply/verification **не завершился успешно**, полное managed
route state больше нельзя считать verified. Такой failure переводит текущий pass в
`INIT/PANIC`: forwarding закрывается, managed state пересобирается и routes проверяются
заново до возможного повторного открытия forwarding.


### 8.8. OWNED и фиксация binding state

Process-local OWNED routes, последнее подтвержденное состояние active concrete bindings
и prefix allocator mapping/cursor изменяются только после завершенной успешной проверки
соответствующего цикла.

**Verification success и `ProfileResult` — разные оси.** Если fail-closed desired state
полностью verified, active binding state текущего snapshot фиксируется даже когда functional availability
дает `ProfileResult=FAIL` из-за zero UNICAST paths. Иначе
валидный `RUN/DEGRADED` создавал бы ложный policy transition на каждом periodic pass.

Порядок завершения verified `ADD`/`REMOVE`:

```text
проверить policy/routes
-> зафиксировать OWNED + active binding state + prefix allocator state
```

`ip_forward` при локальной процедуре не изменяется.

Порядок завершения `INIT/PANIC`:

```text
проверить policy/routes
-> зафиксировать OWNED + active binding state + prefix allocator state
-> включить и подтвердить ip_forward
```

Фиксация после открытия forwarding в `INIT/PANIC` запрещена.

### 8.9. Состояние жизненного цикла

```text
недостаточная наблюдаемость interfaces/policy/ip_forward -> ISOLATED
firewall/NAT != SAFE                                     -> ISOLATED

config.enabled == false
  И startup cleanup confirmed
  И ip_forward == 0                                      -> DISABLED

firewall/NAT == SAFE
  И все enabled profiles SUCCESS
  И ip_forward == 1                                      -> ACTIVE

firewall/NAT == SAFE
  И structural route verification complete
  И (
       хотя бы один enabled profile availability FAIL
       ИЛИ confirmed ip_forward == 0
    )                                                    -> DEGRADED
```

Profile result формируется после проверки full desired firewall/NAT policy и route state.

`SUCCESS` требует:

1. binding-specific contribution full policy применен и verified;
2. exact protected-prefix route state полностью совпадает с desired;
3. для каждого `profile.route` существует как минимум один verified desired UNICAST
   path через active concrete interface;
4. BLACKHOLE и остальные required resources соответствуют desired state.

У множественного selector не требуется присутствие всех paths. Один verified active
interface для каждого protected destination достаточен для `SUCCESS`.

`FAIL` означает только verified functional availability loss: для хотя бы одного
protected destination нет ни одного verified desired UNICAST path при structurally exact
route state.

Structural route/policy mismatch не кодируется как `ProfileResult=FAIL`: failed ordinary
route build/apply/verification эскалирует в `INIT/PANIC`, а недостаточная наблюдаемость
уровня всего pass приводит к `ISOLATED`.

`ACTIVE` и `ProfileResult=SUCCESS` подтверждают desired kernel configuration, но не
end-to-end transport reachability. Ping, handshake и transport peer health не входят в
этот статус.

Операционный status профиля сообщает как минимум:

- `ProfileResult=SUCCESS|FAIL` и стабильную reason code при `FAIL`;
- configured BindingSpec entries;
- candidates с owning BindingSpec;
- active concrete bindings с owning BindingSpec;
- desired/verified direct `UNICAST RouteSpec` с interface/metric;
- exact BindingSpec и их fixed config-derived exact_rank/metric;
- для prefix BindingSpec — process-local active_order и текущие binding -> metric allocations;
  взаимный prefix route priority не обещается; active_order может использоваться как
  диагностический порядок первого принятия bindings текущим daemon.

Ручной `sysctl -w net.ipv4.ip_forward=0` не является административной паузой; чистый
reconciliation возвращает daemon-owned desired value.

## 9. Фильтрация и blackhole

Политика сетевых правил (firewall и NAT) daemon-owned ресурсов состоит из структурной части и части, зависящей
от привязки.

Структурная часть существует для всех управляемых профилей независимо от текущего binding state:

- зарезервированные цепочки `VPNG-*`;
- детерминированный префикс переходов из встроенных цепочек;
- `VPNG-RESERVED`;
- окончательные запреты защищаемых назначений в цепочках профилей;
- `VPNG-INPUT-GUARD`;
- `VPNG-FORWARD-DENY`.

Часть, зависящая от привязок, строится только для active concrete interfaces и
однозначных active bindings текущего snapshot.

### 9.1. Порядок переходов из встроенных цепочек

Профили во всех daemon-owned префиксах сортируются лексикографически по нормализованному
идентификатору профиля в верхнем регистре, по ASCII-коду символов. Порядок не зависит от
локали и должен совпадать в Python- и Rust-реализациях.

`INPUT`:

```text
1..N   -> VPNG-<PROFILE>-INPUT, в порядке профилей
N+1    -> VPNG-INPUT-GUARD
далее  -> сторонние правила INPUT
```

`FORWARD` в проверенном требуемом состоянии:

```text
1      -> VPNG-INGRESS
2      -> VPNG-RESERVED
3..    -> VPNG-<PROFILE>-FORWARD, в порядке профилей
last   -> VPNG-FORWARD-DENY
далее  -> сторонние правила FORWARD
```

`POSTROUTING`:

```text
1..N   -> VPNG-<PROFILE>-NAT, в порядке профилей
далее  -> сторонние правила
```

В проверенном требуемом состоянии daemon-owned префикс физически начинается с позиции 1
во всех трех встроенных цепочках.

Стороннее правило перед daemon-owned префиксом `INPUT` является подтвержденным
`INPUT`-рассогласованием и восстанавливается точечно по §8.6: правило не удаляется, а
после перестановки оказывается после `VPNG-INPUT-GUARD`.

Стороннее правило перед daemon-owned префиксом `FORWARD` или `POSTROUTING` является
транзитным рассогласованием `UNSAFE` и переводит восстановление в `INIT/PANIC`. Для `FORWARD` строгий префикс сохраняет полное владение решением через
`VPNG-FORWARD-DENY`; для `POSTROUTING` гарантирует обработку daemon-owned NAT раньше
сторонних преобразований.

Каждая NAT-цепочка профиля при несовпадении возвращает управление через `RETURN`.
Поэтому сторонние правила `POSTROUTING` после daemon-owned префикса сохраняются и
остаются достижимыми для неуправляемого исходящего трафика.

`OUTPUT` не входит в область управления VPN Gateway: daemon не создает, не изменяет, не
переставляет и не удаляет правила этой цепочки. Политика `OUTPUT` принадлежит
администратору хоста.

Следствие: локально созданный на самом шлюзе трафик не проходит ACL источников
`FORWARD` и может использовать установленные защищаемые маршруты. Это сознательная часть
модели доверенного выделенного хоста; ограничение локального `OUTPUT` остается
ответственностью администратора.

Каждый daemon-переход существует ровно один раз и использует обычный `-j`.


### 9.2. Семантика INPUT

Цепочка `INPUT` профиля содержит точный блок для каждого уникального active concrete
interface:

```text
-i <точный-интерфейс>
ctstate INVALID
    DROP

-i <точный-интерфейс>
ctstate ESTABLISHED,RELATED
    ACCEPT

-i <точный-интерфейс>
    REJECT --reject-with icmp-host-prohibited
```

Exact blocks идут в нормативном `active_order` §4.3. Для `prefix+` в требуемой policy
block новой binding располагается после уже принятых bindings и не меняет относительный
порядок существующих blocks. Транзакционное применение полной цепочки не считается
изменением этого логического порядка. После всех exact blocks цепочка возвращает
управление через `RETURN`.

Таким образом, удаленная сторона VPN не может инициировать новое соединение с самим
шлюзом через active managed interface. Разрешен только ответный
`ESTABLISHED,RELATED` traffic на соединения, инициированные локально самим хостом.

После цепочек профилей `VPNG-INPUT-GUARD` блокирует входящий traffic защитных пространств
имен, который не был завершен более ранним exact block:

- exact BindingSpec — exact interface rule;
- prefix BindingSpec — `-i prefix+`.

Prefix matching никогда не используется для `ACCEPT` или NAT.

Traffic вне защитных пространств имен после daemon-owned INPUT prefix продолжает
обрабатываться обычной host firewall policy.

### 9.3. Семантика FORWARD

`VPNG-INGRESS` сначала содержит exact block для каждого уникального active concrete
interface в нормативном `active_order` §4.3. Для `prefix+` добавление новой binding не
меняет относительный порядок уже существующих blocks:

```text
-i <точный-интерфейс>
ctstate INVALID
    DROP

-i <точный-интерфейс>
ctstate ESTABLISHED,RELATED
    ACCEPT

-i <точный-интерфейс>
    REJECT --reject-with icmp-host-prohibited
```

После exact blocks идут deny guards всех enabled BindingSpec в детерминированном
config order профилей/bindings. Prefix guard использует `-i prefix+`, exact guard —
exact interface rule. Затем следует `RETURN`.

`VPNG-RESERVED` всегда выполняет `REJECT` для назначения в любую managed
enabled `BindingSpec.network`.

Цепочка `FORWARD` профиля для каждого protected destination обходит active egress
interfaces в нормативном `active_order` §4.3 и для каждого содержит:

```text
-d route -o <точный-интерфейс> ctstate INVALID
    DROP

для каждого effective_source:
    -s source -d route -o <точный-интерфейс>
        ACCEPT
```

После всех active egress interfaces для данного protected destination всегда идет:

```text
-d route
    REJECT --reject-with icmp-host-prohibited
```

Отсутствие `-i` в разрешающем правиле профиля не предоставляет обратный доступ через
managed VPN interfaces: incoming traffic уже обязан завершиться внутри `VPNG-INGRESS`.

После всех профильных chains `VPNG-FORWARD-DENY` сохраняет полное владение решением
`FORWARD`:

```text
ctstate INVALID
    DROP

все остальное
    REJECT --reject-with icmp-host-prohibited
```

В проверенном состоянии ни один пересылаемый IPv4 packet при daemon-owned
`ip_forward=1` не достигает сторонних FORWARD rules или builtin policy.

### 9.4. Fail2ban

Поддерживаемая интеграция Fail2ban относится только к обычной политике хоста в `INPUT`
после daemon-owned префикса.

Daemon не распознает Fail2ban по именам цепочек и не анализирует рекурсивно семантику
сторонних правил. Если Fail2ban или другой firewall хоста вставляет правило перед
daemon-owned `INPUT`-префиксом, следующий цикл согласования точечно возвращает префикс
на позицию 1 без изменения `ip_forward` и транзитной политики. Стороннее правило
сохраняется после `VPNG-INPUT-GUARD`.

Для трафика вне управляемых VPN-интерфейсов профильные `VPNG-*` цепочки возвращают
управление, поэтому последующие правила Fail2ban продолжают работать как обычная политика
хоста.

Fail2ban для входящего трафика управляемых VPN-интерфейсов сознательно не поддерживается;
это ничего не стоит текущей однонаправленной модели, в которой новый `INPUT` с
управляемой VPN-стороны все равно запрещен. Если будущая двунаправленная модель потребует
фильтрации разрешенного `NEW` трафика с управляемых VPN-интерфейсов, для нее должна быть
спроектирована явная точка интеграции и при необходимости специализированный action, а не
анализ произвольного стороннего firewall.

Произвольные actions, изменяющие `FORWARD`, `POSTROUTING` или daemon-owned
`VPNG-*`, не получают специальной совместимости с Fail2ban и оцениваются по общим
инвариантам соответствующей области.

### 9.5. Blackhole

Blackhole-маршруты устанавливаются для всех защищаемых маршрутов управляемых профилей:

```text
proto 201
metric 65536
type blackhole
```

Blackhole не зависит от текущего binding state и наличия UNICAST path.

EXP-004.2 подтвердил: при исчезновении зависящего от интерфейса `proto 202` UNICAST
blackhole остается и не дает защищаемому назначению уйти через маршрут по умолчанию.

Blackhole не заменяет фильтрацию: полная политика `FORWARD` остается независимым слоем
отказа с запретом.

## 10. VPN-маршруты

Все VPN-маршруты daemon имеют:

```text
proto 202
```

Это обязательный ownership marker для cleanup после crash/restart/config change.

VPN UNICAST route является **direct interface route**:

```text
destination <prefix>
dev <exact-active-interface>
metric <selector-derived>
proto 202
```

`via` и `onlink` для daemon-owned UNICAST не используются. Transport peer selection
находится за границей VPN-GATE.

Очистка удаляет только принадлежащие сервису routes `proto 202`.

## 11. NAT

Для каждого управляемого профиля существует структурная цепочка:

```text
VPNG-<PROFILE>-NAT
```

и детерминированный переход из `POSTROUTING`.

Для каждого уникального active egress interface профиля в нормативном `active_order`
§4.3 создается:

```text
-o <точный-интерфейс>
-m addrtype ! --src-type LOCAL
-j MASQUERADE
```

После всех таких правил цепочка содержит `RETURN`.

Если active egress interfaces отсутствуют, цепочка содержит только `RETURN`.

Ни exact, ни prefix selector не используются как условие интерфейса в NAT; NAT всегда
materialize только по exact active concrete interface names.

Штатные local `ADD`/`REMOVE` не изменяют `ip_forward` и применяют только доказанную
binding-local delta. Глобальный forwarding barrier используется только `INIT/PANIC`.
Для `ADD` NAT новой binding обязан быть применен и verified до allowing filter и до
добавления `proto 202` route; для `REMOVE` allowing filter снимается раньше route и
NAT.

Сторонние правила `POSTROUTING` не удаляются. Если профильная NAT-chain не совпала с
traffic, ее `RETURN` передает обработку последующим сторонним правилам.

Сохраняется зависимость безопасности:

```text
active bindings определены
-> точная filter/NAT policy применена и проверена
-> routes применены
-> forwarding включен/восстановлен
```

Сторонний route через managed exact interface не обходит daemon policy, потому что полное
владение `FORWARD` разрешает outgoing traffic только явным профильным `ACCEPT`.

### 11.1. Окно реакции на событие

Разрешающий NAT нельзя materialize из selector template: он создается только для active
exact interfaces текущего snapshot.

Между kernel event и reconciliation остается ограниченное окно реакции (§4.5). До
reconciliation новый candidate interface не получает `proto 202` route или exact
разрешающее правило `FORWARD`; blackhole, selector guard и окончательный FORWARD deny
сохраняют отказ с запретом.

Быстрое повторное использование прежнего exact name остается гонкой в границах модели
доверенного хоста и обнаруживается по изменению ifindex на ближайшем Netlink event или
полной пересверке.


## 12. Конфигурация

Основной файл:

```text
/etc/vpn-gateway/vpn-gateway.toml
```

Формат — TOML. Файл и parent directory сохраняют ранее определенные ownership/mode
requirements.

Пример:

```toml
enabled = true
reconcile_interval = 10.0

common_allowed_sources = [
    "10.200.200.8/32",
]

[profiles.primary]
enabled = true
routes = [
    "10.0.0.0/8",
    "192.168.0.0/16",
]
allowed_sources = ["10.200.201.0/24"]

bindings = [
    { interface = "wg0",    network = "172.20.126.0/29" },
    { interface = "wg1",    network = "172.20.127.0/29" },
    { interface = "ocvpn+", network = "172.20.130.0/29" },
]

[profiles.future]
enabled = false
# Остальное содержимое normal startup/--check-config не разбирает.
```

`reconcile_interval` остается ортогональным operational parameter и не участвует в
routing priority.

Transport peer configuration в VPN-GATE отсутствует. WireGuard `AllowedIPs`,
OpenConnect session identity, endpoint и credentials принадлежат transport configuration
вне VPN-GATE.

## 13. Закрытая схема конфигурации

Для enabled config:

```text
enabled                       bool, optional, default true
reconcile_interval            float, optional, default 10.0, range [1.0, 60.0]
common_allowed_sources        array[IPv4|IPv4CIDR], optional, default []

[profiles.<profile>]
enabled                       bool, optional, default true
routes                        non-empty array[IPv4CIDR], required when enabled
bindings                      non-empty array[BindingSpec], required when enabled
allowed_sources               array[IPv4|IPv4CIDR], optional, default []

BindingSpec inline table:
interface                     string, required; exact | trailing-prefix+
network                       canonical IPv4 CIDR, required
```

Top-level unknown keys fatal. Для enabled profile/BindingSpec unknown keys fatal.
Disabled profile body исключен до schema parsing.

Profile id валидируется только для enabled profile:

```text
[A-Za-z][A-Za-z0-9_-]{0,14}
```

Chain names:

```text
VPNG-<PROFILE>-INPUT
VPNG-<PROFILE>-FORWARD
VPNG-<PROFILE>-NAT
```

## 14. Enabled и пустые значения

`config.enabled=false` является валидным intentional disabled state; profile bodies при
этом не разбираются.

При `config.enabled=true`:

- должен существовать хотя бы один enabled profile;
- enabled `profile.routes` non-empty;
- enabled `profile.bindings` non-empty;
- missing/empty `common_allowed_sources` допустим;
- missing/empty `profile.allowed_sources` допустим.

Disabled profile может быть неполным или содержать значения будущей schema: они не
участвуют в startup projection.

## 15. Binding selectors и priority classes

### 15.1. Exact

Exact interface name:

```text
[A-Za-z][A-Za-z0-9_.-]{0,14}
```

Case-insensitive forbidden names:

```text
lo
any
default
all
```

Каждый exact BindingSpec имеет fixed `exact_rank`: ordinal среди exact BindingSpec
профиля в config order. Его metric всегда:

```text
FIRST_UNICAST_METRIC + exact_rank * ROUTE_METRIC_STEP
```

Prefix entries между exact entries rank не занимают.

### 15.2. Prefix `+`

Форма:

```text
<prefix>+
```

Prefix начинается с ASCII letter, использует exact-name grammar и имеет длину 1..14.
`+` допустим только последним символом.

Candidates — все interface names, начинающиеся с prefix, включая exact `prefix`.
Guard использует только deny semantics `-i prefix+`.

Все prefix BindingSpec одного профиля используют общий dynamic allocator §4.4.
Позиция prefix BindingSpec в `bindings[]` не задает route preference.

### 15.3. Namespace conflicts

Selector namespaces **всех enabled BindingSpec** попарно не пересекаются, включая
BindingSpec разных enabled profiles.

Fatal examples:

```text
vpns+     + vpns0
vpns+     + vpnsA+
wg0       + wg0
```

Если два enabled selectors могут matched одно exact interface name, config invalid.
Disabled profile/BindingSpec в conflict set не входят.

`%`, wildcard/glob/regex кроме завершающего `+` запрещены.

## 16. Binding networks и адреса

Каждый BindingSpec имеет собственный `network`:

- canonical IPv4 CIDR;
- `/32` запрещен, минимально допустима `/31`;
- network используется как active applicability predicate и как reserved transport
  address space;
- конкретный host address отдельно в VPN-GATE не задается.

Matching candidate active, если inventory содержит хотя бы один local IPv4 member
BindingSpec.network. Проверяется host membership, а не prefix length адреса на interface;
tunnel endpoint может быть представлен как /32.

Binding networks разных BindingSpec могут совпадать или пересекаться: это допустимо,
поскольку interface ownership определяется непересекающимися selector namespaces.
Protected routes любого enabled profile не должны пересекаться ни с одной enabled
BindingSpec.network.

Remote P2P address, peer address и handshake не участвуют в applicability.

## 17. ACL источников

`common_allowed_sources` и `profile.allowed_sources` optional и default empty.
Они принимают single IPv4 либо canonical IPv4 CIDR; single IPv4 normalizes to /32.

Effective ACL enabled profile:

```text
set(common_allowed_sources) UNION set(profile.allowed_sources)
```

Exact duplicates после normalization удаляются. Пересечения разрешены. Отрицательных
правил и исключений нет.


## 18. Маршруты защищаемых сетей

`profile.routes` enabled профиля — непустой набор canonical IPv4 network prefixes.

Запрещены:

- default route;
- duplicate routes после normalization;
- нетождественные overlap/nesting между protected routes enabled profiles;
- overlap protected route с любой enabled BindingSpec.network.

Для каждого protected destination daemon всегда требует BLACKHOLE
`proto 201 metric 65536`.

UNICAST routes materialize по каждой active concrete binding:

```text
dev exact-interface
via None
proto 202
metric according to BindingSpec class
```

Exact class:

```text
10,20,30... по exact_rank config
```

Prefix class:

```text
dynamic_metric_min = 10 + exact_count * 10
shared cyclic allocator from dynamic_metric_min
```

При исчезновении exact primary следующий exact metric либо dynamic prefix route
естественно становится предпочтительным Linux route. При возврате exact primary его
fixed lower metric восстанавливает failback. Это interface-availability failover, а не
health-check удаленной стороны.


## 19. Состояние VPN и сетевых правил

Lifecycle states:

- `STARTING`;
- `DISABLED` — intentional `config.enabled=false`, `ip_forward=0`, profiles не
  parsed/materialized;
- `ACTIVE` — full policy SAFE, все enabled profiles functional SUCCESS, `ip_forward=1`;
- `DEGRADED` — structurally verified fail-closed state, но хотя бы один enabled profile
  не имеет verified UNICAST path либо forwarding временно OFF;
- `ISOLATED` — policy/prerequisite state нельзя считать обычным verified service state;
- `STOPPING`.

ProfileResult относится только к enabled profiles и остается отдельной осью от lifecycle.
`SUCCESS` означает наличие хотя бы одного verified desired UNICAST path для каждого
protected destination, но не end-to-end reachability.

`DISABLED` не является ошибкой/DEGRADED и не включает forwarding.


## 20. Проверка конфигурации без запуска

`vpn-gatewayd --check-config`:

- не получает instance lock;
- не изменяет kernel state;
- выполняет ту же staged parsing/projection §7;
- при top-level `enabled=false` не разбирает profile bodies;
- у profile `enabled=false` не разбирает ничего кроме disabled flag;
- полностью валидирует enabled profiles, BindingSpec, selectors, routes, ACL,
  cross-profile conflicts и metric capacity;
- exit 0 означает, что enabled projection валидна.

Для проверки disabled profile оператор должен временно включить его в копии config.

## 21. Административный интерфейс

Отдельный IPC может использоваться для простых локальных административных команд, например:

```text
status
shutdown
```

`reload-config` отсутствует по архитектурному решению.

IPC не должен позволять клиенту напрямую изменять состояние ядра; команды исполняет сам `vpn-gatewayd`.

## 22. Что сознательно исключено

На текущем этапе не реализуются:

- автоматическое переключение между VPN-профилями;
- изменение конфигурации без перезапуска;
- откат на старую конфигурацию;
- snapshot конфигурации, сохраняемый между запусками;
- состояние исполнения, сохраняемое между запусками, как источник истины;
- проверка доступности удаленной стороны VPN (ping);
- проверка WireGuard handshake;
- failover между несколькими transport peers одного WireGuard interface: EXP-009
  подтвердил, что WireGuard выбирает peer по `AllowedIPs`, а Linux route next-hop не
  выбирает peer; если нужен управляемый VPN-GATE route preference/failover, transports
  должны экспонироваться как отдельные concrete interfaces либо решаться самим transport;
- пересылка IPv6;
- сторонние Python-библиотеки.

Неперсистентная инвентаризация `OWNED` во время исполнения не относится ни к состоянию daemon,
сохраняемому между запусками, ни к snapshot конфигурации, сохраняемому между запусками.

## 23. Внутренняя модель реализации

Python-реализация больше не обязана помещаться в один исходный файл.

Допустим и предпочтителен небольшой пакет/каталог, если это улучшает аудит и снижает
связанность кода. При развертывании сохраняется одна точка входа daemon, например:

```text
vpn-gatewayd
vpn_gateway/
    config.py
    model.py
    kernel.py
    policy.py
    daemon.py
```

Точные имена и разбиение не являются архитектурным API. Не следует дробить код на
микромодули без смысловой границы.

Будущая реализация на Rust по-прежнему ориентируется на один исполняемый файл. Поэтому
границы предметных областей должны естественно переноситься в Rust `struct`/`enum` и модули
и не зависеть от динамической подмены методов (monkey-patching) или специфичной для Python
метапрограммной техники.



### 23.1. Модель конфигурации и предметной области

Нормативная предметная модель:

```text
GatewayConfig:
    enabled: bool
    reconcile_interval: float
    common_allowed_sources: tuple[IPv4Network, ...]
    profiles: Mapping[ProfileId, VpnProfileConfig]   # only enabled profiles

VpnProfileConfig:
    profile_id: str
    routes: tuple[IPv4Network, ...]
    bindings: tuple[BindingSpec, ...]
    allowed_sources: tuple[IPv4Network, ...]

BindingSpec:
    interface: InterfaceSelector
    network: IPv4Network
    config_index: int
    exact_rank: int | None

InterfaceSelector:
    EXACT(name)
    PREFIX(prefix)
```

LIST selector как отдельный domain type отсутствует.

Runtime projection связывает candidate/active concrete binding с owning BindingSpec.
Concrete identity остается:

```text
InterfaceBinding(name, ifindex)
```

Поскольку enabled selector namespaces не пересекаются, concrete interface имеет не более
одного owning BindingSpec.

Для каждого profile process-local verified state содержит:

- owned routes;
- committed active exact bindings;
- committed process-local prefix active_order;
- shared prefix metric mapping/cursor, если profile имеет prefix BindingSpec.

Verified-state commit должен быть two-phase: вся preparation/validation prospective state
для всех profiles завершается **до первой мутации** process-local committed state.
Commit stage после preparation не содержит validation, способной породить partial commit.

### 23.2. Модель маршрутов

`RouteSpec` остается immutable value object:

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

Нормативные значения:

- BLACKHOLE: `via=None`, `interface=None`, `onlink=False`;
- daemon-owned UNICAST: `via=None`, `interface=<exact active name>`,
  `onlink=False`, `proto=202`.

Поля `via` и `onlink` сохраняются в generic kernel boundary, потому что daemon
инвентаризует и сравнивает foreign routes, но **desired VPN-GATE UNICAST никогда не
использует transport next-hop**.

Route plan сохраняет `adds/deletes/replaces` и authoritative exact-prefix semantics.

### 23.3. Состояние OWNED во время исполнения

Process-local state хранит:

- verified OWNED routes;
- active concrete binding identities в normative `active_order`;
- для каждого `prefix+` profile — подтвержденный process-local active_order,
  отображение `ConcreteBinding(name, ifindex) -> metric` и `next_metric_cursor`.

Current candidate set остается частью immutable reconciliation snapshot, но отдельно как
committed process-local state не хранится.

Prefix active_order и allocator state не сохраняются на диск и не являются источником
сетевой истины. После restart cleanup удаляет `proto 202`, process-local order начинается
заново из первого snapshot, а allocator — с пустого отображения и
`FIRST_UNICAST_METRIC`.

Каждый reconciliation заново читает inventory и строит current state. Prefix active_order
строится из последнего verified order и текущих active bindings: surviving bindings
сохраняют относительный порядок, исчезнувшие удаляются, новые добавляются в конец.
Предварительное распределение prefix metrics вычисляется из последнего verified allocator
state и этого нового order. Новый active_order, распределение и cursor фиксируются только
после successful verification полного требуемого состояния.

Commit verified binding/allocator state не зависит от functional `ProfileResult`:
verified zero-path state с `ProfileResult=FAIL` также commit-ится. При actual
verification error прежние verified binding/allocator state сохраняются.

### 23.4. Граница взаимодействия с ядром

`KernelInterface` остается узкой физической границей и не принимает решений политики.

Обычное согласование:

```text
list_routes() -> строгий полный snapshot основной IPv4-таблицы
list_interfaces() -> записи интерфейсов с name/ifindex/IPv4
add_route(RouteSpec)
delete_route(RouteSpec)
replace_route(RouteSpec)
read/write ip_forward
iptables-save / iptables-restore
```

Для очистки дополнительно используются выборочные по маркеру запросы маршрутов:

```text
list_routes_by_proto(201)
list_routes_by_proto(202)
```

Точное имя метода относится к деталям реализации. Семантический контракт: запрос с
фильтром не разбирает несвязанные сторонние маршруты.

Адаптер дочерних процессов для Debian использует:

```text
ip -j -N -4 route show table main
ip -j addr show
ip -j -N -4 route show table main proto <N>
```

Полная инвентаризация маршрутов по-прежнему считает ошибкой непредставимые формы
multipath/nexthop/nhid.

Выборочная инвентаризация при очистке получает идентичность протокола из контекста запроса,
потому что iproute2 может не печатать `protocol` в отфильтрованном выводе.

Инвентаризация по протоколу остается строгой **внутри зарезервированного пространства
маркеров**: непредставимый маршрут `proto 201/202` с multipath/nhid в структурированной форме не
пропускается молча и считается ошибкой очистки. Для `proto 201` ресурс очистки дополнительно
обязан соответствовать `type=BLACKHOLE metric=65536`; другая форма с зарезервированным
`proto 201` является конфликтом маркера, а не кандидатом на молчаливое удаление.

Разборщик адресов/интерфейсов учитывает только `addr_info[].family == "inet"` и поле
`local`; ifindex сохраняется в `InterfaceRecord`. Remote point-to-point `address`
может сохраняться как diagnostic evidence, но route/binding model от него не зависит.
Дублирующиеся записи одного имени могут объединяться только при одинаковом `ifindex`.

### 23.5. Модель политики firewall/NAT

Слой политики строит из неизменяемой конфигурации и snapshot текущего цикла две явные
формы:

```text
desired_full_policy(snapshot)
desired_isolation_filter(config)
```

Точные имена функций и классов относятся к деталям реализации.

Полная политика содержит структурные ресурсы и точные правила, зависящие от привязки.

Изолирующий фильтр:

- не зависит от инвентаризации интерфейсов;
- не содержит `ACCEPT`, зависящих от привязки;
- не содержит разрешающего сопоставления по префиксу;
- сохраняет защитные правила селекторов `INPUT`;
- сохраняет запрещающие правила входящего `FORWARD`-трафика селекторов;
- сохраняет `REJECT` транспортных сетей VPN, защищаемых назначений и окончательный
  `VPNG-FORWARD-DENY`.

Его профильные цепочки имеют однозначную структуру.

`VPNG-<PROFILE>-INPUT` в изолирующем фильтре:

```text
RETURN
```

`VPNG-<PROFILE>-FORWARD`:

```text
для каждого защищаемого назначения:
    -d route
        REJECT --reject-with icmp-host-prohibited

RETURN
```

`VPNG-INGRESS` не содержит точных блоков active concrete bindings. Он содержит только
запрещающие guard-правила всех управляемых селекторов и завершающий `RETURN`.

При применении изолирующий фильтр является **полным требуемым состоянием под управлением daemon
таблицы `filter`** для этой промежуточной стадии. Он не добавляется поверх текущего фильтра:
устаревшие daemon-owned правила `ACCEPT`, которых нет в требуемом состоянии изолирующей
стадии, должны быть удалены или заменены в той же операции применения.

Применение изолирующего фильтра не изменяет таблицу `nat`. Ранее примененный NAT может
временно оставаться за проверенным запрещающим барьером. Затем оркестрация применяет и
проверяет требуемый NAT текущего snapshot и только после этого применяет полную разрешающую
политику фильтрации.

Успешная проверка изолирующего фильтра означает только подтверждение защитного барьера и
никогда не эквивалентна состоянию `SAFE` полной требуемой политики firewall/NAT.

Только состояние `SAFE` полной требуемой политики firewall/NAT после проверки требуемого
NAT и полного фильтра может открыть путь к завершению согласования маршрутов и последующему
включению пересылки.

Обе формы выводятся из **одной модели политики**. Сравнение и восстановление не имеют
независимых источников истины. Локальные `ADD`/`REMOVE` применяют только доказанную
delta между двумя состояниями этой же модели; `INIT/PANIC` пересобирает полное
daemon-owned состояние.

Ни exact, ни prefix selector не применяются непосредственно как allowing predicate
`ACCEPT` или NAT; там используются только exact active concrete interface names.
Сопоставление `-i prefix+` допустимо только в проверенных deny-only guard rules
`INPUT`/`FORWARD`.

### 23.6. Политика владения маршрутами

Daemon является определяющим владельцем маршрутов только для точных защищаемых префиксов
управляемых профилей.

Для каждого точного защищаемого префикса:

```text
требуемый OWNED RouteSpec              -> оставить
OWNED, но не требуемый                 -> удалить
сторонний нетребуемый точный маршрут   -> удалить
точный требуемый, но не OWNED          -> заменить/канонизировать, затем проверить
настроенный защитный BLACKHOLE          -> требуется всегда
```

Маршрут `proto kernel` никогда не удаляется и не заменяется. Совпадение точного
защищаемого префикса с маршрутом подключенной сети `proto kernel` является фатальным при запуске.

Если такой конфликт с `proto kernel` появляется во время `RUN`, daemon также не имеет
права изменять этот маршрут. План маршрутизации завершается ошибкой для соответствующего
профиля; при уже проверенной безопасном состоянии firewall жизненный цикл сохраняет отказ
с запретом и переходит в `DEGRADED`, а маршрут ядра не принимается как OWNED.

Пересечения с более или менее специфичными маршрутами автоматически не удаляются и
остаются диагностическими.

Отказ с запретом обеспечивается тремя независимыми слоями:

1. `BLACKHOLE` для защищаемого префикса;
2. безусловный `REJECT` защищаемого назначения внутри профильной цепочки `FORWARD`;
3. глобальный окончательный `VPNG-FORWARD-DENY`.

### 23.7. Цикл обработки событий

Один `VpnGatewayDaemon` владеет:

- одним слушателем Netlink;
- периодическим таймером согласования;
- механизмом пробуждения по сигналу;
- событиями IPC и административными командами.

Все события сериализованы. Одновременно выполняется не более одного цикла согласования.

Netlink-событие используется как сигнал пробуждения и признак необходимости пересверки,
а не как достоверное описание изменения состояния. Согласование читает заново полный
snapshot интерфейсов.

Событие interface можно игнорировать только если exact name не может попасть ни в одно
guard namespace managed selectors. Любое имя, совпадающее с exact/list element либо
prefix namespace, будит full reconciliation. Сам event остается wakeup hint; resources
выводятся из заново построенного snapshot.

### 23.8. Диагностическая модель

Ожидаемые эксплуатационные ошибки имеют стабильную машинную идентичность причины,
независимую от человекочитаемого текста. Концептуальный контракт:

```text
DiagnosticFact:
    code   -> стабильный код причины
    detail -> необязательный человекочитаемый контекст
```

Точные имена Python-классов относятся к реализации. Архитектурным контрактом является
стабильная машинная идентичность причины; полный каталог конкретных кодов определяется
реализацией и тестами, а не выводится из свободного текста исключения.

После того как код причины опубликован через CLI/IPC/status или закреплен регрессионным тестом,
его изменение считается изменением совместимости и должно быть явным.

Поле `detail` предназначено только для диагностики человеком и не должно определять
идентичность или дедупликацию события.

Ожидаемые ошибки на границе взаимодействия ядра и пользовательского пространства
переводятся в известные диагностические причины на соответствующей границе оркестрации.
Исключения из-за ошибок программирования, нарушенные внутренние инварианты и иные
неожиданные ошибки не маскируются как штатные `UNKNOWN`/`DEGRADED`.



### 23.9. Результат профиля

Завершенный reconciliation формирует для каждого enabled profile:

```text
SUCCESS
FAIL
```

`SUCCESS` требует одновременно:

- profile contribution к full desired firewall/NAT policy применен и verified;
- exact protected-prefix route state совпадает с desired;
- для каждого protected destination есть хотя бы один verified desired direct UNICAST
  path через active concrete interface;
- BLACKHOLE и остальные required resources соответствуют desired.

Для profile с несколькими BindingSpec присутствие всех потенциальных paths не требуется.
Partial binding availability остается `SUCCESS`, если хотя бы один verified desired
UNICAST path существует для каждого protected destination.

`FAIL` возникает, если после completed verification хотя бы один protected destination
не имеет desired UNICAST path либо profile route/policy state не соответствует desired.

Availability `FAIL` при global `SAFE` policy является `DEGRADED`, не `ISOLATED`.
Полное отсутствие active bindings является валидным fail-closed runtime state и не
является config/startup error само по себе.

Transport handshake/peer health не меняет `ProfileResult`. `SUCCESS` подтверждает
kernel desired state, а не end-to-end reachability.

Ошибка наблюдаемости, не позволяющая достоверно построить profile state, относится к
reconciliation pass целиком и дает `ISOLATED`.

## 24. Замечания по реализации, уже зафиксированные архитектурой

- EXP-001 подтвердил canonical `iptables-save` representation на Debian 13 /
  iptables-nft.
- EXP-002/002A подтвердили interface/address inventory с `ip -j addr show` и
  `addr_info[].local`.
- EXP-004 подтвердил fail-closed blackhole/route ownership и ocserv interface-family
  behavior.
- EXP-005 подтвердил deny-only iptables prefix contract `-i prefix+`.
- EXP-006 подтвердил `iptables-restore --noflush` orchestration и narrow INPUT repair.
- EXP-007/008 подтвердили live daemon lifecycle и runtime drift recovery прежнего
  implementation baseline.
- EXP-009 является основанием interface-centric route model:
  - healthy OpenConnect profile может иметь несколько simultaneous concrete interfaces;
  - direct OpenConnect route `dev vpns00` работает без transport next-hop;
  - disappearing interface removes dependent route, returning interface requires
    rematerialization;
  - metric не является path-health detector;
  - WireGuard peer selection внутри stable `wg0` принадлежит `AllowedIPs`, а duplicate
    prefix не создает primary/secondary Linux routes;
  - peer health не переводит destination ownership между WireGuard peers.
- Allowing rules/NAT/routes используют только exact active interface names.
- Штатные binding transitions используют две локальные процедуры без изменения
  `ip_forward`: `ADD = NAT -> filter -> route`, `REMOVE = filter -> route -> NAT`,
  с verification между стадиями и без пересборки surviving contributions.
  Replacement выполняется как `REMOVE old -> ADD new`.
- Startup и ошибки, при которых локальная delta не доказуема или не verified, используют
  единственную глобальную процедуру `INIT/PANIC`: закрыть forwarding подтвержденным
  `ip_forward=0` либо verified isolation filter, полностью пересобрать managed
  firewall/NAT/routes, проверить и только затем открыть forwarding.
- Confirmed INPUT-only drift without policy transition uses narrow repair.
- Interface inventory failure forbids blind binding-specific repair and leads to isolation.
- `ip_forward` remains daemon-owned and read-after-write verified.
- IPv6 prerequisites §2.6 remain mandatory.
- Python implementation may be a package but keeps one daemon entry point.


### 24.1. Несовместимые изменения относительно реализации до binding-specific networks

Следующий implementation package обязан синхронизировать код с текущей архитектурой:

- удалить старый selection через `managed_vpns`; enabled profiles определяются
  `profile.enabled`;
- добавить top-level/profile `enabled` с staged parsing §7;
- убрать profile-level `interface` и `network`;
- добавить ordered `bindings[]` из `BindingSpec{interface, network}`;
- удалить LIST selector domain form; BindingSpec selector только EXACT/PREFIX;
- active qualification использовать owning BindingSpec.network;
- fixed exact metrics считать по exact_rank среди exact BindingSpec;
- для всех prefix BindingSpec профиля использовать общий allocator с
  `dynamic_metric_min = FIRST + exact_count*STEP`;
- reserved transport networks выводить из всех enabled BindingSpec.network;
- selector conflict validation выполнять по всем enabled BindingSpec;
- добавить lifecycle `DISABLED` для top-level `enabled=false`;
- сохранить ADD/REMOVE/INIT-PANIC без глобального churn survivors;
- structural route verification failure обязан эскалировать в INIT/PANIC;
- verified-state commit обязан быть two-phase/non-partial.

## 25. Открытые решения

Следующие детали реализации и исследований требуют подтверждения:

1. Точный механизм сериализованного цикла обработки событий и подавления/объединения серий
   Netlink-событий.
2. Точный механизм постановки и объединения полной пересверки после Netlink `ENOBUFS`;
   само требование полной пересверки уже является нормативным.
3. Финальная модель привилегий systemd: root либо отдельный служебный пользователь с
   минимальным набором Linux capabilities и файловых разрешений.
4. Точный минимальный набор IPC и административных команд.
5. Пограничный случай конфликта метрики/ключа стороннего точного маршрута, ранее отложенный
   до отдельного эксперимента на целевой системе.
6. Пороги «шторма восстановления» и защелкивания состояния не вводятся без наблюдаемых
   данных.


## 26. Ключевые инварианты

1. Daemon владеет своими IPv4 firewall/NAT rules, proto 201/202 routes и
   `net.ipv4.ip_forward`; внешний конкурентный owner этих ресурсов не поддерживается.
2. Startup выполняет `LOCK -> CLEANUP -> CONFIG PROJECTION -> APPLY -> VERIFY -> COMMIT`
   и только затем разрешает forwarding.
3. `config.enabled=false` после cleanup дает intentional `DISABLED`: profiles не
   разбираются, managed network state не materialize, `ip_forward=0`.
4. `profile.enabled=false` читается как gate до body parsing; остальное тело disabled
   profile не участвует в schema/value/semantic validation.
5. При enabled config runtime projection содержит только enabled profiles.
6. При enabled config должен существовать хотя бы один enabled profile.
7. Enabled profile имеет non-empty `routes[]` и `bindings[]`; ACL lists optional и
   default empty.
8. Один BindingSpec содержит `interface` selector и собственную `network`.
9. BindingSpec selector имеет только EXACT или PREFIX; LIST selector отсутствует.
10. Selector namespaces всех enabled BindingSpec попарно не пересекаются.
11. Concrete binding identity = exact interface name + ifindex.
12. Candidate становится active только при наличии local IPv4 внутри owning
    BindingSpec.network.
13. BindingSpec.network является trust boundary applicability, а не доказательством
    transport process identity.
14. Binding networks разных specs могут пересекаться; interface ownership задается
    selector namespace.
15. Protected route не пересекается ни с одной enabled BindingSpec.network.
16. Protected routes enabled profiles глобально не имеют нетождественных overlap/nesting.
17. Point-to-point remote address, peer, handshake, operstate и LOWER_UP не являются
    binding truth.
18. Allowing INPUT/FORWARD, NAT и UNICAST route используют только exact active interface
    names; prefix syntax допустим только в deny guards.
19. Candidate-only interface остается guard-blocked и не получает allowing resources.
20. IPv6 host prerequisites проверяются до allowing projection; violation в RUN latch-ит
    ISOLATED до restart.
21. IPv6 disable check охватывает selector namespace каждого enabled BindingSpec, а не
    только active bindings.
22. Для каждого protected destination всегда существует desired BLACKHOLE proto 201
    metric 65536.
23. Каждый desired UNICAST route direct: `via=None`, exact `dev`, proto 202,
    `onlink=false`.
24. Все daemon-owned UNICAST metrics строго меньше BLACKHOLE_METRIC.
25. Exact rank считается только среди exact BindingSpec профиля в config order.
26. Exact metric = FIRST_UNICAST_METRIC + exact_rank*ROUTE_METRIC_STEP.
27. Missing exact binding не сдвигает metrics остальных exact specs.
28. Same-name/new-ifindex exact binding является новой concrete identity, но получает ту
    же config-derived exact metric.
29. Все prefix BindingSpec профиля используют один shared dynamic allocator.
30. `dynamic_metric_min = FIRST_UNICAST_METRIC + exact_count*ROUTE_METRIC_STEP`.
31. Любой exact route профиля имеет меньшую metric, чем любой dynamic prefix route.
32. Позиция prefix BindingSpec внутри `bindings[]` route priority не задает.
33. Непрерывно active prefix binding сохраняет metric.
34. Исчезнувшая prefix binding освобождает metric только после verified-state commit.
35. Новая prefix binding получает следующий свободный aligned metric от process-local
    cursor; allocator циклически wrap-ится к dynamic_metric_min.
36. Prefix allocator не заполняет ранние holes специально и пропускает occupied metrics.
37. Exhausted prefix metric space делает snapshot projection failed/ISOLATED; partial
    desired state не принимается.
38. Если profile имеет prefix BindingSpec, config оставляет минимум один dynamic slot.
39. Prefix active_order process-local: survivors сохраняют relative order, new append в
    interface-inventory encounter order, дополнительная сортировка запрещена.
40. Prefix active_order диагностический; route preference между prefix bindings не
    гарантируется и после restart может измениться.
41. Profile active serialization order: active exact bindings по exact rank, затем
    process-local prefix active_order.
42. Existing survivor firewall/NAT rules и routes не удаляются/пересоздаются только ради
    canonical reordering.
43. RouteSpec traversal/serialization order не является route semantics и не вызывает
    churn unchanged routes.
44. EXP-009: transport peer не является route-next-hop abstraction; WireGuard peer
    selection принадлежит AllowedIPs.
45. VPN-GATE failover/failback основывается на independent concrete interfaces, а не на
    нескольких peers одного WG interface.
46. Failover по metric является interface-availability mechanism, не remote health-check.
47. Netlink event — wakeup hint; source of truth — fresh full snapshot.
48. Потеря Netlink events компенсируется periodic reconciliation.
49. Same-name/new-ifindex replacement = REMOVE old -> ADD new.
50. Штатный ADD: NAT -> verify -> filter -> verify -> route -> verify -> commit.
51. Штатный REMOVE: filter -> verify -> route -> verify -> NAT -> verify -> commit.
52. Normal ADD/REMOVE не изменяет `ip_forward`.
53. Mixed safely decomposable transition выполняет все REMOVE до ADD.
54. Survivor identity/order/metric должны сохраняться; если локальность нельзя доказать,
    используется INIT/PANIC.
55. Source firewall/NAT и route state проверяются до первой local mutation.
56. Для REMOVE допускается kernel-side disappearance route удаленной binding; missing
    survivor route не допускается.
57. INIT/PANIC использует confirmed `ip_forward=0` либо verified isolation filter как
    global barrier.
58. При confirmed forwarding OFF isolation stage не требуется перед full rebuild.
59. При isolation barrier allowing filter не применяется раньше verified NAT.
60. INPUT-only confirmed drift может ремонтироваться точечно без изменения FORWARD/NAT/routes.
61. FORWARD/NAT drift, UNKNOWN, non-decomposable transition или local procedure failure
    используют INIT/PANIC.
62. Ordinary route-only drift при SAFE filter сначала исправляется route executor.
63. Любой failed route build/apply/**structural verification** эскалирует в INIT/PANIC.
64. Functional zero-path `ProfileResult=FAIL` при exact structural verification не
    является route verification failure.
65. Verification success и functional availability — разные оси.
66. Verified zero-path fail-closed state commit-ится и дает DEGRADED, а не PANIC.
67. Profile SUCCESS требует хотя бы один verified desired UNICAST path для каждого
    protected destination.
68. ACTIVE требует SAFE policy, все enabled profiles SUCCESS и `ip_forward=1`.
69. DISABLED является intentional state, не ACTIVE/DEGRADED/ISOLATED.
70. ISOLATED используется при недостаточной наблюдаемости/неверифицируемом safety state.
71. OWNED routes, verified binding state, prefix active_order и allocator state
    process-local и после restart строятся заново.
72. Prospective verified-state commit готовится и полностью валидируется до первой
    мутации committed process-local state.
73. Commit stage после successful preparation не должен иметь validation path, способный
    создать partial multi-profile commit.
74. Failed apply/verification не изменяет committed binding/allocator state.
75. Само наличие ресурса в kernel не означает принятия его daemon во владение.
76. desired_full_policy и desired_isolation_filter выводятся из одной config/domain model.
77. VPNG-RESERVED закрывает destinations всех enabled BindingSpec.network до profile ACL.
78. VPNG-INGRESS exact block: INVALID DROP; ESTABLISHED,RELATED ACCEPT; остальное REJECT.
79. Для каждого protected destination после dynamic ACCEPT существует unconditional REJECT.
80. VPNG-FORWARD-DENY окончательно закрывает оставшийся transit IPv4.
81. NAT profile chain содержит MASQUERADE для каждого unique active egress interface и
    terminal RETURN; foreign POSTROUTING остается достижим для unmanaged traffic.
82. Cleanup сначала подтверждает `ip_forward=0`, затем удаляет proto 202,
    daemon-owned firewall/NAT, затем proto 201, после чего проверяет отсутствие owned state.
83. Blackhole не снимается до подтвержденной очистки остальных owned resources.
84. Cleanup не flush-ит целиком routing/filter/nat tables.
85. Reserved namespace `VPNG-*` полностью принадлежит daemon.
86. Config file security, runtime directory 0700, O_NOFOLLOW lock и lifetime flock
    остаются обязательными.
87. `--check-config` использует ту же staged enabled projection, но не берет instance
    lock и не меняет kernel.
88. Disabled profile намеренно не lint-ится; для проверки его body его включают в копии config.
89. SIGHUP не reload-ит config; config changes применяются только restart.
90. Reconciliation/event handling serialized; параллельные reconciliation запрещены.
91. Programming errors/internal contract violations не маскируются как ожидаемые
    UNKNOWN/DEGRADED.
92. Diagnostic reason code является stable machine identity; free-form detail не участвует
    в идентичности.
93. Threat model: untrusted local processes не имеют CAP_NET_ADMIN и не управляют interface
    lifecycle.
94. Остаточное окно event->reaction и невозможность iptables привязать name rule к
    historical ifindex являются явными границами модели.
95. Current Python package decomposition не является архитектурным API; domain boundaries
    должны переноситься в будущие Rust struct/enum/modules.
