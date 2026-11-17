# VPN-GATE NG3 — review первой функционирующей alpha-сборки

**Date:** 2026-11-17  
**Cycle:** `ng3-alpha-cycle-20261117-runtime-assembly-35m`  
**Runtime evidence commit:** `5a1a9f53c8d861e9a616cf18bfa7107764f4a38d`  
**GitHub Actions run:** `44082595411`  
**EXP-051 alpha job:** `134036710197`

## Scope

Review unit собирает ранее принятые NG3 контракты в первый реально устанавливаемый и
запускаемый runtime:

- controller systemd service;
- стабильный managed-netns path;
- загрузка принятого Device/Profile + integration config;
- zero-path fail-closed startup;
- отдельный stack-specific OpenVPN systemd service;
- локальный periodic fresh observe/bind/reconcile loop;
- реальный payload;
- VPN-only restart без restart controller;
- bounded stack stop.

Review **не** выбирает отложенную external grammar Device NAT/firewall/publication и не
объявляет первую alpha полной реализацией Release 1.

## Requirement trace

Реализация требуется уже закрытыми узлами:

- `VPNG0001-R1.R1`;
- `VPNG0001-R1.R2`;
- `VPNG0001-R1.R3.C1.C1`;
- `VPNG0001-R1.R3.C1.C1.R1`;
- `VPNG0001-R1.R3.C1.C1.R3`;
- `VPNG0004-R4.R4`;
- `VPNG0004-R4.R5`;
- `VPNG0005-R5.R1`;
- `VPNG0005-R5.R2`;
- `VPNG0005-R5.R2.R1`;
- `VPNG0005-R5.R3`;
- `VPNG0005-R5.R3.R1`;
- `VPNG0005-R5.R6.R2`;
- `VPNG0005-R5.R6.R3`;
- `VPNG0007-R7.R1`;
- `VPNG0007-R7.R7`.

Ограничивает review unit `VPNG0001-R1.R2.R4.R6.C1`: final human-facing spelling Device
NAT/firewall/publication еще нельзя угадывать.

## F1 — experiment-only assembly была недостаточна для alpha

До этого цикла production controller существовал как library assembly, а реальный
OpenVPN/systemd сценарий собирался только experiment harness.

Это не удовлетворяло практической цели первой alpha: оператор не мог установить controller
service, запустить его обычным `systemctl` и отдельно запустить VPN unit.

Введены:

- `rou.alpha_runtime`;
- `vpn-gate-alpha.service`;
- stack-specific OpenVPN unit example;
- minimal installer;
- runnable deployment documentation.

**Disposition:** accepted.

## F2 — one-shot startup без runtime reconciliation оставлял zero-path READY навсегда

Принятая startup semantics правильно разрешает READY при отсутствии текущего VPN endpoint:
Profile остается fail-closed до появления binding.

Но для реального service lifetime этого недостаточно: OpenVPN запускается **после** controller
READY, а значит production process должен затем заметить `vpn0`.

Новая alpha-сборка реализует уже принятую §12.2 local Manager reconciliation semantics:

```text
retained accepted config + DeviceBindingState
    +
periodic fresh link observation
    ->
fresh binding projection
    ->
pure desired-state rebuild
    ->
read-only exact audit
    |
    +-- exact + gate enabled -> no write
    |
    +-- drift/change/failure -> existing guarded activation
                               -> forwarding closed
                               -> fresh convergence
                               -> verified postcondition
```

Audit interval 1 s является implementation parameter, а не user-visible latency promise.

Нет:

- durable retry queue;
- command replay;
- global scheduler;
- event journal;
- new lifecycle state machine.

**Disposition:** accepted.

## F3 — periodic exact audit не должен сам создавать forwarding outage

Прямой вызов guarded activation на каждом тике сначала закрывал бы ForwardingGate даже при
полностью exact state.

Alpha therefore сначала выполняет read-only structural observation/comparison. Если state exact
и ForwardingGate уже ENABLED, тик заканчивается без физической mutation.

Только обнаруженный drift/неопределенность переводит управление в существующую guarded
`activate_network_policy(...)`.

Это соответствует §12.2: already-satisfied audit не мутирует state.

