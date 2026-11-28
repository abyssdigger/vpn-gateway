# VPN-GATE NG3 alpha — краткая инструкция администратора

**Status:** development/alpha operator runbook; not the Release-1 publication guide  
**Release-1 administrator guide:** `release/0.1.0/DEPLOYMENT.md`  
**Verified alpha deployment:** Debian 13 + systemd, root deployment  
**Controller unit:** `vpn-gate-alpha.service`  
**Current managed netns:** `/run/netns/vpn-gate-alpha`

Этот документ описывает практический путь от checkout до работающего alpha-instance:
установка controller, Device/Profile configuration, подготовка поддержанного OpenVPN/systemd
канала, запуск, проверка, monitoring и реакция на operational log.

Это инструкция для checkout/development alpha. Для фактического выпуска 0.1.0
администраторским source of procedure является `release/0.1.0/DEPLOYMENT.md`, который
упаковывается в release bundle и проходит отдельный documentation-driven walkthrough.

## 1. Что принадлежит кому

Администратор владеет:

- VPN-specific configuration, credentials/certificates и отдельным VPN service;
- ordinary-host interfaces, global IPv4 forwarding, unrelated host firewall/NAT;
- host routing вне явно выбранного peaceful-helper scope.

VPN-GATE владеет своим managed network domain, внутренней policy и ограниченными
owner-scoped host contributions, которые явно включены конфигурацией.

Не редактируйте вручную VPN-GATE-owned netns/RPDB/nft/runtime state при работающем
controller. Recoverable drift продукт исправляет сам; произвольное out-of-band повреждение
authoritative state может стать неоднозначным и не обязано автоматически восстанавливаться.

Если такое вмешательство уже произошло:

1. сначала выполните `systemctl stop vpn-gate-alpha.service`;
2. проверьте ERROR records и результат cleanup;
3. устраните указанный конфликт/остаток только после остановки controller;
4. запускайте controller снова из чистой, однозначной boundary.

Не пытайтесь заставить новый instance «усыновить» произвольные surviving processes,
namespace references или неизвестные сетевые объекты.

## 2. Предварительные условия

Ниже команды проверены для Debian 13. Нужны root и systemd.

Для alpha controller:

```sh
apt-get update
apt-get install -y python3 iproute2 iputils-ping nftables procps
```

Для OpenVPN example дополнительно:

```sh
apt-get install -y openvpn
```

## 3. Установка VPN-GATE alpha

Из корня checkout:

```sh
sh design/NG3/deployment/alpha/install.sh
```

Installer копирует reference runtime в `/usr/lib/vpn-gate-alpha/rou`, устанавливает
systemd unit и создаёт `/etc/vpn-gate-alpha/config.toml`, если файла ещё нет.

После установки сначала отредактируйте конфигурацию; unit автоматически не запускается.

## 4. Настройка controller

Основной файл:

```text
/etc/vpn-gate-alpha/config.toml
```

Минимальный пример для одного OpenVPN Device и outbound Profile:

```toml
log_level = "info"

# :local автоматически направляет host-originated traffic к Profile destinations.
# Для полностью ручной host routing используйте ":none".
helper_routing_interfaces = ":local"
helper_routing_policy = "peaceful"

[device.ovpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

# local transport port должен совпадать с lport в OpenVPN config.
allow_vpn_client = "udp:11941>203.0.113.10:1194"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16"]
device_order = ["ovpn"]
```

Замените documentation addresses на реальные значения.

Если `use_outbound_nat = false`, удалённая сторона должна иметь обратный маршрут к
ordinary-side source addresses. Если нужен Device NAT, используйте
`use_outbound_nat = true`.

### Политика освобождения управляемых VPN (разработка)

Для управляемых обычных VPN Device принят верхнеуровневый параметр
`managed_reclaim = "careful" | "strict"` (по умолчанию `"careful"`).
Он не меняет `warm_paths` и не распространяется на внешние VPN-сервисы.

**Пока не используйте этот параметр как подтверждение активного reclaim:** в текущей
ветке #41 имеются разбор конфигурации и вспомогательные функции, но штатный
startup/periodic runtime ещё не переведён на новый механизм. Целевую семантику,
ограничения и поля статуса см. в [черновике эксплуатационной документации](../../docs/ru/operations/managed-device-reclaim.md).
До интегрированной проверки не следует выводить возможность освобождения из одной
лишь структурной потребности, настроенной политики или не подтверждённого статуса.

