# VPN-GATE NG3 — первая исполняемая alpha-сборка

**Статус:** первая функционирующая alpha deployment/runtime-сборка  
**Целевая среда:** Linux + systemd, root deployment  
**Managed netns:** `/run/netns/vpn-gate-alpha`

Эта сборка предназначена для первого реального запуска NG3 reference runtime. Она не
является финальным Release-1 packaging contract и не вводит новую конфигурационную семантику.
После requirement/design review 2026-11-20 alpha использует выбранный Release-1 peaceful
host-routing helper. Отдельный authoritative host-routing owner сохранён только как
prototype/evidence для отложенного aggressive helper и в alpha lifecycle не подключён.

## Что уже реально работает

Alpha controller:

- запускается как `vpn-gate-alpha.service`;
- создает и проверяет managed network namespace;
- загружает каноническую Release-1 Device/Profile конфигурацию;
- запускается безопасно даже при отсутствии текущего VPN endpoint;
- материализует fail-closed network policy, точный local allow для VPN client transport и полный `publish_vpn_server` путь: managed local admission + отдельный host-side DNAT owner;
- удерживает controller lifetime lock;
- раз в секунду выполняет локальный fresh audit;
- использует stateless Linux VPNPathAdapter: каждый startup/audit получает новый полный authoritative interface snapshot, а секундный timer служит только wakeup cadence;
- при появлении, исчезновении или пересоздании VPN endpoint заново вычисляет binding и lower
  desired state;
- при drift закрывает forwarding перед structural convergence;
- по умолчанию не меняет ordinary-host routing: `helper_routing_interfaces = ":none"`;
  при явном выборе `:local`, `:external`, `:any` или точных ingress-интерфейсов
  peaceful helper направляет только выбранный traffic к Profile destinations через
  `vnga-host0`, сохраняя приоритет explicit non-default administrator routes и абсолютный
  bypass для traffic, уже вышедшего из STACK;
- peaceful helper применяется только на lifecycle boundary: alpha не наблюдает и не
  восстанавливает его host routes в секундном audit loop и не закрывает внутренний forwarding
  из-за последующей замены маршрута администратором;
- не требует restart controller после `systemctl restart` отдельного VPN service;
- при stop выполняет bounded controller cleanup после того, как systemd dependency ordering
  остановил bound VPN service;
- публикует текущую status-проекцию в `/run/vpn-gate-alpha/status.json`: accepted intent,
  подтверждённые current paths, readiness, availability-state и current blocking problems.

## Ограничения этой alpha

Это ограничения текущей сборки, а не новые product constraints:

- primary managed-L3 endpoint сейчас фиксирован:
  - namespace: `vpn-gate-alpha`;
  - host endpoint: `vnga-host0`, unnumbered routed veth;
  - stack endpoint: `vnga-inner0`, stack-local service address `198.19.255.2/32`;
  - boundary lifecycle в host `main` владеет только service route
    `198.19.255.2/32 dev vnga-host0`; peaceful helper держит отдельную lifecycle-scoped
    routing table/rules с собственным protocol marker, причём explicit non-default `main`
    routes проверяются до helper table, а SNAT /32 использует `198.19.255.2` как onlink
    next hop; peer transit-subnet gateway IP отсутствует;
  - routed-veth backend использует Proxy ARP и `rp_filter=0` только на двух boundary endpoints;
- canonical grammar уже принята; alpha materializes Device `use_outbound_nat`, ordinary
  Device `firewall`, `allow_vpn_client` и `publish_vpn_server`;
- `availability_check` и Profile `+snat` входят в canonical alpha path: `+snat` materializes
  inside STACK after managed policy using the normalized Profile identity, а текущий alpha
  возвращает replies через prototype host /32 via stack service address; сам core `+snat`
  host-side reachability не обещает;
- host-side publication требует уже существующего внешнего host forwarding; alpha проверяет
  `net.ipv4.ip_forward` и явные ordinary-host IPv4/interface selectors, но не включает global
  host forwarding и не меняет адреса/UP-state внешних ordinary host interfaces;