**Disposition:** accepted.

## F4 — managed-domain invariant loss остается fail-closed

Если periodic audit больше не может подтвердить exact managed domain, runtime не пытается
усыновлять или реконструировать произвольно поврежденную среду.

Он отдельно пытается подтвердить `ForwardingGate=DISABLED` и публикует diagnostic.

Это соответствует `VPNG0005-R5.C1`: out-of-band root/admin damage не превращается в generic
forensic recovery mechanism.

**Disposition:** accepted.

## F5 — `Type=notify` нужен для корректной systemd ordering semantics

Stack-specific VPN unit использует:

```ini
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service
NetworkNamespacePath=/run/netns/vpn-gate-alpha
```

Если controller был бы обычным `Type=simple`, systemd мог бы считать start job завершенным
до того, как Python создал managed namespace.

`Type=notify` делает READY boundary фактическим deployment contract:

```text
start controller process
    ->
controller startup + managed netns + fail-closed policy confirmed
    ->
sd_notify READY=1
    ->
controller start job complete
    ->
dependent VPN unit may start
```

**Disposition:** accepted.

## F6 — final Device NAT grammar не была придумана ради smoke

Requirement `VPNG0001-R1.R2.R4.R6.C1` явно запрещает считать неподтвержденную external
Device NAT/firewall/publication syntax нормативной.

Поэтому alpha runtime использует только lower normalized semantics:

```text
Device NAT       -> NatIntent.NONE
Device firewall  -> omitted/permissive
publication      -> none
```

EXP-051 строит NAT-free topology с explicit remote return route.

Это позволяет доказать runtime assembly, не делая скрытый product/config decision.

Недостаток очевиден: текущая alpha не является практической заменой Device MASQUERADE для
обычных remote networks без return route.

**Disposition:** accepted как ограничение первой alpha implementation, не как новый R/C.

## F7 — real installed alpha впервые замкнула controller -> VPN -> payload loop

EXP-051 запускает actual installed files, а не experiment-only controller calls.

Подтверждено:

```text
systemctl start vpn-gate-alpha
    -> READY
    -> no VPN endpoint yet
    -> fail-closed payload policy
    -> exact OpenVPN transport allow exists

systemctl start vpn-gate-alpha-openvpn
    -> MainPID inside managed netns
    -> vpn0 appears
    -> controller stays alive
    -> production local reconcile
    -> fresh binding
    -> structural convergence
    -> payload PASS
```

Evidence markers:

```text
EXP051_ALPHA_CONTROLLER_READY=PASS
EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS
EXP051_VPN_SYSTEMD_NAMESPACE=PASS
EXP051_FIRST_MANAGER_RECONCILE=PASS
EXP051_FIRST_PAYLOAD=PASS
```

**Disposition:** accepted.

## F8 — VPN-only restart proves live endpoint-generation replacement

Controller не перезапускался.

```text
OpenVPN pid 4449 / vpn0 ifindex 2
    ->
systemctl restart vpn-gate-alpha-openvpn
    ->
OpenVPN pid 4565 / vpn0 ifindex 3
```

Production controller journal содержит два `status=reconciled` event:

1. первое появление endpoint;
2. новое поколение endpoint после VPN-only restart.

Payload после второго reconcile снова PASS.

Это доказывает, что runtime использует fresh concrete identity и не зависит от старого ifindex.

**Disposition:** accepted.

## F9 — stack stop использует уже принятую systemd lifecycle boundary

`systemctl stop vpn-gate-alpha.service` приводит к:

- bound OpenVPN unit inactive;
- старый VPN PID absent;
- controller cleanup;
- managed netns absent;
- host boundary absent.

EXP-051 marker:

`EXP051_STACK_STOP_CLEAN=PASS`

Custom VPN PID registry/process supervisor не появился.

**Disposition:** accepted.

## F10 — config hot reload намеренно отсутствует

Alpha читает accepted config один раз через startup loader.

Изменение `config.toml` требует controller restart. Это не потеря принятой capability:
architecture прямо оставляет future live-change/reload вне текущего promise.

Это существенно упрощает первый functioning runtime и не вводит config revision/epoch model.

**Disposition:** accepted.

