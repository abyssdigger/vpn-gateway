# RC3 — внешний review после EXP-009, проход 3

**Дата:** 2026-11-10  
**Роль рецензента:** внешний эксперт по сетевым и информационным технологиям без знания истории проекта.  
**Проверяемая версия:** после исправлений review pass 2.  
**Код не анализировался.**

## Итог прохода

**Вердикт: CHANGES REQUIRED — одно замечание к state machine.**

Замечания pass 1 и pass 2 закрыты. Структура, selector/binding model, route lifecycle,
firewall/NAT fail-closed model и ProfileResult теперь согласованы.

## R3.1 — не определено завершенное состояние при подтвержденном ip_forward=0 во время RUN

§8.9 определяет:

- `ACTIVE`: `SAFE` + все profiles `SUCCESS` + `ip_forward=1`;
- `DEGRADED`: `SAFE` + хотя бы один profile `FAIL`;
- `ISOLATED`: недостаточная наблюдаемость или firewall/NAT не `SAFE`.

Остается непокрытый runtime case:

```text
firewall/NAT = SAFE
all profiles = SUCCESS
ip_forward = 0, значение достоверно прочитано
```

Такое состояние может возникнуть, например, если daemon после безопасного reconciliation
не смог восстановить вручную выключенный `ip_forward`, но повторное чтение подтверждает
`0`.

Это не `ACTIVE`, но и не `ISOLATED`: безопасность подтверждена, потеряна только
доступность IPv4 forwarding. Следовательно, это `DEGRADED`.

Нормативная state machine должна покрывать:

```text
SAFE + completed checks + all profiles SUCCESS + ip_forward=1
    -> ACTIVE

SAFE + completed checks + (any profile FAIL OR confirmed ip_forward=0)
    -> DEGRADED

unknown/unreadable ip_forward, если его состояние требуется для завершения цикла
    -> insufficient observability / ISOLATED
```

Startup остается отдельным случаем: невозможность выполнить обязательный финальный
`ip_forward=1` во время startup является hard failure и не переводится в `RUN/DEGRADED`.

## Повторно проверено без замечаний

- startup error и startup transport unavailability разведены;
- `peers=[]` валиден, но operationally дает profile `FAIL`/daemon `DEGRADED`;
- ProfileResult использует одинаковый квантор «≥1 verified UNICAST path для каждого protected destination»;
- partial multi-binding failover остается profile `SUCCESS`;
- single-binding status не заявляет transport health;
- multi-binding association без P2P evidence не угадывается;
- guard namespace для IPv6 и firewall согласован;
- 99 инвариантов последовательны;
- ссылки на разделы разрешаются;
- EXP-009 и нормативная архитектура разделены как evidence и derived model.

После закрытия R3.1 требуется повторный review state machine и итоговый целостный проход.
