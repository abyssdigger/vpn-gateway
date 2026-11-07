# VPN-GATE change log

Краткий технический журнал развития реализации. Здесь фиксируются существенные
architecture/implementation milestones, состояние тестов и следующий незакрытый блок.

## 2026-11-07 — EXP-002A confirmed

EXP-002A passed against the corrected RC2.4.1 adapter:

```text
empty0 = frozenset()
p2p0   = frozenset({IPv4Address('172.20.140.1')})
EXP-002A OVERALL=PASS
```

This confirms the live Debian 13 / iproute2 address-inventory contract after the EXP-002
correction. The route/address kernel boundary is now considered validated; the next
implementation block is `_apply_plan()` / `_verify_plan()`.

## 2026-11-07 — RC2.4.1 EXP-002 correction

EXP-002 live smoke found one real mismatch in the RC2.4 address-inventory contract.

- `ip -j -4 addr show` omitted an existing interface with no IPv4 address;
- adapter changed to `ip -j addr show` and filters only `family == "inet"` in Python;
- numeric route types emitted by `ip -j -N` (`6/7/8/9`) were confirmed and were already
  accepted by the parser;
- P2P local address handling through `addr_info[].local` was confirmed;
- EXP-002 is recorded as FAIL with one actionable finding; EXP-002A is pending to validate
  the corrected adapter directly.

Regression after the correction:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Kernel adapter:  13/13 PASS
Total:           56/56 PASS

py_compile: PASS
--version:  PASS (RC2.4.1)
```

## 2026-11-07 — RC2.4 kernel route adapter

Реализован реальный iproute2 boundary для route/address части `SubprocessKernelInterface`.

### Route inventory

- используется `ip -j -N -4 route show table main`;
- `default` нормализуется в `0.0.0.0/0`;
- bare host destination нормализуется в `/32`;
- protocol IDs читаются численно благодаря `-N`;
- отсутствующий RTPROT_BOOT нормализуется в `proto=3`;
- поддерживаются UNICAST/BLACKHOLE/UNREACHABLE/PROHIBIT/THROW;
- `onlink` переносится из JSON flags;
- multipath/nexthop-group/structured-via routes не пропускаются молча и дают `KernelError`.

### Route mutations

Реализованы:

```text
add_route()
delete_route()
replace_route()
```

Команды явно задают IPv4 `table main`, route type, numeric protocol и остальные поля
`RouteSpec`. `proto=None` считается нематериализуемым состоянием и не подменяется
iproute2 default.

### Interface IPv4 inventory

Реализован `list_interface_ipv4()` через `ip -j -4 addr show`:

- используется `addr_info[].local`;
- peer/broadcast fields не влияют на readiness;
- interface без IPv4 возвращается с пустым `frozenset`.

### Tests

Добавлено 12 kernel-adapter unit tests.

Ожидаемый regression set:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Kernel adapter:  12/12 PASS
Total:           55/55 PASS

py_compile: PASS
--version:  PASS (RC2.4)
--help:     PASS
```

Следующий шаг — live smoke на Debian 13 с реальным `iproute2`, после чего можно
реализовывать `_apply_plan()` и `_verify_plan()`.

## 2026-11-07 — repository state synchronization

Repository metadata synchronized with the actual RC2.3 development state:

- changelog switched to newest-first order;
- daemon top-level description synchronized from RC2.2 to RC2.3;
- accidentally committed Python bytecode removed;
- `.gitignore` now excludes `__pycache__/` and `*.py[cod]`.

No functional daemon behavior changed in this commit.

## 2026-11-07 — RC2.3 route reconciliation planning

Реализован pure route-planning layer поверх одного immutable ACTUAL/DESIRED snapshot.

### `_derive_desired_routes()`

- ready profile -> BLACKHOLE + UNICAST;
- not-ready profile -> только BLACKHOLE;
- DESIRED вычисляется один раз на reconciliation pass;
- полученный snapshot используется далее без повторного вычисления readiness.

### `_build_plan()`

План строится по ACTUAL + DESIRED + process-local OWNED:

- missing desired -> add;
- desired + actual + owned -> keep;
- desired + actual + not owned -> authoritative canonicalization;
- competing exact foreign route -> delete;
- owned non-desired exact route -> delete;
- more-/less-specific routes не изменяются.

### Explicit replace operation

Обнаружен архитектурный пробел в прежней модели:

```text
ReconciliationPlan(adds, deletes)
```

не мог корректно представить состояние:

```text
actual ∩ desired
но RouteSpec не OWNED текущим процессом
```

