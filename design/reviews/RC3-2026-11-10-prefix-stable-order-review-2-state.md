# RC3 — prefix stable-order review 2

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** state/lifecycle reviewer  
**Область:** active_order + allocator verified state  
**Вердикт:** **ACCEPT — NO FINDINGS**

## State contract

Prefix process-local state образует согласованную тройку:

```text
active_order
binding -> metric
next_metric_cursor
```

Из предыдущего verified state и текущего active set строится provisional state:

1. surviving bindings сохраняются в прежнем order;
2. vanished bindings удаляются;
3. newly observed bindings добавляются в конец;
4. multiple new bindings одного snapshot сортируются только между собой;
5. allocator сохраняет metrics survivors и выделяет metrics new bindings.

Provisional order/allocator state используется одним reconciliation snapshot и
commit-ится только после successful verification вместе с OWNED/binding state.

Failed apply/verification не может изменить verified active_order или allocator state.

## Transition behavior

- add new prefix binding: append policy blocks + allocate route metric;
- remove binding: remove ее blocks/routes; survivors not reordered;
- same name/new ifindex: fresh binding; append as new;
- restart: history intentionally resets after cleanup;
- allocator exhaustion: snapshot construction fails closed.

Новая binding все равно является policy-changing transition и использует protective
barrier. Упрощение касается только отсутствия бессмысленного reorder/renumber существующих
resources, а не ослабления barrier.

## Status

Status may expose process-local order as diagnostic evidence of first acceptance by the
current daemon, but must not present it as route-priority or persistent creation history.

## Итог

**ACCEPT — NO FINDINGS.**
