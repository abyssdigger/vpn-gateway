# EXP-043 — Device firewall active REJECT realization

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

Prove an exact Linux/nftables lower realization for the already accepted Device-firewall
`REJECT` verdict.

The requirement needs an active negative response, not silent DROP. This experiment compares
candidate lower actions on real forwarded traffic.

## Requirements

- `VPNG0001-R4.R4.R6.R2.R1`;
- `VPNG0001-R4.R4.R6.R2.R2`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`.

## Candidate realization

For a rule normalized specifically to TCP:

```text
reject with tcp reset
```

For UDP, ICMP or a protocol-unspecified IPv4 rule:

```text
reject
```

The experiment records exact nft JSON for both forms.

## Behavioral checks

A disposable ordinary -> managed -> VPN forwarding topology is created.

- TCP: a real listener exists on the VPN-side target. The firewall rejects the connection
  with TCP reset; the client must fail immediately with connection-refused semantics rather
  than timeout.
- UDP: a real UDP listener exists. Bare reject must generate an active unreachable observed
  by a connected UDP client as connection refused.
- ICMP: ping through a bare reject rule must receive an explicit unreachable diagnostic,
  not merely time out.

## Scope limits

PASS does not select external `REJECT` spelling. It only selects a lower implementation for
an already normalized Device firewall action.
