# VPN-GATE change log

Краткий технический журнал развития реализации. Здесь фиксируются существенные
architecture/implementation milestones, состояние тестов и следующий незакрытый блок.


## 2026-11-08 — EXP-005 PASS; architecture RC2.6.3 adopts iptables-native prefix selector

EXP-005 validated the remaining deny-only interface-family firewall contract on target
Debian 13 / iptables-nft 1.8.11.

Confirmed:

- `iptables-restore` accepts `-i vpns+`;
- `iptables-save` preserves the same canonical operand;
- `vpns+` matches the entire textual prefix namespace, including bare `vpns`, numeric
  suffixes and nonnumeric suffixes;
- an earlier exact `-i vpns0` ACCEPT takes precedence, while another prefix member reaches
  the later deny-only guard.

Architecture advanced to RC2.6.3:

- old vpn-gateway-only percent-sentinel numeric-family syntax is removed;
- `prefix+` is the single prefix-family selector and deliberately mirrors iptables
  semantics;
- the whole textual prefix namespace is reserved by a managed prefix selector;
- trailing `+` exact interface names are unsupported because iptables interprets that
  operand as wildcard/prefix matching;
- wildcard/prefix remains forbidden for ACCEPT/NAT/routes; those always use the resolved
  concrete exact interface.

Python implementation remains RC2.5.1 and is intentionally unchanged.

Next: implementation can proceed without a remaining selector-family firewall experiment.



## 2026-11-08 — RC2.6.2 architecture vivisection APPROVED

Two independent adversarial review passes were archived against RC2.6.2.

Safety/state-machine verdict: **APPROVE**.

- isolation barrier replacement semantics are sufficient;
- isolation verification cannot be confused with full-policy SAFE;
- failure to disable forwarding remains fail-closed under deny-first ordering;
- bootstrap full-filter-before-NAT remains safe because cleanup has already confirmed
  `ip_forward=0`;
- no new ordinary-default-route leak path was found;
- same-name/ifindex replacement remains an explicitly accepted trusted-host reaction-window
  limitation.

Implementation/data-model verdict: **APPROVE**.

- selector -> concrete binding -> kernel resource boundaries are implementable;
- one immutable desired reconciliation snapshot is coherent with fresh ACTUAL verify reads;
- multi-file Python package split is recommended;
- no architecture-level implementation blocker remains.

The only pre-code external contract still requiring target validation is the deny-only
selector-family iptables interface match/canonicalization.

Reviews:

- `design/RC2/code/reviews/RC2.6.2-architecture-safety-vivisection-2026-11-08.md`
- `design/RC2/code/reviews/RC2.6.2-architecture-implementation-vivisection-2026-11-08.md`

Next: target experiment for the deny-only family guard, then staged RC2.6.x implementation.



## 2026-11-08 — Architecture RC2.6.2 final isolation-barrier clarification

RC2.6.2 incorporates the two remaining RC2.6.1 safety re-review clarifications:

- isolation-filter materialization is a complete replacement/canonicalization of the
  daemon-owned filter desired state for that stage, so stale binding-specific daemon ACCEPT
  rules cannot survive underneath the barrier;
- successful isolation-filter verification is explicitly **not** equivalent to full desired
  firewall/NAT SAFE;
- full-policy SAFE requires verified desired NAT plus verified full desired filter for the
  same immutable reconciliation snapshot.

Python implementation remains RC2.5.1 and is intentionally unchanged.

Next: independent RC2.6.2 architecture vivisection before implementation.



## 2026-11-08 — RC2.6.1 architecture re-review

Two independent re-review passes were archived against RC2.6.1.

Result:

- all previous HIGH findings are resolved;
- no new architecture blocker was found;
- safety review requests two narrow clarifications before implementation:
  isolation-filter verification is not equivalent to full-policy SAFE, and isolation
  materialization must replace stale daemon binding-specific ACCEPT state rather than merely
  append denies;
- implementation review considers RC2.6.1 implementable and leaves selector overlap corner
  cases/package migration discipline to unit tests and implementation sequencing.

Reviews:

- `design/RC2/code/reviews/RC2.6.1-architecture-safety-rereview-2026-11-08.md`
- `design/RC2/code/reviews/RC2.6.1-architecture-implementation-rereview-2026-11-08.md`

No architecture change is made by this re-review commit.



## 2026-11-08 — Architecture RC2.6.1 review corrections

Both RC2.6 architecture reviews were accepted and incorporated before implementation.

RC2.6.1 adds:

- deny-first binding-sensitive repair:
  isolation filter -> NAT -> full filter -> routes, with verify between stages;
- the deny-first barrier remains mandatory when `ip_forward=0` cannot be confirmed;
- interface inventory/read/parse/resolution failure is an ISOLATED-class failure because
  full binding-specific policy cannot be derived safely;
