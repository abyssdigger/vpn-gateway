# EXP-079 — managed-boundary absolute helper bypass

## Статус

PREPARED — privileged Linux evidence для no-recapture части `VPNG0001-R2.R2`.

## Вопрос

Можно ли гарантированно исключить packets с managed HOST↔STACK ingress из peaceful-helper
dispatch range, не заставляя их обязательно завершать lookup именно в `main`?

## Candidate lowering

```text
iif <managed-boundary> goto <helper-exit>
lookup main suppress_prefixlength 0
<helper dispatch rules>
<helper-exit>: nop
ordinary administrator/kernel RPDB continues
```

## PASS criterion

PASS требует:

1. STACK-origin packet перепрыгивает helper dispatch и использует обычный host default;
2. после удаления ordinary default тот же STACK-origin lookup не падает обратно в helper
   table, а завершается отсутствием маршрута;
3. non-STACK traffic по-прежнему может попасть в helper dispatch;
4. JSON observation однозначно представляет `goto` и `nop` для будущего strict owner.

## Выполнение

```sh
sudo python3 "design/experiments/EXP-079 NG3 managed boundary helper bypass/exp079_managed_boundary_helper_bypass.py"
```
