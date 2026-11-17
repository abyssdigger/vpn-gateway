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
- загружает принятую Device/Profile + `integration.*` конфигурацию;
- запускается безопасно даже при отсутствии текущего VPN endpoint;
- материализует fail-closed network policy и точный local allow для VPN transport;
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
- final human-facing Device NAT/firewall/publication grammar еще не принята;
- поэтому alpha runtime использует internal `NatIntent.NONE`, omitted Device firewall и no
  publication;
- для payload без NAT удаленная сторона должна иметь нормальный обратный маршрут;
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

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.0/24"]
device_order = ["ovpn"]

[integration.openvpn-alpha]
device = "ovpn"
protocol = "udp"
remote_ipv4 = "203.0.113.10"
remote_port = 1194
local_port = 11941
```

`integration.*` задает transport facts только для bounded local/system admission. Он не
заменяет VPN-specific OpenVPN/WireGuard/OpenConnect configuration.

## OpenVPN example

Подготовить VPN-specific config:

```text
/etc/vpn-gate-alpha/openvpn.conf
```

Для принятого first-alpha OpenVPN shape существенны:

- `route-noexec`;
- policy-neutral VPN configuration;
- стабильный local transport port, если он используется в `integration.local_port`;
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
controller READY: managed netns существует, startup network policy подтверждена.

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

## Acceptance evidence

EXP-051 запускает именно установленный controller unit + отдельный OpenVPN unit в Debian 13
systemd environment и проверяет:

- zero-path fail-closed startup;
- точный transport admission до запуска VPN;
- VPN MainPID внутри managed netns;
- первое runtime reconciliation после появления `vpn0`;
- реальный controlled payload;
- VPN-only restart без restart controller;
- fresh ifindex generation + второе runtime reconciliation;
- чистую остановку всего stack.

См. `design/experiments/EXP-051 NG3 first functioning alpha/`.
