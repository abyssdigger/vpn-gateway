# VPN-GATE NG3 — первая исполняемая alpha-сборка

**Статус:** первая функционирующая alpha deployment/runtime-сборка  
**Целевая среда:** Linux + systemd, root deployment  
**Managed netns:** `/run/netns/vpn-gate-alpha`

Эта сборка предназначена для первого реального запуска уже принятой NG3 архитектуры. Она не
является финальным Release-1 packaging contract и не вводит новую конфигурационную семантику.

## Что уже реально работает

Alpha controller:

- запускается как `vpn-gate-alpha.service`;
- создает и проверяет managed network namespace;
- загружает каноническую Release-1 Device/Profile конфигурацию;
- запускается безопасно даже при отсутствии текущего VPN endpoint;
- материализует fail-closed network policy, точный local allow для VPN client transport и полный `publish_vpn_server` путь: managed local admission + отдельный host-side DNAT owner;
- удерживает controller lifetime lock;
- раз в секунду выполняет локальный fresh audit;
- при появлении, исчезновении или пересоздании VPN endpoint заново вычисляет binding и lower
  desired state;
- при drift закрывает forwarding перед structural convergence;
- не требует restart controller после `systemctl restart` отдельного VPN service;
- при stop выполняет bounded controller cleanup после того, как systemd dependency ordering
  остановил bound VPN service.

## Ограничения этой alpha

Это ограничения текущей сборки, а не новые product constraints:

- имена managed namespace/veth и boundary IPv4 сейчас фиксированы:
  - `vpn-gate-alpha`;
  - `vnga-host0`;
  - `vnga-inner0`;
  - `198.19.255.1/30 <-> 198.19.255.2/30`;
- canonical grammar уже принята; alpha materializes Device `use_outbound_nat`, ordinary
  Device `firewall`, `allow_vpn_client` и `publish_vpn_server`;
- `availability_check`, Profile `+snat` и `+route-return` распознаются как canonical syntax, но alpha
  fail-fast отклоняет их до завершения соответствующих lower runtime paths;
- host-side publication требует уже существующего внешнего host forwarding; alpha проверяет
  `net.ipv4.ip_forward` и явные host IPv4/interface selectors, но не включает global host
  forwarding, не назначает host addresses и не поднимает host interfaces;
- при `use_outbound_nat = false` удаленная сторона должна иметь нормальный обратный маршрут;
- config hot reload не поддерживается: изменение `config.toml` требует restart controller;
- RuntimeStatusAgent/UI еще не подключен; `journalctl` содержит только текущие alpha
  diagnostics;
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
- точный client-transport admission до запуска VPN;
- реальную server publication через host DNAT + managed local admission до появления VPN endpoint;
- VPN MainPID внутри managed netns;
- первое runtime reconciliation после появления `vpn0`;
- реальный controlled payload;
- VPN-only restart без restart controller;
- fresh ifindex generation + второе runtime reconciliation;
- удаление host publication owner до managed-domain teardown и чистую остановку всего stack.

См. `design/experiments/EXP-051 NG3 first functioning alpha/`.
