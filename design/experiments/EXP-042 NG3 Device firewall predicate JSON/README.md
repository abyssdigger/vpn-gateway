# EXP-042 — Device firewall L3/L4 predicate JSON primitives

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R1.R2.R4.R6.R2.R1]** *Чтобы пользователь мог описывать ограничения Device в привычной последовательной firewall-модели и понимать влияние порядка правил без скрытой оптимизации со стороны VPN-GATE.* | VPN-GATE должен сохранять заданный пользователем порядок `firewall = [...]`; Release-1 rule string имеет форму `<in|out> <allow|deny|reject> [tcp|udp|icmp] [from <IPv4-CIDR>[:port-bundle]] [to <IPv4-CIDR>[:port-bundle]]` с опциональным trailing comment, а первый применимый terminal verdict определяет результат Device firewall. `port-bundle` допустим только с TCP/UDP и состоит без пробелов из одного или нескольких comma-separated элементов `N` или `A-B`, где каждый порт в `1..65535`, `A <= B`, а один физический порт не может повторяться или входить в пересекающиеся элементы bundle; VPN-GATE должен сохранять declared item order и не должен переставлять правила или исправлять широкое раннее правило ради более позднего. [`closed`]
- **[VPNG0001-R1.R2.R4.R6.R2.R2]** *Чтобы пользовательские `IN/OUT` не требовали знания Linux FORWARD semantics и при этом однозначно соответствовали фактическому направлению пакета относительно VPN Device.* | VPN-GATE должен трактовать в Device firewall `OUT` как payload packet, входящий через ordinary/host boundary и уходящий через current concrete path этого Device, а `IN` — как packet, входящий через current concrete path Device и уходящий через ordinary/host boundary; source/destination addresses и ports должны означать буквальные L3/L4 поля payload packet в точке этой фильтрации, а не адреса внешнего VPN transport или значения после последующего VPN-GATE source NAT. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Purpose

Establish the minimum Linux/nftables lower evidence needed before the NG3 semantic
Device-firewall compiler can emit exact predicate expressions.

This experiment is **lower-mechanism evidence only**. It does not choose external
configuration grammar and does not declare which protocol names/combinations become
user-facing Release-1 syntax.

## Requirements

- `VPNG0001-R4.R4.R6.R2.R1`;
- `VPNG0001-R4.R4.R6.R2.R2`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`.

## Primitive questions

For an ordinary nft child chain, record exact JSON for:

1. IPv4 source CIDR;
2. IPv4 destination CIDR;
3. L4 protocol selector through `meta l4proto`;
4. TCP source port;
5. TCP destination port;
6. UDP source port;
7. UDP destination port;
8. inclusive TCP port range;
9. mixed exact/range TCP port set;
10. terminal `return` / `drop`.

The tested TCP/UDP/ICMP tokens are technical examples for lower JSON evidence. PASS does not
make them an external parser whitelist.

## Candidate rules

```text
ip saddr 192.0.2.0/24
ip daddr 198.51.100.10
meta l4proto tcp
tcp sport 12345
tcp dport 443
return

meta l4proto udp
udp sport 5353
udp dport 53
drop

meta l4proto icmp
return

tcp sport 1000-1003
tcp dport { 80, 443, 8000-8007 }
return
```

## Decision

PASS may be used by the pure compiler to build exact nft match expressions from already
normalized internal predicate semantics, including scalar/range/set port operands.

PASS does not:

- choose TOML spelling;
- accept arbitrary protocol tokens;
- define protocol/port validation policy;
- select final REJECT realization;
- authorize mutation.
