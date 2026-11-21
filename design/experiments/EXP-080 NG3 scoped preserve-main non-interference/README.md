# EXP-080 — scoped preserve-main non-interference

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R2.R2]** *Чтобы разрешенная родителем host-side автоматизация для типовой эксплуатации первого release оставалась явно управляемой и не превращалась в постоянный захват ordinary-host routing.* | Первый release должен предоставлять peaceful host-routing automation, которая через продуктовую конфигурацию по умолчанию отключена и при включении применяет route assistance только к явно выбранной администратором области ordinary-host traffic. Область должна позволять отдельно выбирать host-originated traffic, весь non-local ingress traffic или точные host ingress interfaces; traffic вне выбранной области не должен захватываться helper'ом. Peaceful helper не должен сам включать или выключать host IP forwarding. При включенной области helper устанавливает идентифицируемые host-routing contributions при start, обновляет их при поддерживаемой lifecycle reload-операции и при stop удаляет только сохранившиеся принадлежащие helper'у contributions, не удаляя заменившее их администраторское состояние. Между lifecycle-операциями helper не обязан непрерывно наблюдать или восстанавливать последующие изменения, не должен принудительно возвращать замененное администратором состояние, а такая внешняя поломка или замена сама по себе не должна переводить core managed forwarding VPN-GATE в fail-closed. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Статус

COMPLETE — PASS — SELECTED as privileged non-interference evidence for `VPNG0001-R5.R1.R1`.

## Finding

Global `lookup main suppress_prefixlength 0` before selector-scoped helper dispatch can
change routing for traffic outside helper scope by preempting a later administrator RPDB
rule with an explicit non-default route from `main`.

## Candidate fix

Use the same selector on preserve-main and helper dispatch:

```text
<selector> lookup main suppress_prefixlength 0
<selector> lookup <peaceful-helper-table>
```

## PASS criterion

1. old global preserve reproduces interference for unselected LAN-B;
2. selector-scoped preserve leaves LAN-B administrator RPDB decision intact;
3. selected LAN-A still prefers explicit non-default `main` route over helper;
4. ordinary `main` routes remain unchanged.

## Result

See `EXP-080-result-20261120.md`.

Workflow run `44772483578`, job `linux-host-managed-routing` (`136413467975`) completed
with `EXP080_RESULT=PASS`.

## Disposition

Selected lower evidence. It rejects global preserve-main for narrow peaceful scopes and
selects selector-paired preserve+dispatch lowering.
