# VPN-GATE NG3 — first functioning alpha 35m checkpoint

> **Current requirement mapping (2026-11-20):** the systemd-specific requirement subtree
> used by this historical review was later normalized without changing the accepted systemd
> architecture/evidence:
>
> - historical `VPNG-U001-R1.R3.C1.C1` -> current `VPNG-U001-R1.R3.C3`
>   (external VPN runtime lifecycle ownership/supervision constraint);
> - historical `VPNG-U001-R1.R3.C1.C1.R1` -> current `VPNG-U001-R1.R3.C3.R1`
>   (external lifecycle integration contract);
> - historical `VPNG-U001-R1.R3.C1.C1.R2` -> current `VPNG-U001-R1.R3.C1.R1.R2`
>   (policy-neutral administrator onboarding configuration);
> - historical `VPNG-U001-R1.R3.C1.C1.R3` -> current `VPNG-U001-R1.R2.R4.R6.R4`
>   (Device client-side VPN transport/control intent).
>
> The concrete systemd/`NetworkNamespacePath`/`BindsTo`/`After` mechanism remains selected
> architecture and evidence, not current generic requirement wording.

**Date:** 2026-11-17  
**Cycle:** `ng3-alpha-cycle-20261117-runtime-assembly-35m`  
**CYCLE_INTERVAL:** 35m  
**CYCLE_START_COMMIT:** `923164c11b61a694e16a16702353ee94d53967fb`  
**T0:** 2026-11-17T12:12:46Z

## Cycle intent

Собрать уже принятую NG3 семантику в первый реально устанавливаемый и запускаемый alpha
runtime вместо очередного изолированного experiment-only assembly.

## Completed logical block

Получен первый работающий deployment:

```text
accepted config.toml
    ->
vpn-gate-alpha.service (Type=notify)
    ->
managed netns /run/netns/vpn-gate-alpha
    ->
zero-path fail-closed policy
    ->
separate vpn-gate-alpha-openvpn.service
    ->
real OpenVPN MainPID inside managed netns
    ->
vpn0 appears
    ->
live local Manager reconciliation
    ->
fresh binding + structural policy
    ->
real payload
```

Controller остается живым при отдельном restart VPN service и самостоятельно принимает новое
поколение endpoint.

## Requirement trace

Новая implementation work напрямую требуется уже принятыми:

- `VPNG-U001-R1.R1`;
- `VPNG-U001-R1.R2`;
- `VPNG-U001-R1.R3.C1.C1`;
- `VPNG-U001-R1.R3.C1.C1.R1`;
- `VPNG-U001-R1.R3.C1.C1.R3`;
- `VPNG-U004-R4.R4`;
- `VPNG-U004-R4.R5`;
- `VPNG-U005-R5.R1`;
- `VPNG-U005-R5.R2`;
- `VPNG-U005-R5.R3`;
- `VPNG-U005-R5.R6.R2`;
- `VPNG-U005-R5.R6.R3`;
- `VPNG-U007-R7.R1`;
- `VPNG-U007-R7.R7`.

Ограничение `VPNG-U001-R1.R2.R4.R6.C1` соблюдено: final Device
NAT/firewall/publication TOML grammar не была придумана в implementation.

## Runtime implementation

Добавлен:

`design/NG3/code/python/rou/alpha_runtime.py`

Он:

- загружает accepted structural Device/Profile config;
- загружает accepted `integration.*` transport facts;
- использует существующий `start_controller_once(...)`;
- удерживает lifetime lock;
- хранит только необходимый `DeviceBindingState`;
- раз в секунду выполняет fresh local audit;
- exact state оставляет без mutation;
- drift/endpoint change отправляет в существующий guarded `activate_network_policy(...)`;
- при managed-domain verification loss пытается подтвердить fail-closed containment;
- SIGTERM/SIGINT только выставляют stop request;
- shutdown использует существующий `stop_controller_once(...)`.

Ни retry queue, ни command replay, ни global scheduler не добавлены.

## Deployment implementation

Добавлены:

- `design/NG3/deployment/alpha/vpn-gate-alpha.service`;
- `design/NG3/deployment/alpha/vpn-gate-alpha-openvpn.service.example`;
- `design/NG3/deployment/alpha/config.example.toml`;
- `design/NG3/deployment/alpha/install.sh`;
- `design/NG3/deployment/alpha/README.md`.

Controller unit использует `Type=notify`, чтобы dependent VPN service с
`After=vpn-gate-alpha.service` запускался только после фактического READY и существования
`NetworkNamespacePath`.

## Explicit alpha limitations

Текущий alpha slice не угадывает отложенную external policy grammar.

Поэтому:

```text
Device NAT       = internal NatIntent.NONE
Device firewall  = omitted/permissive
publication      = none
```

EXP-051 использует явный remote-side return route.

Также пока отсутствуют:

- config hot reload;
- RuntimeStatusAgent presentation;
- полный availability/probe/failover runtime;
- production packaging/version lifecycle;
- все VPN integrations.

Это implementation gaps, а не новые ограничения требований.

## EXP-051

Experiment:

`design/experiments/EXP-051 NG3 first functioning alpha/`

Final runtime evidence:

- commit: `5a1a9f53c8d861e9a616cf18bfa7107764f4a38d`;
- workflow: `44082595411`;
- alpha smoke job: `134036710197`;
- all NG3 jobs: PASS.

Evidence:

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

Два production reconciliation marker доказывают:

1. reconcile после первого появления `vpn0`;
2. reconcile после VPN-only restart и смены `ifindex 2 -> 3`.

## Architecture update

`design/NG3/architecture.md` теперь содержит §12.3 с mapping первой executable alpha assembly
на уже принятые требования.

Также исправлен оставшийся старый текст §16.4: VPN provisioning/configuration остаются
admin-owned, но systemd-bounded process/cgroup lifecycle для explicitly bound in-stack VPN уже
принят EXP-049/050.

Новой requirement semantics не введено.

## Review

`design/reviews/NG3-2026-11-17-first-functioning-alpha-review.md`

Verdict: **PASS**.

## Requirement-state inventory

### `decomp`

Accumulated links:

1. `VPNG-U005-R5 -> VPNG-U005-R5.R6` — resolved.
2. `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1` — resolved.
3. `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2` — resolved.
4. `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2` — resolved.
5. `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1` — resolved second occurrence.
6. `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2` — resolved second occurrence.

Pending `decomp`: **none**.

### `unreal`

**none**

### `broken`

**none**

### `[rejected_closure]`

**none**

## Mechanical check

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

## Cycle timing

Logical block reached a reviewed PASS well before the nominal 35-minute interval. Per CD
policy the cycle is stopped at the coherent checkpoint rather than padded with unrelated work.

## Next intended logical unit

Сделать alpha практически полезнее, не расширяя scope универсальным rewrite.

Наиболее прямой следующий blocker — отдельный configuration-format unit для уже принятой
Device NAT semantics, чтобы реальная alpha могла явно выбрать `NONE` или `MASQUERADE`
без test-only remote return route.

После этого логично собирать:

1. availability/probe runtime;
2. preference/failover reconciliation;
3. RuntimeStatusAgent presentation.

Device firewall/publication grammar следует закрывать отдельными review units, а не смешивать
с NAT только ради большого config parser.

## Checkpoint verdict

**PASS — первая функционирующая NG3 alpha реально взлетела.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R1` -> `VPNG-M001-R1.R1.R1`
- `VPNG-U005-R5.R2` -> `VPNG-M001-R1.R1.R2`
- `VPNG-U005-R5.R3` -> `VPNG-M001-R1.R1.R3`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`
- `VPNG-U005-R5.R6.R2` -> `VPNG-M001-R1.R1.R6.R2`
- `VPNG-U005-R5.R6.R3` -> `VPNG-M001-R1.R1.R6.R3`
- `VPNG-U007-R7.R1` -> `VPNG-D001-R1.R1.R1`
- `VPNG-U007-R7.R7` -> `VPNG-D001-R1.R1.R7`

The original IDs in the historical body are intentionally preserved.