### Availability monitoring

Чтобы состояние пути было не `unchecked`, задайте проверку, например:

```toml
[device.ovpn.availability_check]
mechanism = "icmp"
target = "10.20.0.1"

[profile.corp]
# остальные поля как выше
availability_check = "default"
```

Target должен быть осмысленным для данного VPN path.

### Logging threshold

`log_level` принимает только:

```text
error
warning
info
debug
```

Default при отсутствии поля — `info`.

Обычная эксплуатация: `info`. Для разбора реакции компонентов временно используйте
`debug`. Изменение `config.toml` в текущей alpha применяется через restart controller:

```sh
systemctl restart vpn-gate-alpha.service
```

Отдельного `trace` level нет: developer execution trace — другая, пока отложенная функция.

## 5. Подготовка OpenVPN

VPN-GATE не генерирует и не редактирует vendor VPN configuration. Подготовьте обычный
рабочий OpenVPN client config и сохраните его как:

```text
/etc/vpn-gate-alpha/openvpn.conf
```

Для поддержанного alpha shape существенны:

```text
dev vpn0
dev-type tun
proto udp4
remote <VPN_SERVER_IP> <VPN_SERVER_PORT>
lport <LOCAL_TRANSPORT_PORT>
route-noexec
```

Далее добавьте обычные site-specific OpenVPN TLS/auth/cipher/credential settings.

Критические integration rules:

- `dev` должен соответствовать `expected_interfaces` Device;
- `lport` и remote endpoint должны соответствовать `allow_vpn_client`, если он задан;
- `route-noexec` оставляет Profile routing под ownership VPN-GATE;
- VPN hooks не должны менять VPN-GATE-owned route/RPDB/nft/sysctl state.

Установите stack-specific systemd wrapper:

```sh
cp design/NG3/deployment/alpha/vpn-gate-alpha-openvpn.service.example \
  /etc/systemd/system/vpn-gate-alpha-openvpn.service
systemctl daemon-reload
```

Wrapper запускает OpenVPN внутри уже созданного managed netns через
`NetworkNamespacePath=/run/netns/vpn-gate-alpha`.

## 6. Запуск

Сначала controller:

```sh
systemctl start vpn-gate-alpha.service
systemctl status --no-pager vpn-gate-alpha.service
```

Успешный `systemctl start` означает подтверждённый READY, а не только существующий процесс.

Затем VPN:

```sh
systemctl start vpn-gate-alpha-openvpn.service
systemctl status --no-pager vpn-gate-alpha-openvpn.service
```

Controller restart после появления VPN interface не нужен. Периодический fresh audit
обнаружит `vpn0`, выполнит binding/reconciliation и опубликует новое состояние.

## 7. Как убедиться, что всё заработало

### 7.1. Current human status

```sh
cat /run/vpn-gate-alpha/status.txt
```

Ожидаемый shape после обнаружения пути:

```text
Devices
    ovpn: vpn0
Profiles
    corp
        01. vpn0 unchecked
```

При настроенном availability check вместо `unchecked` ожидайте
`available (<check>)`, `not available (<check>)` или `unknown (<check>)`.

`unknown` означает, что current state не подтверждён; не интерпретируйте его как
`not discovered`.

Machine-readable alpha snapshot:

```sh
cat /run/vpn-gate-alpha/status.json
```

Оба файла обновляются только при изменении semantic runtime snapshot; секундный audit сам
по себе не переписывает их.

### 7.2. Реальный traffic

Проверьте именно тот destination, который входит в Profile policy:

```sh
ping -c 3 10.20.0.1
```

Используйте реальный адрес вашей удалённой стороны. Успешный status без end-to-end traffic
может означать проблему remote routing/firewall вне ownership VPN-GATE.

Если `helper_routing_interfaces = ":none"`, ordinary host должен сам доставлять выбранный
traffic к `vnga-host0`; точный contract и примеры находятся в
`design/NG3/host-integration.md`.

## 8. Protective mode

Protective mode — явная аварийная/административная блокировка IP traffic через управляемую
область без teardown runtime state.

Проверить состояние:

```sh
vpn-gate-control protective status
```

Включить:

