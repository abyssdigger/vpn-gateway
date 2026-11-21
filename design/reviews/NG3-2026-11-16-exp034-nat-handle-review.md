# NG3 — экспертное ревью EXP-034, точное удаление stale NAT по handle

**Дата:** 2026-11-16  
**CD-ветка:** `ng3-design-cycle-20261116-nat-observer-recovery-40m`  
**Scope:** только независимый Linux/nft kernel experiment. Продуктивная
NAT-mutation и изменение user-facing семантики вне scope.

## Normative review

**Implements:** `VPNG-U001-R1.R2.R4.R6.R1`,
`VPNG-U001-R1.R3.R2`, `VPNG-U001-R1.R3.R3`,
`VPNG-U004-R4.R3.R2`, `VPNG-U004-R4.R4`, `VPNG-U004-R4.R5`.

**Constrained by:** `VPNG-U001-R1.R2.R4.R6.C1`.

Требование подтвердить текущее и заменённое interface identity уже
принято в NG3. Новое неизвестное — факт nft exact-handle deletion,
а не продуктовый выбор. Границы будущих Driver и Executor отдельно
обозначены в `NG3-2026-11-16-exp034-nat-handle-gates.md`.

## Evidence

- `EXP-034-result-20261116.md` — hypothesis, commands, result,
  ограничение области применимости.
- Linux script `exp034_exact_nat_handle.py`: изолированный netns,
  подтверждённое `ip_forward=0`, old/new ifindex, обнаружение stale,
  добавление current rule, удаление только stale handle, failed-delete
  negative control, повторная точная классификация.
- GitHub Actions `NG3 Python` на commit `3b7b6087c6cb1a00ab064740661f1bc60e0e6b57`:
  [run 43859095573](https://github.com/abyssdigger/vpn-gateway/actions/runs/43859095573),
  **SUCCESS 8/8 jobs**, включая тест EXP-034.
- Фактическое наблюдение: old ifindex 5, new ifindex 7, old handle 3,
  new handle 4; удаление handle 3 оставило handle 4 без изменения.

## Findings / disposition

**Нет accepted defects в области experiment.**
Скрипт проверяет не только exit code, но и действительный повторный
nft snapshot + `compare_payload_nat`; это исключает ложный PASS от
успешного сообщения команды при неверном постусловии.

**Ограничение E-01 — ACCEPTED, DEFERRED BEHIND NAMED GATE.**
Эксперимент не моделирует конкурентных writers, полный
`payload_forward` ruleset, end-to-end structural policy rebuild,
re-enable forwarding или partial-failure recovery. Это не скрытый
допуск: `NetworkPolicyExecutor` физической NAT-mutation остаётся
за отдельным requirement/component gate, подтверждением ownership,
`ForwardingGate` и postcondition. Нельзя трактовать результат
EXP-034 как общий safe-to-mutate token.

**Отклонённых findings: нет.**
Дополнительных пользовательских решений не требуется.

## Simplification and verdict

Не добавлены Agent, Manager, persistent handle registry, очередь событий,
ретраи или runtime wire contract. EXP-034 минимален для одного
проверяемого Linux/kernel факта.

**FINAL VERDICT: PASS — технический факт exact-handle deletion
на CI-target доказан.** Промышленная NAT-mutation остаётся GATED.
