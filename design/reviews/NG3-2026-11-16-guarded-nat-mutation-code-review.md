# NG3 — экспертное ревью bounded guarded NAT-only Executor

**Дата:** 2026-11-16  
**CD branch:** `ng3-design-cycle-20261116-nat-observer-recovery-40m`  
**Review unit:** один физический NAT add/delete шаг в owned
`payload_postrouting` под подтверждённо закрытым `ForwardingGate`.
**Scope:** нижняя reference slice; **не** полный structural
`NetworkPolicyExecutor` и не открытие forwarding.

## Design gate / traceability

Нормативный gate:
`design/reviews/NG3-2026-11-16-guarded-nat-mutation-gates.md`.

**Implements:** `VPNG0001-R1.R2.R4.R6.R1`,
`VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3`,
`VPNG0004-R4.R3.R2`, `VPNG0004-R4.R4`, `VPNG0004-R4.R5`.

**Constrained by:** `VPNG0001-R1.R2.R4.R6.C1`.

Проверена цепочка Basis/Statement первичных корней,
Purpose/Statement производных, Reason/Statement ограничения
и явный актор VPN-GATE. Новых пользовательских semantics,
NAT TOML grammar или accepted Product Constraints не введено.

**Component model:** Direct Executor принимает переданный
`PayloadNatDesiredState`; уже существующий Direct Calculator
`compare_payload_nat` классифицирует состояние; нижний
`LinuxPayloadNatBackend` выполняет argv-based Driver operations
и link-sandwiched nft observation. Нет Engine, собственного
lifecycle, persistent cache, events или retry loop.

## Проверенные инварианты

1. `converge_forwarding_gate_once(DISABLED)` выполняется до nft
   observation и write. Gate перепроверяется перед физическим
   шагом и после него; Executor никогда не включает forwarding.
2. Перед mutation требуются exact owner marker, обе invariant
   цепочки, чистый NAT comparison. Любой неизвестный nft объект
   и правило другой цепочки приводят к CONFLICT и запрещают
   изменение в данном bounded reference slice.
3. Stale old ifindex не может подтверждать desired для нового
   одноимённого endpoint. Удаление — по фактическому handle,
   добавление — по точным текущим числовым ifindices.
4. За один вызов — не более **одной** физической операции.
   В случае partial progress следующий вызов получает новый
   наблюдённый snapshot, не хранит старые handles.
5. После команды сравнивается **весь** owned nft object set,
   допускающий ровно одно подтверждённое изменение. Успех
   syscall/CLI сам по себе не означает postcondition.
6. При ошибке после записи обязательно переопросить
   `ForwardingGate`; никакая ошибка nft observation не
   оправдывает допущение, будто барьер сохранился.

## Findings / disposition

**F-01 — ACCEPTED + FIXED.** При ошибке re-observation/classification
после write ранняя ветка выхода пропускала завершающий
`observe_forwarding_gate`. Не меняя fail-closed результата по nft,
это ухудшало authoritative recovery и могло скрыть loss барьера.
Исправлено в
`467e9a689e51478cc80936516c9a39a63f1efd47`.
Добавлены fault-injection tests: после nft observation failure
отдельно различаются `BARRIER_LOST` и
`POSTCONDITION_FAILED`. Повторный CI PASS.

**F-02 — ACCEPTED + FIXED (integration evidence).** Сначала
физические add/delete покрывались fake Driver тестами;
добавлен privileged одноразовый namespace integration
`integration_payload_nat_mutation.py`: закрытие gate,
реальное добавление NAT, same-name replacement,
stale handle cleanup, новое current правило,
отказ при неизвестном forward-rule. PASS.

**F-03 — ACCEPTED + DEFERRED BEHIND NAMED GATE.** Обнаруженный
в пределах полного Release 1 structural сценарий с уже
материализованными `payload_forward` и/или probe rules
не поддерживается этим bounded NAT-only slice.
Попытка mutation вместо недоказанного составного действия
возвращает CONFLICT до write. Это ограничение текущей reference
реализации, **не** новая пользовательская first-release
ограничительная семантика. Полная materialization остаётся
за отдельной unit с complete owned nft classification и
route/RPDB/filter/probe composition. Нельзя использовать
`CONFIRMED` этого slice как разрешение на end-to-end
forwarding activation.

Отклонённых findings: нет; открытых accepted defects в текущем
bounded scope: нет.

## Evidence

GitHub Actions `NG3 Python` на финальном исправленном коде,
commit `467e9a689e51478cc80936516c9a39a63f1efd47`,
[run 43861571788](https://github.com/abyssdigger/vpn-gateway/actions/runs/43861571788):
**8/8 jobs SUCCESS**.

- 302 rootless unit tests: PASS.
- EXP-033 exact-ifindex NAT: PASS.
- live authoritative NAT observer: PASS.
- EXP-034 exact stale-handle delete: PASS.
- live bounded guarded NAT-only mutation: PASS.
- forwarding gate, nft namespace/scaffold, route-priority и
  lower policy platform integration: PASS.

## Final expert verdict

**PASS — bounded guarded one-step NAT-only reference Executor
доказан в заявленной узкой области.**
Результат нельзя считать завершением полного structural
NetworkPolicyExecutor, полной NAT runtime integration
или утверждением конечной Release 1 готовности.
Следующая review unit: complete structural nft ownership
classification и композиция forward/probe/NAT с route/RPDB,
прежде чем разрешать forwarding activation.
