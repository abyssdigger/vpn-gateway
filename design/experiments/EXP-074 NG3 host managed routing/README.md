# EXP-074 — current host managed-destination routing

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG-U001-R2.R3.R1]** *Чтобы ordinary host routing не могла незаметно обойти явно выбранную администратором authoritative host-routing guarantee.* | Для destination, принятого aggressive host-routing helper под управление, конкурирующая ordinary host routing policy не должна переопределять выбранную helper'ом доставку этого destination к VPN-GATE; host-local delivery и трафик, уже вышедший из managed network domain в сторону host, не должны из-за этого захватываться обратно, а несвязанное ordinary host routing state не должно становиться объектом произвольной мутации helper'а. [`closed`]
- **[VPNG-U002-R2.R6]** *Чтобы ответ на входящий трафик из VPN-канала мог быть корректно обработан его отправителем.* | Для управляемого трафика, принятого со стороны VPN через разрешенный канал, VPN-GATE должен обеспечивать передачу относящегося к нему ответного трафика обратно через тот VPN-канал, через который был принят исходный трафик; наличие других разрешенных каналов для адреса отправителя не должно само по себе менять канал такого ответа. [`closed`]
- **[VPNG-U001-R2.R3.C1]** *Поскольку непрерывная защита ordinary-host routing от внешнего вмешательства и безопасная аварийная композиция с административным containment существенно расширяют host-integration и recovery scope, тогда как первый рабочий релиз может использовать peaceful lifecycle helper или полностью административную host routing.* | Первый release не обязан предоставлять aggressive host-routing helper и связанные с ним continuous-recovery / unrecoverable-alarm guarantees; отсутствие этой capability не должно запрещать peaceful host-routing helper или полностью ручное управление host routing администратором. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Current requirement trace

This experiment is exact Linux acceptance evidence for:

- `VPNG-U001-R5.R2.R1` — authoritative managed-destination routing for the opt-in aggressive
  host-routing helper.

Older direction-derived host-routing decompositions are historical and no longer define current
product semantics. `VPNG-U003-R4` remains a core STACK return-affinity requirement, but
EXP-074 is no longer used to make host routing an unconditional part of that core contract.

The aggressive helper itself is constrained out of Release 1 by `VPNG-U001-R5.R2.C1`.

## Question

Does the tested authoritative host-routing realization implement one managed-destination
table such that:

- matching managed destinations are sent through `vpng0`;
- `0.0.0.0/0` captures non-local ordinary/forwarded traffic even when host `main`
  contains a more-specific route;
- packets already arriving from `vpng0` bypass managed capture and use ordinary
  `main`;
- kernel local delivery remains local;
- cleanup leaves unrelated host `main` routes unchanged?

EXP-072 remains valid lower evidence for device-only managed-L3 routing and for the older
specificity-preserving bootstrap mechanism. EXP-074 is the acceptance gate only for the
aggressive authoritative-routing child, not for the simple lifecycle helper.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-074 NG3 host managed routing/exp074_host_managed_routing.py"
```
