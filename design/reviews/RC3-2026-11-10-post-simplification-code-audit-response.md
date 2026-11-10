# Ответ проекта на post-simplification code audit

**Дата:** 2026-11-10  
**Audit:** `RC3-2026-11-10-post-simplification-code-audit.md`

## Disposition

Все cleanup findings приняты.

Удалено:

- write-only `committed_candidates`;
- dead `_reported_route_overlaps` и `_routes_for_profile()`;
- legacy `KernelInterface.list_interface_ipv4()`;
- dead `ProfileInterfaceState.has_active_path`;
- dead `InterfaceSelector.value`;
- unused daemon `effective_sources()`;
- obsolete ConfigLoader interface constants;
- повторная completeness-проверка уже проверенного ProfileResult mapping.

IPv6 prerequisite latch перенесен перед interface inventory. Latched daemon по-прежнему
на каждом periodic pass best-effort подтверждает forwarding-off и восстанавливает
isolation filter, но не выполняет ненужный interface snapshot до restart.

## Что намеренно сохранено

- candidate/active split;
- full typed interface inventory;
- RTMGRP_LINK;
- RTMGRP_IPV4_IFADDR;
- RTMGRP_IPV4_ROUTE;
- periodic full reconciliation;
- committed active binding identities для protective-barrier decision;
- IPv6 check всех selector-matching interfaces, включая candidate-only.

Эти части теперь непосредственно следуют из selector + network semantics и не являются
остатком peer/local-address модели.

## Validation

```text
Python 3.13 compileall: PASS
Unit tests: 121/121 PASS
```

Три удаленных теста относились только к удаленному legacy `list_interface_ipv4()` API.

## Separate observation

Netlink receive/open failure resilience оставлена без изменений: это отдельное behavioral
improvement, а не cleanup старой модели. Periodic reconciliation уже дает source-of-truth
fallback, поэтому возможный periodic-only/reopen режим стоит рассматривать отдельным
решением.
