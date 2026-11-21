# EXP-041 — ordered Device firewall child-chain primitives

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R1.R2.R4.R6.R2]** *Чтобы transport-level ограничения могли дополнительно защищать tunnel traffic, не превращаясь в обход Profile policy.* | VPN-GATE должен для каждого Device поддерживать дополнительную ordered firewall policy для payload traffic, проходящего через его concrete paths; effective permission должен оставаться пересечением Profile permission и Device firewall verdict, поэтому Device `ALLOW` не должен создавать destinations, direction или path eligibility, отсутствующие в Profile policy. [`closed`]
- **[VPNG0001-R1.R2.R4.R6.R2.R1]** *Чтобы пользователь мог описывать ограничения Device в привычной последовательной firewall-модели и понимать влияние порядка правил без скрытой оптимизации со стороны VPN-GATE.* | VPN-GATE должен сохранять заданный пользователем порядок `firewall = [...]`; Release-1 rule string имеет форму `<in|out> <allow|deny|reject> [tcp|udp|icmp] [from <IPv4-CIDR>[:port-bundle]] [to <IPv4-CIDR>[:port-bundle]]` с опциональным trailing comment, а первый применимый terminal verdict определяет результат Device firewall. `port-bundle` допустим только с TCP/UDP и состоит без пробелов из одного или нескольких comma-separated элементов `N` или `A-B`, где каждый порт в `1..65535`, `A <= B`, а один физический порт не может повторяться или входить в пересекающиеся элементы bundle; VPN-GATE должен сохранять declared item order и не должен переставлять правила или исправлять широкое раннее правило ради более позднего. [`closed`]
- **[VPNG0001-R1.R2.R4.R6.R2.R2]** *Чтобы пользовательские `IN/OUT` не требовали знания Linux FORWARD semantics и при этом однозначно соответствовали фактическому направлению пакета относительно VPN Device.* | VPN-GATE должен трактовать в Device firewall `OUT` как payload packet, входящий через ordinary/host boundary и уходящий через current concrete path этого Device, а `IN` — как packet, входящий через current concrete path Device и уходящий через ordinary/host boundary; source/destination addresses и ports должны означать буквальные L3/L4 поля payload packet в точке этой фильтрации, а не адреса внешнего VPN transport или значения после последующего VPN-GATE source NAT. [`closed`]
- **[VPNG0001-R1.R2.R4.R6.R2.R3]** *Чтобы отсутствие Device firewall configuration сохраняло прежний смысл «Device не вводит дополнительного ограничения», а явное ограничение не получало скрытого разрешающего fallthrough.* | Если пользователь не задаёт Device firewall rules, VPN-GATE должен нормализовать Device firewall к эквивалентной permissive policy, разрешающей любой поддерживаемый payload в обоих направлениях `IN` и `OUT`; если пользователь задал хотя бы одно явное правило, VPN-GATE должен сохранить только явную ordered policy, а отсутствие совпавшего terminal verdict должно завершаться `DROP`. [`closed`]
- **[VPNG0001-R1.R2.R4.R6.R2.R4]** *Чтобы Device firewall оставался защитой управляемого VPN-трафика, а не превращал VPN-GATE в универсальный host firewall.* | VPN-GATE должен применять пользовательскую Device firewall policy только к payload traffic, который проходит между explicit ordinary/host boundary и current concrete VPN paths этого Device внутри managed network domain; эта policy не должна захватывать произвольный host-local или host-to-host traffic вне VPN-GATE managed payload path. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Purpose

Prove the Linux/nftables lower primitives required by the already accepted NG3 ordered
Device-firewall composition without selecting external configuration grammar or final
protocol-specific REJECT semantics.

The experiment covers:

- exact jump from `payload_forward` into one owned Device child chain;
- preservation of child-chain rule order in nft JSON;
- `return` meaning "continue in payload_forward to the Profile hard gate";
- terminal child-chain `drop` meaning explicit-policy no-match fail-closed;
- an owned `reject` rule JSON/action primitive as evidence only.

## Requirements

- `VPNG0001-R1.R4.R2`;

- `VPNG0001-R4.R4.R6.R2`;
- `VPNG0001-R4.R4.R6.R2.R1`;
- `VPNG0001-R4.R4.R6.R2.R2`;
- `VPNG0001-R4.R4.R6.R2.R3`;
- `VPNG0001-R4.R4.R6.R2.R4`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`.

## Candidate lower shape

The test uses one disposable Device child chain:

```text
payload_forward
    exact managed host/path pair -> jump device_fw_exp041
    exact Profile NEW permission -> accept
    policy drop

device_fw_exp041
    comment "vpn-gate:ng3:device-fw-child-v1"
    ordered explicit rules
    ...
    terminal drop for explicit-policy no-match
```

An ALLOW-like Device rule is represented by `return`, never by `accept`.

The experiment does **not** define stable production child-chain naming. It also does not
define the final mapping from normalized `REJECT` to protocol-specific nft reject forms.

## Procedure

A disposable three-namespace forwarding topology is created.

1. Create the marked NG3 nft table and `payload_forward policy drop`.
2. Create one ordinary Device child chain with owner comments on all test rules.
3. Add an exact host/path jump before the Profile hard-gate allow.
4. Verify a matching child `drop` blocks traffic that the Profile rule would otherwise
   accept.
5. Replace that matching action with `return`; verify the same traffic reaches the later
   Profile allow and succeeds.
6. Verify an unmatched packet hits the explicit-policy terminal `drop`.
7. Add a non-conflicting test-only `reject` rule and capture its nft JSON.
8. Read the full ruleset JSON and assert jump target, action primitives, comments and exact
   rule ordering.

## Decision

PASS opens a later strict owner-observation/desired-state unit for Device child chains.

PASS does not authorize physical production mutation, choose external Device-firewall
syntax, or close the separate protocol-appropriate REJECT realization gate.