- при `use_outbound_nat = false` удаленная сторона должна иметь нормальный обратный маршрут;
- текущая alpha не предоставляет reload: изменение `config.toml` требует restart controller; это прямо разрешено `VPNG0005-R5.R6.R4.C1` и не считается alpha-gap;
- текущий RuntimeStatusAgent подключён через alpha JSON surface; путь/JSON presentation пока
  являются alpha interface machinery, а не стабильным Release-1 API;
- availability/failover runtime этой сборкой еще не считается end-to-end завершенным;
- автоматического поиска/клонирования/редактирования vendor VPN units нет.

## Установка

Из checkout repository от root:

```sh
sh design/NG3/deployment/alpha/install.sh
```

Installer:

- копирует текущий `rou` package в `/usr/lib/vpn-gate-alpha/rou`;
- устанавливает `vpn-gate-alpha.service`;
- создает `/etc/vpn-gate-alpha`;
- кладет example config только если пользовательского config еще нет;
- выполняет `systemctl daemon-reload`.

Он специально не устанавливает и не принимает ownership произвольного VPN unit.

## Конфигурация controller

Отредактировать:

```text
/etc/vpn-gate-alpha/config.toml
```

Минимальный accepted slice:

```toml
# Safe defaults: no ordinary-host routing changes.
helper_routing_interfaces = ":none"
helper_routing_policy = "peaceful"

[device.ovpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
allow_vpn_client = "udp:11941>203.0.113.10:1194"
# Optional when the host prerequisite/selector already exists:
# publish_vpn_server = "tcp/eth0:443>8443"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.0/24"]
device_order = ["ovpn"]
```

`allow_vpn_client` задает Device-owned transport/control facts только для bounded
local/system admission. `publish_vpn_server` отдельно создает managed local publication
admission и owner-scoped host DNAT mapping; отсутствие requested selector/host forwarding
делает startup/reconciliation unready, а не дает runtime право менять global host setup.
Оба поля не заменяют VPN-specific OpenVPN/WireGuard/OpenConnect configuration и сами по себе
не разрешают Profile payload forwarding.

`helper_routing_interfaces` задаёт только область traffic, которой помогает host-routing
helper: `:local` — host-originated traffic, `:external` — non-local ingress, `:any` —
оба класса, а точные имена вроде `eth0,br0` — только traffic с указанных ingress.
`:local` можно объединять с точными именами. Значение по умолчанию `:none` полностью
отключает route automation. `helper_routing_policy = "peaceful"` — единственная политика
Release 1 и default: helper действует на lifecycle boundary, но не возвращает позже
заменённое администратором состояние. Даже при helper `0.0.0.0/0` затрагивается только
выбранная selector-область.

Peaceful helper не включает `net.ipv4.ip_forward`. Если выбран внешний ingress при
выключенном IPv4 forwarding, alpha пишет `VPNG_ALPHA_HOST_ROUTING_WARNING`, но оставляет
sysctl администратору. Точный manual/out-of-scope host-integration contract и примеры
remote-prefix, Profile-SNAT и full-tunnel маршрутов приведены в
`design/NG3/host-integration.md`.

## OpenVPN example

Подготовить VPN-specific config:

```text
/etc/vpn-gate-alpha/openvpn.conf
```

Для принятого first-alpha OpenVPN shape существенны:

- `route-noexec`;
- policy-neutral VPN configuration;
- стабильный local transport port, если он указан в `allow_vpn_client`;
- отсутствие privileged legacy hooks, меняющих VPN-GATE-owned route/RPDB/nft/sysctl state.

Установить отдельный stack-specific wrapper:

```sh
cp design/NG3/deployment/alpha/vpn-gate-alpha-openvpn.service.example \
  /etc/systemd/system/vpn-gate-alpha-openvpn.service
systemctl daemon-reload
```

Unit содержит:

```ini
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
NetworkNamespacePath=/run/netns/vpn-gate-alpha
```

Это отдельная service identity. Не следует использовать systemd alias как будто это
независимый service clone.

## Запуск

Сначала controller:

```sh
systemctl start vpn-gate-alpha.service
systemctl status vpn-gate-alpha.service
```