- a config-only isolation filter is explicit and contains no binding-specific ACCEPT;
- one immutable pass-level reconciliation snapshot holds interface resolution/readiness,
  desired routes and full desired policy;
- numeric-family selectors reserve their runtime interface-name namespace;
- same-name/ifindex replacement and the kernel-event reaction window are explicit trusted-host
  threat-model boundaries;
- filtered proto-201/202 cleanup remains strict inside the reserved marker namespace;
- status must expose selector/binding/readiness separately from ACTIVE lifecycle state.

The old `filter -> nat` repair contract is removed. Python implementation remains RC2.5.1
and is intentionally unchanged.

Next: short independent re-review of RC2.6.1, then target experiment for deny-only
interface-family iptables matching before implementation.



## 2026-11-08 — RC2.6 independent architecture reviews

Two independent review passes were archived before implementation:

- safety/state-machine review:
  `design/RC2/code/reviews/RC2.6-architecture-safety-review-2026-11-08.md`;
- implementation/data-model review:
  `design/RC2/code/reviews/RC2.6-architecture-implementation-review-2026-11-08.md`.

The safety review found one high-severity ordering issue: after RC2.6 makes NAT and ACCEPT
rules binding-specific, the old `filter -> nat` repair sequence is unsafe if
`ip_forward=0` cannot be confirmed. It recommends a deny-only filter baseline before NAT
and before restoring full ACCEPT rules.

It also requires interface-inventory failure to isolate the daemon because expected policy
can no longer be derived without a trustworthy binding snapshot.

No RC2.6 architecture changes are made by the review commit itself; maintainer disposition
and architecture correction are the next step.



## 2026-11-08 — Architecture RC2.6 after EXP-004

Architecture revised from RC2.4.1 to RC2.6 before further Python implementation.

Key changes:

- complete IPv4 FORWARD ownership: terminal `VPNG-FORWARD-DENY` before foreign rules;
- `interface` is now an exact or numeric-family selector (`vpns%`);
- selectors resolve only to concrete runtime interfaces; wildcard selector text never enters
  RouteSpec/allow/NAT kernel operations;
- selector overlap inside the managed set is a fatal config error;
- runtime binding tracks exact name + ifindex; ambiguity is fail-closed;
- firewall/NAT policy now has structural plus binding-specific parts;
- MASQUERADE and profile allow rules follow a verified ready concrete binding;
- binding transitions isolate forwarding before policy/route rematerialization;
- fixed deny-only selector INPUT guard is required; exact iptables prefix syntax remains a
  target experiment before implementation;
- cleanup route inventory uses selective proto 201/202 queries, while normal reconciliation
  retains strict full-table inventory;
- daemon safely creates/validates its private runtime directory before lock;
- Python implementation may be split into a package/directory with one daemon entry point,
  keeping domain boundaries suitable for a future single-binary Rust implementation.

The bounded kernel-event -> daemon-reaction window for dynamic interface families is explicit
in the architecture rather than hidden behind static-interface assumptions.

Post-EXP expert review:
`design/RC2/code/reviews/EXP-004-post-review-2026-11-08.md`.

Next: independent architecture review before any RC2.6 implementation work.


## 2026-11-08 — EXP-004 gateway boundary validation PASS

EXP-004 completed five live boundary checks after the RC2.5.1 happy-path run.

Validated/observed:

- unmanaged forwarded traffic currently falls through daemon chains into base
  `FORWARD ACCEPT`; because vpn-gatewayd owns global `ip_forward`, complete IPv4
  forwarding-policy ownership is now required;
- on OpenConnect interface loss, the dependent `proto 202` route disappears while the
  `proto 201` blackhole survives and prevents default-route fallback;
- when the VPN reconnects, RC2.5.1 does not restore `proto 202` without daemon
  reconciliation/restart, confirming the known runtime-reconciliation gap;
- ocserv `device` is a prefix, not an exact interface name: occupying `vpns0` produced
  `vpns1`, and `device = vpns0` produced `vpns00`;
- configuration direction is one `interface` key with trailing `%` for a numeric family
  (for example `vpns%` -> `^vpns[0-9]+$`); more than one match is ambiguous and
  fail-closed;
- filter and nat cleanup payloads using duplicate `-D`, then `-F/-X`, succeeded in one
  `iptables-restore --noflush` transaction while preserving foreign rules;
- a synthetic undeleted external reference made `CHAIN_DEL` fail with rc=4 and left the
  table unchanged, confirming per-table transactional behavior on the tested backend;
- `ip -j -N -4 route show table main proto 201/202` cleanly isolates daemon marker routes
  from unrelated foreign multipath state and is suitable for cleanup-specific inventory.

