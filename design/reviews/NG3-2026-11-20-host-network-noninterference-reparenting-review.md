# VPN-GATE NG3 — host-network non-interference / helper reparenting review

> **Reload correction note (2026-11-20):** the review below originally over-interpreted
> peaceful-helper reload handling as making reload mandatory in alpha. The current tree
> instead treats reload as a standard-but-optional lifecycle operation: semantics are defined
> by `VPNG-U005-R5.R6.R4` when supported, while
> `VPNG-U005-R5.R6.R4.C1` explicitly permits alpha releases to omit reload and require
> restart for configuration changes. Historical wording below is retained as review history.

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-rudiment-cleanup-finish-35m`  
**Reviewed range:** `cfe3c91dbea3930aa26fb377b3a119643a51aee0..6bf78352cfa1a5dec73a17b8eb12e0a47c286edd`

## Verdict

**PASS for requirement placement, lifecycle scope and traceability.**

The previous temporary placement of host-routing helpers under `VPNG-U001-R1` failed the
immediate-parent Purpose test: managed routing itself does not explain why VPN-GATE should or
should not own ordinary-host routing.

The corrected tree places the responsibility boundary directly under the primary
`VPNG-U001` promise.

## Corrected requirement shape

```text
VPNG-U001
├─ R1  managed routing between ordinary network and VPN paths
│
└─ R2  bounded influence on ordinary-host networking
   ├─ R2.R1     core works with administrator-provided host integration
   │  └─ R2.R1.R1  stable manual host-integration contract/instructions
   ├─ R2.R2     Release-1 peaceful host-routing automation
   └─ R2.R3     explicit aggressive host-routing automation
      ├─ R2.R3.R1  authoritative managed-destination routing <- EXP-074
      ├─ R2.R3.R2  continuous ownership/recovery
      ├─ R2.R3.R3  unrecoverable-alarm containment
      └─ R2.R3.C1  not required in Release 1
