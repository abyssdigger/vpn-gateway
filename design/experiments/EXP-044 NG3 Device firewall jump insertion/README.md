# EXP-044 — Device firewall jump insertion before Profile gate

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG-U001-R1.R2.R4.R6.R2]** *Чтобы transport-level ограничения могли дополнительно защищать tunnel traffic, не превращаясь в обход Profile policy.* | VPN-GATE должен для каждого Device поддерживать дополнительную ordered firewall policy для payload traffic, проходящего через его concrete paths; effective permission должен оставаться пересечением Profile permission и Device firewall verdict, поэтому Device `ALLOW` не должен создавать destinations, direction или path eligibility, отсутствующие в Profile policy. [`closed`]
- **[VPNG-U001-R1.R2.R4.R6.R2.R1]** *Чтобы пользователь мог описывать ограничения Device в привычной последовательной firewall-модели и понимать влияние порядка правил без скрытой оптимизации со стороны VPN-GATE.* | VPN-GATE должен сохранять заданный пользователем порядок `firewall = [...]`; Release-1 rule string имеет форму `<in|out> <allow|deny|reject> [tcp|udp|icmp] [from <IPv4-CIDR>[:port-bundle]] [to <IPv4-CIDR>[:port-bundle]]` с опциональным trailing comment, а первый применимый terminal verdict определяет результат Device firewall. `port-bundle` допустим только с TCP/UDP и состоит без пробелов из одного или нескольких comma-separated элементов `N` или `A-B`, где каждый порт в `1..65535`, `A <= B`, а один физический порт не может повторяться или входить в пересекающиеся элементы bundle; VPN-GATE должен сохранять declared item order и не должен переставлять правила или исправлять широкое раннее правило ради более позднего. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Purpose

Prove the smallest Linux/nftables mutation primitive needed to preserve the accepted
Device-firewall ordering:

```text
Device firewall jump
    BEFORE
Profile NEW/RETURN accept rules
```

Appending a Device jump after an existing Profile accept is not equivalent and may bypass
the Device restriction.

## Requirements

- `VPNG-U001-R1.R4.R2`;

- `VPNG-U001-R4.R4.R6.R2`;
- `VPNG-U001-R4.R4.R6.R2.R1`;
- `VPNG-U004-R4.R1`;
- `VPNG-U004-R4.R2`;
- `VPNG-U004-R4.R3.R2`.

## Procedure

A disposable ordinary -> managed -> VPN forwarding topology uses the accepted
`payload_forward policy drop` base chain.

1. Install a Profile NEW allow rule.
2. Create an owned Device child chain whose matching rule drops the same packet.
3. Append the Device jump with `add rule`; verify nft order is Profile then Device and the
   packet passes.
4. Remove that test jump.
5. Insert the same Device jump with `insert rule`; verify nft order is Device then Profile
   and the packet is denied.
6. Record exact JSON ordering and handles.

## Decision

PASS establishes `insert rule` as a sufficient minimal primitive for adding a Device jump
ahead of existing Profile rules without rebuilding the whole `payload_forward` chain.

PASS does not yet authorize production mutation. The guarded Executor must still prove
ownership, stale-object deletion, barrier preservation and fresh postcondition.
