# EXP-080 — scoped preserve-main non-interference

## Статус

COMPLETE — PASS — SELECTED as privileged non-interference evidence for `VPNG0001-R2.R2`.

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