Одновременный add+delete одного и того же `RouteSpec` противоречил invariants самого plan.

Поэтому `ReconciliationPlan` расширен до:

```text
route_adds
route_deletes
route_replaces
```

`route_replaces` является явной authoritative canonicalization operation, а не silent adoption.

В `KernelInterface` добавлен соответствующий contract:

```text
replace_route(RouteSpec)
```

Ownership после replace всё равно появляется только после успешного verify/commit.

### `_validate_plan()`

Реализованы safety checks:

- add/delete/replace sets попарно disjoint;
- add разрешён только для current DESIRED route, отсутствующего в ACTUAL;
- replace разрешён только для current DESIRED route, присутствующего в ACTUAL и отсутствующего в OWNED;
- foreign delete допустим только внутри authoritative exact protected-prefix scope;
- owned non-desired delete должен иметь ownership justification;
- `proto kernel` нельзя delete или replace;
- exact protected prefix, совпадающий с connected `proto kernel` route, является fatal plan conflict;
- incomplete DESIRED snapshot запрещён;
- duplicate exact resource claims между managed profiles запрещены defensively.

### `_routes_for_profile()`

Related route set включает:

- exact protected-prefix routes;
- competing exact routes;
- more-specific overlaps;
- less-specific overlaps.

Default route `0.0.0.0/0` из overlap diagnostics исключается.

### Tests

После этого этапа ожидаемый regression set:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Total:           43/43 PASS

py_compile: PASS
--version:  PASS
--help:     PASS
```

### Следующий блок

Следующий implementation milestone — реальный route kernel adapter:

```text
ip -j route
ip -j addr
ip route add
ip route del
ip route replace
```

После него должны быть реализованы:

```text
_apply_plan()
_verify_plan()
```

После этого route reconciliation впервые сможет работать с реальным kernel state,
а не только с pure-model snapshots.

---

## 2026-11-07 — стартовая точка журнала

На момент начала ведения журнала в реализации уже присутствовали следующие блоки.

### Configuration

Реализован `ConfigLoader` для `/etc/vpn-gateway/vpn-gateway.toml`.

Основные свойства:

- secure open конфигурации с `O_NOFOLLOW`;
- проверка final path component через `lstat`;
- повторная проверка реально открытого объекта через `fstat`;
- config file и parent directory должны принадлежать root и не быть writable для group/other;
- runtime загружает и валидирует только profiles из `managed_vpns`;
- malformed unmanaged profile не блокирует normal startup;
- `--check-config` выполняет полный offline lint всего catalog:
  - managed errors -> ERROR;
  - unmanaged invalid definitions/conflicts -> WARNING;
  - допустимые особые состояния, например `peers=[]`, -> NOTE;
- case-insensitive разрешение profile IDs;
- нормализация duplicate set-like values;
- проверка конфликтов managed interfaces, protected routes и VPN transport networks;
- runtime config преобразуется в typed immutable representation.

### Typed route/profile model

Реализованы базовые typed value objects:

- `RouteSpec`;
- `RouteType`;
- lifecycle/state/reason enums;
- immutable reconciliation-related value objects.

`VpnProfile` уже умеет строить `CONFIGURED` route set:

- BLACKHOLE guard для каждого protected prefix;
- peer UNICAST routes;
- peer metrics `10, 20, ...` в порядке `peers`;
- при `peers=[]` остаются только BLACKHOLE guards.

Также реализован process-local `OWNED` state:

- ACTUAL kernel state сам по себе не означает ownership;
- OWNED заменяется только после успешного verify;
- replacement выполняется atomically;
- входной route set копируется defensively.

### Daemon skeleton

Уже присутствуют:

- lifecycle/state machinery;
- managed profile registry;
- readiness helper по наличию interface и ожидаемого local IPv4 address;
- `effective_sources()`;
- guards, требующие полный result mapping ровно по всем managed profiles;
- `_commit_owned()` с проверкой полного mapping до первой mutation;
- fixed firewall/NAT, cleanup, runtime reconciliation и Netlink contracts/skeletons.

Большая часть firewall/NAT, cleanup, event loop и route apply/verify на этой точке ещё
оставалась implementation TODO.

### Kernel abstraction

Определён `KernelInterface` и subprocess-based implementation skeleton.

В abstraction предусмотрены операции для:

- route inventory;
- route mutation;
- interface IPv4 inventory;
- `net.ipv4.ip_forward`;
- `iptables-save`;
- `iptables-restore`.

Конкретная route materialization на этой точке ещё не реализована.