```sh
vpn-gate-control protective enter
```

Success означает, что отдельный owned protective gate уже fresh-подтвержден. После этого
ordinary-boundary IP traffic в обоих направлениях и forwarding между VPN paths закрыты, но
managed netns, interfaces, intent и diagnostic context сохраняются.

Снять:

```sh
vpn-gate-control protective leave
```

Success означает, что controller сначала заново подтвердил применимое ordinary desired state,
а затем успешно снял protective gate. Non-zero результат leave нельзя трактовать как снятый
режим: блокировка сохраняется либо переустанавливается fail-closed.

Для независимых automation request sources:

```sh
vpn-gate-control protective enter --source automation:maintenance
vpn-gate-control protective leave --source automation:maintenance
```

Запросы source-scoped: один source не может снять активный запрос другого. Во время active
режима Manager периодически fresh-наблюдает отдельный protective gate и восстанавливает его
после exact-owned drift.

Текущий control socket root-only:
`/run/vpn-gate-alpha/control.sock`.

## 9. Monitoring

Текущий человекочитаемый state:

```sh
watch -n 1 cat /run/vpn-gate-alpha/status.txt
```

Operational log в реальном времени:

```sh
journalctl -fu vpn-gate-alpha.service
```

Только warning/error по journal priority:

```sh
journalctl -u vpn-gate-alpha.service -p warning --no-pager
```

VPN implementation log смотрится отдельно:

```sh
journalctl -fu vpn-gate-alpha-openvpn.service
```

Не смешивайте два источника: controller log объясняет VPN-GATE policy/reaction, OpenVPN log —
protocol/session implementation.

## 10. Что означает operational log

Форма записи:

```text
LEVEL TAG event context...
```

Текущие короткие component tags:

| Tag | Область |
| --- | --- |
| `LIFE` | lifecycle/start/stop |
| `BIND` | discovery и current VPN path binding |
| `AVAIL` | confirmed availability transitions |
| `PROF` | Profile effective-order reaction |
| `POLICY` | policy reconciliation/application |
| `HOST` | ordinary-host integration prerequisites |

### ERROR

Продукт не смог выполнить требуемую операцию, достичь required internal state или подтвердить
обязательный postcondition.

Действия:

1. прочитайте `status.txt`;
2. посмотрите ERROR record и соседние records controller;
3. проверьте внешний prerequisite, указанный diagnostic context;
4. после исправления environment/config дайте normal reconciliation шанс восстановиться;
5. если ошибка относится к startup/configuration или current alpha config был изменён —
   выполните поддержанный restart.

Не считайте ERROR исправленным только потому, что process остаётся active.

### WARNING

Обнаружено существенное несоответствие environment ожидаемому, но подтверждённого product
failure ещё может не быть.

Пример текущей alpha: выбран external host-routing scope при выключенном
`net.ipv4.ip_forward`.

WARNING требует проверки environment; не надо автоматически перезапускать controller, если
сама причина не требует lifecycle operation.

### INFO

Существенное изменение environment/lifecycle.

Примеры:

```text
INFO LIFE ready ...
INFO BIND path_binding_changed ...
INFO AVAIL path_unavailable ...
INFO AVAIL path_available ...
```

Одиночный ожидаемый transition — обычная работа. Частое повторяющееся появление/исчезновение
пути или availability transition указывает на нестабильность VPN/environment и требует
диагностики.

### DEBUG

Component-level реакция продукта на событие, например:

```text
DEBUG PROF effective_order_changed ...
DEBUG POLICY reconcile_result_changed ...
```

DEBUG отвечает на вопрос «что пересчитал/применил компонент», но не трассирует каждую
function/branch. Обычно держите `log_level = "info"`; включайте `debug` на время разбора.

## 11. Restart и stop

Restart только VPN:

```sh
systemctl restart vpn-gate-alpha-openvpn.service
```

Controller должен остаться запущенным и обнаружить новую concrete endpoint generation.

Применение изменённого VPN-GATE config:

```sh
systemctl restart vpn-gate-alpha.service
```

Остановка всего stack:

```sh
systemctl stop vpn-gate-alpha.service
```

`BindsTo` останавливает bound OpenVPN service, после чего controller выполняет owned cleanup.
Успешный stop должен удалить managed netns/boundary и перестать влиять на traffic.
