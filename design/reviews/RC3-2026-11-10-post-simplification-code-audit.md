# RC3 — post-simplification code audit

**Дата:** 2026-11-10  
**Область:** startup/init, interface discovery, monitoring, reconciliation, fail-closed protection  
**Baseline:** interface-centric RC3 после удаления peers и local_address  
**Вердикт:** **PASS WITH CLEANUP FINDINGS**

## Общий вывод

Удаление transport peers и exact local host address корректно дошло до основной runtime
логики. В критическом path не осталось peer association, exact-address readiness,
AMBIGUOUS resolution или transport-specific next-hop semantics.

Текущий runtime data flow соответствует упрощенной модели:

```text
selector + profile.network + full interface inventory
-> candidates
-> active bindings (local IPv4 membership in network)
-> exact firewall/NAT + direct routes
```

### Что остается необходимо

- полный `ip -j addr show` остается нужен:
  - LINK existence/name/ifindex;
  - local IPv4 membership в `profile.network`;
  - addressless matching interface должен оставаться candidate-only;
- `RTMGRP_LINK` остается нужен для create/delete/recreate;
- `RTMGRP_IPV4_IFADDR` остается нужен для active membership transitions;
- `RTMGRP_IPV4_ROUTE` остается нужен для low-latency route drift reconciliation;
- periodic reconciliation остается обязательной страховкой;
- current `committed_active_bindings` нужен для определения policy-changing transition;
- IPv6 prerequisite check должен охватывать все selector-matching interfaces, включая
  candidate-only, поскольку IPv4 inactivity не является IPv6 protection.

## Cleanup finding 1 — write-only committed candidate state

`VpnProfile._committed_candidates` записывается после verification, но runtime никогда
его не читает. Policy transition зависит только от `committed_active_bindings`.

Candidate set остается частью immutable current snapshot/diagnostics, но хранить его как
process-local committed state не требуется.

**Action:** удалить `committed_candidates` и соответствующий argument commit API.

## Cleanup finding 2 — abandoned overlap diagnostic state

`_reported_route_overlaps` только создается/reset, но не читается.
`_routes_for_profile()` также не вызывается.

Fail-closed protection foreign more-/less-specific routes обеспечивается firewall
destination policy; route planner намеренно authoritative только для exact protected
prefix. Неактивный cache не добавляет защиты.

**Action:** удалить cache и dead helper. Если отдельная overlap telemetry понадобится
позже, вводить ее как завершенную observable feature.

## Cleanup finding 3 — obsolete pre-typed interface API

`KernelInterface.list_interface_ipv4()` и реализация в subprocess adapter полностью
дублируют часть `list_interfaces()` и больше не вызываются daemon.

Этот boundary был временным migration API до typed `InterfaceRecord`.

**Action:** удалить abstract method, implementation и dedicated legacy tests.

## Cleanup finding 4 — dead convenience/helpers

Не используются:

- `ProfileInterfaceState.has_active_path`;
- `InterfaceSelector.value`;
- daemon `effective_sources()` (policy module имеет фактически используемый
  `_effective_sources()`);
- ConfigLoader `_INTERFACE_RE` / `_FORBIDDEN_INTERFACES` после переноса validation в
  `InterfaceSelector`.

**Action:** удалить.

## Cleanup finding 5 — duplicate ProfileResult completeness check

`_reconcile_routes_snapshot()` уже возвращает mapping после
`_require_complete_profile_results()`, но caller повторяет ту же проверку.

**Action:** оставить проверку внутри route reconciliation boundary и удалить вторую.

## Cleanup finding 6 — latched IPv6 isolation inventories interfaces unnecessarily

После `_host_prerequisite_latched=True` автоматический recovery запрещен до restart.
Текущий `reconcile()` сначала выполняет full interface inventory, а затем проверяет
latch.

Isolation maintenance не зависит от inventory.

**Action:** проверять latch до `list_interfaces()`. Продолжать на каждом pass best-effort
disable forwarding + reapply/verify isolation filter, чтобы drift в isolation не
оставался без ремонта.

## Проверка новой address-membership semantics

Корректно:

- address change `.1 -> .2` внутри того же `profile.network` не меняет
  `active_bindings(name+ifindex)` и не вызывает heavy policy barrier;
- появление первого local IPv4 из network активирует binding и вызывает barrier;
- удаление последнего local IPv4 из network деактивирует binding и вызывает barrier;
- IPv4 outside network не активирует candidate;
- concrete host address не попадает в route/NAT/filter desired state.

## Отдельное observation — не cleanup finding

Netlink является только latency wakeup source, а periodic reconcile — source-of-truth
fallback. Сейчас unrecoverable receive/open error Netlink может завершить run loop вместо
перехода на periodic-only operation/reopen strategy.

Это не наследие peer/local-address модели и не требуется исправлять в рамках данной
cleanup. Имеет смысл рассмотреть отдельно как resilience improvement.

## Итог

Основная инициализация/discovery/protection logic после двух архитектурных упрощений
правильная. Найденные остатки — dead migration/state helpers, а не скрытая старая
семантика. Их удаление сокращает код без изменения fail-closed behavior.