## Component-model review

Роли остаются локализованными:

- configuration parsers — Adapter/normalization boundary;
- binding/policy builders — pure Calculators;
- `AlphaPreparedPolicy` хранит ровно semantic binding state, требуемый accepted binding
  projection;
- alpha runtime loop исполняет текущую `PayloadTrafficManager` responsibility;
- Linux backends остаются Adapter/Driver lower machinery;
- systemd остается внешним supervisor VPN process/cgroup;
- lifecycle control остается procedural, без нового LifecycleManager.

Никакой lower Linux detail не был добавлен в user Device/Profile semantics.

**Verdict:** component model PASS.

## Safety review

PASS:

- zero-path controller start не разрешает payload;
- exact VPN transport allow существует до VPN start;
- structural change проходит через ForwardingGate-disabled barrier;
- exact no-op audit не создает mutation;
- managed-domain verification loss делает explicit fail-closed attempt;
- current endpoint identity использует ifindex;
- stop postcondition проверяется existing controller stop machinery;
- arbitrary VPN process adoption отсутствует.

Known alpha limitation:

- при out-of-band полном удалении namespace controller может только диагностировать и
  попытаться containment; Release 1 не требует forensic recovery.

## Simplification review

Намеренно не добавлены:

- generic daemon/process supervisor;
- PID registry;
- config watcher;
- hot-reload epochs/revisions;
- durable retry queue;
- command replay;
- status database;
- universal plugin/config abstraction;
- guessed Device NAT/firewall syntax;
- global scheduler.

Один local periodic loop достаточен для уже принятой recovery semantics.

**Verdict:** PASS.

## Evidence

Final runtime code run:

- commit `5a1a9f53c8d861e9a616cf18bfa7107764f4a38d`;
- workflow `44082595411`;
- all NG3 jobs PASS;
- alpha job `134036710197` PASS.

Alpha markers:

```text
EXP051_ALPHA_CONTROLLER_READY=PASS
EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS
EXP051_VPN_SYSTEMD_NAMESPACE=PASS:pid=4449
EXP051_FIRST_PAYLOAD=PASS
EXP051_FIRST_MANAGER_RECONCILE=PASS
EXP051_MANAGER_RECONCILE_COUNT=PASS:2
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS:old_pid=4449:new_pid=4565:old_ifindex=2:new_ifindex=3
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

Existing EXP-049/050 regression job in the same workflow also PASS.

## What remains before a materially useful broader alpha

EXP-051 proves one direct OpenVPN path, not full product breadth. The next implementation
units should remain requirements-driven and address independently accepted gaps, notably:

- final Device NAT/firewall/publication configuration grammar before those capabilities can be
  used from real alpha config;
- availability/probe runtime assembly and path preference/failover;
- RuntimeStatusAgent presentation;
- practical packaging/configurable deployment constants after evidence shows which constants
  must be exposed.

Do not fold these into one universal runtime rewrite.

## Requirement-state inventory

### `decomp`

Accumulated links:

1. `VPNG0005-R5 -> VPNG0005-R5.R6` — resolved.
2. `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` — resolved.
3. `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` — resolved.
4. `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2` — resolved.
5. `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` — resolved second occurrence in the
   requirement tree.
6. `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` — resolved second occurrence in the
   requirement tree.

Pending `decomp`: **none**.

### `unreal`

**none**

### `broken`

**none**

### `[rejected_closure]`

**none**

## Mechanical requirement check

```text
normative R/C nodes:                    154
closed:                                 154
pending_closure:                          0
rejected_closure:                         0
open/malformed:                           0
closed without architecture reference:    0
decomp links:                              6, all resolved
active unreal:                             0
active broken:                             0
```

No requirement status or product semantics changed in this cycle.

## Verdict

**PASS.**

Первая functioning NG3 alpha существует как обычный установленный systemd stack и реально
переносит payload через independently managed OpenVPN. Самое важное новое evidence: controller
остается живым, видит появление/замену VPN endpoint и сам reconciliation'ит current policy без
своего restart.

Следующий цикл должен расширять практически полезную alpha по отдельным уже принятым
requirement branches, а не снова проектировать базовый runtime lifecycle.