`Type=notify` означает, что `systemctl start` возвращает success только после подтвержденного
controller READY: managed netns существует, startup network policy подтверждена и, если
запрошен `publish_vpn_server`, подтверждены managed local admission + host publication mapping.

Затем stack-specific VPN:

```sh
systemctl start vpn-gate-alpha-openvpn.service
```

Появление `vpn0` не требует restart controller. Periodic local reconciliation должен
обнаружить новое поколение endpoint и перестроить current policy.

## Restart только VPN

```sh
systemctl restart vpn-gate-alpha-openvpn.service
```

Controller остается запущенным. Новое `vpn0` с новым ifindex считается новой concrete endpoint
generation; оно должно использоваться только после fresh binding и reconciliation.

## Остановка всего stack

```sh
systemctl stop vpn-gate-alpha.service
```

Через `BindsTo` + ordering systemd сначала останавливает bound VPN service/cgroup, после чего
controller завершает managed-domain cleanup. Successful stop требует отсутствия managed netns
и host boundary.

## Текущий status

Пока сервис запущен, оператор может прочитать:

```text
/run/vpn-gate-alpha/status.json
```

Это current-only snapshot, а не журнал. Он показывает отдельно accepted configured intent и
`confirmed_effective_state`; при failed reconciliation подтверждённое effective state
сбрасывается в `null`, а причина появляется в `blocking_problems` и
`unknown_or_unconfirmed_fields`.

Текущая alpha отклоняет `availability_check`, поэтому для поддерживаемого alpha-slice
availability честно отображается как `disabled`. JSON schema/path пока не объявлены
стабильным Release-1 внешним API.

## Диагностика

```sh
journalctl -u vpn-gate-alpha.service
journalctl -u vpn-gate-alpha-openvpn.service
```

Текущие implementation markers:

```text
VPNG_ALPHA_READY
VPNG_ALPHA_RECONCILE status=exact
VPNG_ALPHA_RECONCILE status=reconciled
VPNG_ALPHA_RECONCILE status=failed
VPNG_ALPHA_STOP
VPNG_ALPHA_FATAL
VPNG_ALPHA_HOST_ROUTING_WARNING
```

Это не финальный user-facing status API.

## Implementation language boundary

Текущий executable alpha controller остается Python reference runtime. Это явно разрешено
`VPNG0007-R7.R8.C1` для ранних alpha/beta releases и не означает, что Python принят как
окончательная production/stable runtime implementation. Целевая production boundary
определена `VPNG0007-R7.R8` как Rust.

## Acceptance evidence

EXP-051 запускает именно установленный controller unit + отдельный OpenVPN unit в Debian 13
systemd environment и проверяет:

- zero-path fail-closed startup;
- реальный routed managed-L3 primary boundary: unnumbered host endpoint, stack service `/32`,
  device-only host service route и device-only stack default;
- точный client-transport admission до запуска VPN;
- реальную server publication через host DNAT + managed local admission до появления VPN endpoint;
- VPN MainPID внутри managed netns;
- первое runtime reconciliation после появления `vpn0`;
- реальный controlled payload;
- VPN-only restart без restart controller;
- fresh ifindex generation + второе runtime reconciliation;
- routed managed-L3 boundary без addressed transit subnet;
- удаление host publication owner до managed-domain teardown и чистую остановку всего stack.

Текущая boundary/evidence база: EXP-070/071 для managed-L3 backend; EXP-074 — точное evidence
отложенного aggressive authoritative child; EXP-075 — lower SNAT-identity route fact;
EXP-076 — core Profile-SNAT dataplane acceptance с ancillary host-route observation;
EXP-077 — complementary evidence для main-first precedence и non-destructive lifecycle
cleanup; EXP-078 — scoped selectors (`:local`/`:external`/`:any`/exact ingress);
EXP-079 — absolute managed-boundary no-recapture через RPDB `goto`/post-helper `nop`.
EXP-051 сохраняется как evidence первого functioning alpha lifecycle.

См. `design/experiments/EXP-051 NG3 first functioning alpha/`.
