# EXP-086 — WireGuard same-prefix multi-peer availability

## Status

PREPARED — execution pending.

## Requirement / architecture context

Текущая NG3-модель отделяет Profile destinations и availability policy от VPN transport
implementation. При этом current WireGuard route-realization boundary опирается на
cryptokey routing: destination ownership внутри одного WireGuard interface определяется
`AllowedIPs`, а обычная Linux route realization идентифицирует только egress interface.

Эксперимент проверяет, можно ли отказаться от WireGuard-specific peer destination ownership
для случая двух peer одного `wg0`, через каждый из которых доступна одна и та же remote
subnet, и передать выбор peer обычному route-priority / availability механизму VPN-GATE.

## Question

Можно ли при одном WireGuard interface с двумя peer, имеющими альтернативный доступ к одной
remote subnet, выбирать фактический peer только стандартной Linux route-priority перестановкой,
которую уже использует availability VPN-GATE, не меняя WireGuard `AllowedIPs` между peer?

## Hypotheses

### H1 — same-prefix peer ownership is not simultaneously representable

После попытки назначить один и тот же prefix `10.77.0.0/24` обоим peer одного `wg0`
`wg show wg0 allowed-ips` должен показывать этот prefix ровно у одного peer.

### H2 — ordinary FIB priority cannot distinguish peers behind one wg interface

При двух Linux routes к `10.77.0.0/24` через один и тот же `wg0` с разными metrics
изменение порядка metrics не должно менять WireGuard peer, через который реально проходит
payload. FIB выбирает `wg0`; peer selection остается за WireGuard.

### H3 — changing cryptokey ownership changes the selected peer

Если не менять Linux route shape/egress interface, но переназначить
`AllowedIPs = 10.77.0.0/24` другому peer, следующий payload должен пройти уже через нового
owner peer.

## Topology

Один disposable client namespace содержит:

- два независимых underlay линка к двум peer namespaces;
- один `wg0`;
- два WireGuard peer с разными public keys и UDP endpoints;
- client inner address `10.200.0.1/32`.

Оба peer namespaces независимо представляют одну и ту же remote identity:

`10.77.0.1/32`

и имеют обратный WireGuard path к `10.200.0.1/32`.

Таким образом payload destination для обоих альтернативных peer одинаков, а underlay и keys
различны.

## Procedure

1. Создать disposable namespaces и реальные WireGuard interfaces.
2. Поднять оба peer и проверить payload через первого owner.
3. Назначить `10.77.0.0/24` второму peer того же client `wg0`.
4. Проверить фактический `wg show ... allowed-ips` и доказать H1.
5. Установить две одинаковые Linux destination routes через `wg0` с различными metrics.
6. Передать payload и определить selected peer по per-peer WireGuard transfer counters.
7. Поменять только порядок Linux route metrics, не меняя WireGuard config; повторить payload и
   проверить H2.
8. Не меняя egress interface, переназначить prefix другому WireGuard peer; повторить payload и
   проверить H3.
9. Удалить все disposable namespaces/state.

## PASS criterion

PASS означает, что одновременно доказаны H1-H3.

Такой PASS является **negative feasibility result** для исходной идеи: existing generic
availability route-priority mechanism сам по себе не может выбирать между двумя peer одного
WireGuard interface для одной и той же remote subnet.

PASS не запрещает иные реализации, в частности:

- отдельный WireGuard interface на каждый peer, после чего existing path/availability model
  получает разные concrete endpoints;
- WireGuard-specific Enforcer/Driver, который по availability переключает `AllowedIPs`
  ownership между peer.

Второй вариант не является заменой WireGuard cryptokey routing обычным FIB routing: он,
наоборот, делает WireGuard peer ownership отдельным управляемым lower state и требует
самостоятельного architecture/product review.