```

The independently useful administrative payload-containment requirement remains under the
safety tree at `VPNG-U004-R4.R7`.

## Parent/Purpose review

### VPNG-U001-R2

The Purpose directly refines the primary promise to operate on **selected** IP traffic:
using VPN-GATE for that selected traffic must not silently change unrelated ordinary-host
network behavior.

The Statement therefore bounds host-network mutation to explicitly enabled host-side
capabilities and forbids core managed forwarding from implicitly taking ownership of
ordinary-host routing.

### VPNG-U001-R2.R1

This child makes the non-interference boundary operational:

- core managed forwarding cannot require a host-routing helper;
- administrator-provided equivalent host routing is a supported deployment;
- core VPN-GATE does not mutate ordinary-host routing merely to make its own forwarding work.

`VPNG-U001-R2.R1.R1` separately prevents "the administrator can do it" from becoming hidden
tribal knowledge: the project must publish the stable route/reachability contract.

### VPNG-U001-R2.R2

Release 1 must provide peaceful host-routing automation, but its **use** remains optional and
explicitly configuration-controlled.

The accepted lifecycle semantics are:

- enabled: apply contributions on start;
- enabled: update contributions on reload;
- enabled: remove only still-owned surviving contributions on stop;
- disabled: do not mutate ordinary-host routing;
- no continuous fight with administrator changes between lifecycle operations;
- no core ForwardingGate closure merely because peaceful-helper routing is later changed.

The exact config spelling and Linux lowering remain `[pending_closure]`.

### VPNG-U001-R2.R3

Aggressive host routing is a separate explicit delegation of stronger ownership, not an
implementation mode secretly inherited by core or peaceful operation.

`EXP-074` remains exact closure evidence for `VPNG-U001-R2.R3.R1` only.

Continuous recovery and unrecoverable-alarm containment remain pending and the whole
aggressive capability is excluded from Release 1 by `VPNG-U001-R2.R3.C1`.

## Reload consequence

The accepted peaceful-helper lifecycle requires a real Release-1 reload operation.

`VPNG-U005-R5.R6.R4` now requires:

- explicit reload;
- validation of the candidate configuration before mutation;
- safe application of changed active-function desired state;
- success only after required postconditions;
- no false publication of a failed candidate as active.

The current alpha still requires restart for configuration changes. This is now an explicit
implementation gap, not product semantics.

The older `declarations.md` text about reload was narrowed to its actual topic:
post-first-release **external Profile network-list sources**. Deferring that feature no longer
defers the general Release-1 configuration reload operation.

## Configuration-model consequence

The Device/Profile fields already defined in `config-model.md` remain canonical.

However the complete Release-1 top-level grammar is no longer considered closed because
`VPNG-U001-R2.R2` requires an explicit peaceful-helper enable/disable choice whose spelling
has not yet been selected.

No provisional field name was invented during this review.

## Current implementation consequence

The current Python alpha still wires the EXP-074-style authoritative host-routing owner into
controller startup/runtime reconciliation and may close the internal ForwardingGate when that
owner drifts.

That implementation now has only one honest role:

> executable prototype/evidence for the postponed aggressive helper.

It must not remain the default Release-1 core path.

A later implementation unit must therefore:

1. detach the authoritative owner from core/default controller composition;
2. retain it separately as aggressive-helper prototype/evidence rather than deleting the
   proven lower mechanism;
3. implement a peaceful lifecycle helper that satisfies `VPNG-U001-R2.R2`;
4. allow the helper to be disabled while core operates with administrator-provided host
   integration under `VPNG-U001-R2.R1`;
5. materialize the Release-1 reload operation required by `VPNG-U005-R5.R6.R4`;
6. prove equivalent core managed-forwarding behavior with helper-provided versus equivalent
   administrator-provided host routing.

This implementation work is required before a Release-1 snapshot can claim the new
host-integration requirements, but it is not needed to validate the requirement-tree
correction itself.

## Traceability review

Current normative artifacts contain no active references to the temporary
`VPNG-U001-R1.R4/R1.R5` subtree.

All new `[pending_closure]` nodes have architecture references:

- `VPNG-U001-R2.R1.R1`;
- `VPNG-U001-R2.R2`;
- `VPNG-U001-R2.R3`;
- `VPNG-U001-R2.R3.R2`;
- `VPNG-U001-R2.R3.R3`;
- `VPNG-U005-R5.R6.R4`.

Closed `VPNG-U001-R2`, `VPNG-U001-R2.R1`, `VPNG-U001-R2.R3.R1` and
`VPNG-U001-R2.R3.C1` have exact architecture references.

The previous 2026-11-20 host-routing-helper review is preserved as historical evidence of the
first split and now explicitly states that its temporary requirement IDs were superseded by
this reparenting.

## Next requirement

The next previously identified suspicious requirement remains:

`VPNG-U004-R4.R1.R1`

Its zero-path fail-closed safety need appears valid, but its current wording still leaks the
old host-wide "ambient/main routing" model and must be reviewed against the corrected managed
boundary.

## Requirement migration note

The following requirement IDs are historical references from this record's original baseline.
They were later removed without a direct normative successor, so their last normative
compact-form wording is preserved here:

- `VPNG-U005-R5.R6.R4` — *Чтобы поддерживаемая lifecycle integration могла использовать стандартную reload-операцию без подмены ее неявным полным restart экземпляра.* | Если поддерживаемый deployment/lifecycle interface объявляет reload доступной операцией, VPN-GATE должен сначала валидировать новую конфигурацию, затем безопасно применить требуемые изменения активных функций и считать reload успешным только после подтверждения соответствующих postconditions; неуспешный reload не должен молча объявлять новую конфигурацию действующей. [`pending_closure`]
- `VPNG-U005-R5.R6.R4.C1` — *Поскольку reload является стандартной, но не обязательной lifecycle-операцией service-manager API и не требуется для проверки базовой работоспособности ранней alpha, её реализация не должна задерживать alpha-срезы.* | Alpha releases не обязаны предоставлять reload; при отсутствии reload изменение конфигурации может требовать явного restart, а peaceful host-routing helper применяет обновленную конфигурацию при следующей поддерживаемой lifecycle-операции. Это ограничение не меняет semantics reload там, где операция объявлена поддерживаемой. [`closed`]

The original IDs in the historical body are intentionally preserved.
