# RC3 — external optimization review: remove redundant local_address

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** architecture simplification / configuration-minimization reviewer  
**Область:** interface applicability predicate after EXP-009  
**Вердикт:** **OPTIMIZATION RECOMMENDED**

## Контекст

После EXP-009 RC3 больше не использует transport peer как route-next-hop abstraction.
VPN-GATE управляет concrete interfaces и protected routes.

Текущий профиль все еще содержит одновременно:

```toml
network = "172.20.130.0/29"
local_address = "172.20.130.1"
```

При этом `local_address` используется только как predicate перехода:

```text
matching interface
-> candidate
-> configured local_address present?
-> active concrete binding
```

Он не участвует в:

- `RouteSpec.via`;
- source-address selection;
- NAT address selection;
- ACL;
- transport peer association;
- handshake/health determination.

## Finding 1 — local_address duplicates network for the remaining purpose

Единственная оставшаяся задача predicate — не считать matching interface active до
появления ожидаемой VPN IPv4 configuration и не активировать interface с совершенно
чужой адресацией.

Уже обязательный `vpn.network` достаточен для этого:

```text
candidate is active
iff
exists local IPv4 on candidate such that IPv4 ∈ vpn.network
```

Это сохраняет важное различие:

```text
RTM_NEWLINK:
    interface exists
    no IPv4 from vpn.network
    -> candidate only

RTM_NEWADDR:
    local IPv4 from vpn.network appears
    -> active binding
```

Точная проверка одного `local_address` дает лишь дополнительное требование, что
transport использует один заранее известный host address внутри `network`. После
interface-centric boundary это требование не имеет самостоятельной функции VPN-GATE:
конкретная host-address assignment является transport configuration.

**Severity:** DESIGN COMPLEXITY / REDUNDANCY, не safety defect.

## Finding 2 — exact local host address unnecessarily narrows supported transports

Текущая schema требует, чтобы все concrete interfaces одного profile имели один exact
local IPv4.

Это сильнее фактической потребности gateway. Для route/firewall/NAT materialization
достаточно доказать, что matching interface получил адрес из объявленной transport
network.

Удаление exact-host predicate делает модель менее transport-specific, не добавляя
transport health semantics.

## Finding 3 — network already has independent normative meaning

`network` нельзя удалить вместе с `local_address`, потому что оно уже используется для:

- `VPNG-RESERVED` fail-closed destination protection;
- validation пересечений transport/protected networks;
- описания transport address space.

Следовательно, использование того же `network` как interface-applicability predicate
не вводит нового configuration datum.

## Recommended change

Удалить `local_address` из RC3 closed schema и domain model.

Новая семантика:

```text
candidate:
    interface matches selector

active concrete binding:
    candidate has at least one local IPv4 address inside profile.network
```

Для interface без IPv4 либо только с адресами вне `profile.network`:

- candidate остается видимым;
- exact ACCEPT/NAT/proto-202 route не materialize;
- selector guard продолжает закрывать interface.

Не проверять фактическую prefix length локального interface address против
`profile.network`: P2P/tunnel transports могут представлять local endpoint как /32.
Membership проверяется по host IPv4 value.

## Compatibility impact

Это намеренно breaking RC3 config simplification:

```toml
# old
network = "172.20.130.0/29"
local_address = "172.20.130.1"

# new
network = "172.20.130.0/29"
```

Legacy `local_address` должен стать unknown profile key, а не молча игнорироваться.

## Expected safety result

Fail-closed behavior сохраняется:

- `NEWLINK` без VPN IPv4 не активирует path;
- адрес вне `vpn.network` не активирует path;
- address add/delete, меняющий membership, является active-binding transition;
- transport health по-прежнему не выводится из address membership;
- selector guards действуют независимо от active state.

## Recommendation

**ACCEPT optimization.**

После удаления `local_address` предметная модель становится еще проще:

```text
selector + network + current interface inventory
-> candidate set
-> active binding set
-> exact policy/routes
```

Отдельный expected host IPv4 для этой функции не требуется.