Setup also exposed that standalone foreground startup currently assumes
`/run/vpn-gateway` already exists. Post-EXP review should make the daemon safely
create/validate this private `0700` runtime directory and its expected owner while retaining systemd
`RuntimeDirectory=` as the deployment default.

Full procedure/results: `design/vpn-gateway-experiments.md`.

This EXP supersedes the previous sequencing note that called graceful shutdown
"EXP-004". The next step is a post-EXP architecture/implementation review; lifecycle
shutdown/up-down-up validation moves to EXP-005 unless that review identifies a prerequisite.


## 2026-11-08 — EXP-003 first live end-to-end gateway PASS

RC2.5.1 completed the first real end-to-end happy-path test on the Debian 13 lab topology.

Validated live:

- `net.ipv4.ip_forward=1` after successful startup;
- owned `proto 201` blackhole for `10.0.0.0/8`;
- preferred `proto 202` route via `172.20.130.5 dev vpns0 metric 10 onlink`;
- expected `VPNG-*` INPUT/FORWARD/NAT chains and prefix jumps;
- server-side MASQUERADE on `vpns0`;
- OpenConnect-client forwarding plus egress MASQUERADE;
- real Windows LAN traffic to `<protected-target-ip>` traversing
  `<gateway-lan-ip> -> 172.20.130.5 -> <lan-router-ip> -> <protected-target-ip>`.

The same target previously went directly through `<lan-router-ip>`; after installing the
test route through `<gateway-lan-ip>`, reachability remained intact and the trace visibly
followed the intended VPN gateway path.

External CLI boundary forms are now to be manually validated on the target Debian before
being encoded in the subprocess adapter; this rule was applied before the RC2.5.1 retry.

EXP-003 is recorded in `design/vpn-gateway-experiments.md`.

Independent technical review: [`RC2.5.1-review-2026-11-08.md`](design/RC2/code/reviews/RC2.5.1-review-2026-11-08.md).
The review now includes maintainer disposition: read-before-write forwarding fixes are
accepted for RC2.5.2; moving OWNED commit after forwarding and a pseudo-atomic combined
snapshot API are rejected; route metric-collision handling requires a target experiment
before any validation rule is added.

Next order: RC2.5.2 forwarding read-before-write correction, then EXP-004 graceful
shutdown/cleanup + up/down/up idempotency. Fault injection, systemd safety-net behavior and
runtime self-healing remain intentionally deferred.

## 2026-11-07 — RC2.5.1 Debian iptables-save compatibility fix

The first real foreground bootstrap on Debian 13.7 / iptables-nft 1.8.11 failed during
config-independent startup cleanup before any gateway resources were materialized:

```text
iptables-save: invalid option -- 'w'
```

The RC2.5 subprocess adapter incorrectly assumed that `iptables-save` accepted the same
`-w/--wait` option as `iptables-restore`.

Correction:

- `iptables-save -t filter` and `iptables-save -t nat` are now invoked without `-w`;
- `iptables-restore -w N --noflush` retains bounded xtables lock waiting;
- the kernel-adapter regression test now asserts the Debian 13-compatible argv exactly.

Architecture remains RC2.4.1; implementation version is RC2.5.1.

## 2026-11-07 — RC2.5 happy-path bootstrap

Implementation RC2.5 completes the first executable happy-path gateway while retaining
architecture RC2.4.1.

Implemented:

- config-independent marker cleanup before config load and on graceful stop;
- real `net.ipv4.ip_forward` procfs adapter;
- memory-only `iptables-save` / `iptables-restore --noflush` adapter with bounded lock wait;
- fixed INPUT/FORWARD/NAT policy materialization and verification;
- daemon jumps inserted as a deterministic prefix ahead of foreign/UFW rules;
- static MASQUERADE for every managed VPN egress;
- initial route plan apply with missing BLACKHOLE guards first;
- fresh exact route verification and OWNED commit only after successful verify;
- `ip_forward=1` only after firewall and route verification;
- signal-only happy-path RUN loop until SIGTERM/SIGINT, followed by cleanup.

Runtime firewall repair, periodic reconciliation and Netlink self-healing remain intentionally
deferred. External drift during RC2.5 testing requires a service restart.

Regression:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Kernel adapter:  17/17 PASS
Bootstrap:         7/7 PASS
Total:            67/67 PASS

py_compile: PASS
--version:  PASS (RC2.5)
--help:     PASS
--check-config: PASS
```

The RC2.5 firewall comparator was also checked against the real Debian 13 canonical
`iptables-save` snapshot retained from EXP-001 and classified it as `SAFE`.

Next milestone: run RC2.5 in the foreground on the sterile Debian 13 gateway and validate
real forwarding through the already-established VPN interface before adding runtime
self-healing.

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
