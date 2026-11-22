# EXP-085 — full-tunnel aggressive escape guard

## Цель

Проверить, что независимая защитная блокировка aggressive host-routing корректна и для
`0.0.0.0/0`: блокирует уход через ordinary uplink после RPDB drift, но сохраняет
host-local delivery и трафик, уже пришедший от VPN-GATE через managed boundary.

## Проверки

- корректный local/forwarded outbound идет через managed boundary;
- full-tunnel guard не блокирует host-local delivery;
- full-tunnel guard не блокирует managed-boundary -> ordinary return traffic;
- earlier foreign RPDB rule меняет route lookup, но local/forwarded escape блокируется;
- после удаления foreign rule managed delivery восстанавливается при оставшемся guard.

PASS является evidence для E.004 lower semantics, но не материализует E.004.
