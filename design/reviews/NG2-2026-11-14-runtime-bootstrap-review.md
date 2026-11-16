# NG2 — protective runtime bootstrap review

**Дата:** 2026-11-14  
**Тип:** autonomous focused implementation review  
**Scope:** protective forwarding closure before Linux NetworkRulesAdapter publication

## Review criteria

Проверялись:

- отсутствие forwarding window между process restart и первым owner reconcile;
- Direct completion semantics bootstrap и Driver;
- fresh verification вместо доверия к successful sysctl write;
- отсутствие payload/Profile policy в bootstrap;
- отсутствие преждевременного stale-policy cleanup без desired owner state;
- reuse существующего Linux Adapter backend boundary;
- failure contract: Adapter не должен быть доступен caller при недоказанном close;
- disposable privileged restart evidence;
- dead/duplicate artifacts после интеграции.

## Findings

### B1 — startup cannot rely on the first Adapter mutation to close forwarding

**Severity:** safety  
**Disposition:** implemented.

После process restart dedicated ROU namespace может сохранить stale physical network
policy и `net.ipv4.ip_forward=1` до первого owner RequestEvent.

Добавлен явный bootstrap gate:

1. Driver устанавливает `net.ipv4.ip_forward=0`;
2. выполняет fresh readback;
3. bootstrap возвращает `LinuxNetworkRulesAdapter` только после подтвержденного `0`.

При FAILURE Adapter в результате отсутствует.

### B2 — successful sysctl write is not sufficient evidence

**Severity:** safety/evidence  
**Disposition:** implemented and tested.

`close_forwarding_verified()` не трактует successful `sysctl -w` как конечный
результат. После записи выполняется отдельное чтение `sysctl -n net.ipv4.ip_forward`.

Unit regression включает runner, который принимает write, но возвращает `1` на readback;
операция корректно завершается FAILURE.

### B3 — bootstrap must not silently become a second network-policy reconciler

**Severity:** architecture  
**Disposition:** implemented.

Bootstrap не удаляет stale route/nft state и не реконструирует previous owners.

Его единственная safety operation — доказанное закрытие forwarding. Existing stale
physical policy остается за barrier до первого обычного Adapter reconcile, где уже
существуют owner desired rules и применяется проверенный structural transaction.

Privileged integration начинается с:

- stale foreign nft table;
- `ip_forward=1`.

После bootstrap доказано:

- `ip_forward=0`;
- stale table еще существует.

После первого normal Adapter apply stale table удалена structural reconcile и forwarding
может открыться только после обычной final verification Adapter.

### B4 — bootstrap initially duplicated the Adapter backend Protocol

**Severity:** maintainability/boundary clarity  
**Disposition:** fixed during review.

Первая реализация повторяла `observe_interfaces/materialize_structural/verify_current`
в отдельном bootstrap Protocol.

Это создавало бы два параллельных описания одной lower-domain capability.

Fix: `LinuxRuntimeBootstrapBackend` наследует существующий `LinuxNetworkBackend` и
добавляет только bootstrap-specific `close_forwarding_verified()`.

### B5 — integration harness retained an obsolete direct Adapter import

**Severity:** cleanup  
**Disposition:** fixed.

После перехода harness на bootstrap factory прямой import `LinuxNetworkRulesAdapter`
стал неиспользуемым и удален.

## Component-model review

Bootstrap не является Engine:

- Events не подписывает и не публикует;
- lifetime state между request processing не поддерживает;
- выполняет одну synchronous startup assembly operation.

`close_forwarding_verified()` является Direct Driver operation: return сообщает
завершенный результат именно protective close + fresh verification.

Bootstrap assembly создает Direct Adapter только после выполнения startup invariant.
Payload/Profile semantics в Driver/bootstrap не протекают.

## Evidence

NG2 workflow на implementation baseline `318970278f8c849f053fff4fc02af52d08e7818a`:

- rootless NG2 unit suite: PASS;
- privileged Linux Adapter integration: PASS;
- privileged live payload dataplane/NAT integration: PASS.

NG1 Python validation на том же development line: PASS.

Последующие cleanup commit `c72555990d0effb5d1da788984a1a810c873c2c9` также прошел
NG2 Python и NG1 Python validation.

No target/live stand experiment is required: the property is Linux namespace/kernel
behavior and is sufficiently proven by the disposable privileged namespace gate.

## Final verdict

**PASS after cleanup.**

No unresolved finding blocks the protective runtime bootstrap unit.

Next review unit should address runtime assembly above this gate. Namespace/transport
lifecycle remains separate unless the runtime assembly contract proves it must be coupled.
