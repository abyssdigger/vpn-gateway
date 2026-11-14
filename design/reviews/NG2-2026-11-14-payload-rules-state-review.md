# NG2 — PayloadRulesStateCalculator initial review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** initial multidimensional payload-rules state calculator

## Review criteria

Проверялись:

- соответствие согласованной многомерной state model;
- различение authoritative observation и stale/unknown data;
- независимость convergence / safety / service;
- conservative proof discipline;
- чистота component model;
- изоляция payload domain от network-stack implementation;
- отсутствие повторной интерпретации исходного payload config;
- Python -> Rust alignment.

## Findings

### S1 — stale KNOWN observation must not become authoritative payload knowledge

**Severity:** correctness  
**Disposition:** accepted and implemented.

`NetworkRulesState(knowledge=KNOWN, fresh=False)` содержит последнюю известную semantic
projection, но не доказывает current external state.

`PayloadRulesStateCalculator` поэтому возвращает:

```text
knowledge   = UNKNOWN
convergence = UNKNOWN
safety      = UNKNOWN
service     = UNKNOWN
```

а не сравнивает stale rules с desired.

### S2 — exact convergence must not collapse the service axis

**Severity:** architecture  
**Disposition:** accepted and covered.

Exact desired/observed equality означает:

```text
convergence = MATCHED
safety      = SAFE
```

но не автоматически `service = READY`.

Tests cover:

- exact active rules -> `MATCHED + SAFE + READY`;
- exact zero-path/default-deny rules -> `MATCHED + SAFE + ISOLATED`;
- exact mixed active/zero-path rules -> `MATCHED + SAFE + DEGRADED`.

Это подтверждает, что convergence и service действительно независимы.

### S3 — proven isolation is safe even when divergent

**Severity:** correctness  
**Disposition:** accepted and implemented.

При default-deny filtering отсутствие `traffic_allows` является достаточным
network-rules proof того, что payload bytes не разрешены данным owner ruleset.

Поэтому authoritative divergent observation без traffic allows классифицируется:

```text
KNOWN + DIVERGED + SAFE + ISOLATED
```

Routing/NAT objects сами по себе permission не создают.

### S4 — non-isolated divergence must not be guessed

**Severity:** safety/architecture  
**Disposition:** accepted; intentionally conservative.

Syntactic inequality двух `NetworkRulesSpec` недостаточна, чтобы доказать:

- permission widening -> `UNSAFE`;
- conservative restriction -> `SAFE`;
- partial usable service -> `DEGRADED`.

Initial calculator therefore returns:

```text
KNOWN + DIVERGED + UNKNOWN + UNKNOWN
```

for authoritative non-isolated divergence.

Это не deferred product defect, а explicit boundary следующего review unit:
нужен conservative semantic relation algorithm с доказуемыми cases.

### S5 — calculator must not re-read payload request/config

**Severity:** architecture  
**Disposition:** accepted and implemented.

Public contract:

```text
calculate(
    desired: NetworkRulesSpec,
    observed: NetworkRulesState,
) -> PayloadRulesState
```

`PayloadTrafficStateRequest` не передается.

Таким образом:

- `PayloadRulesCalculator` единожды переводит payload intent в network-rules domain;
- `PayloadRulesStateCalculator` интерпретирует только desired/observed network-rules
  relation обратно в payload-rules state;
- Profile direction, Device envelope, NAT config и Linux implementation knowledge не
  дублируются в state calculator.

## Component-model review

`PayloadRulesStateCalculator` является Direct Calculator:

- explicit immutable-like inputs;
- deterministic result;
- no I/O;
- no Events;
- no hidden history;
- no Adapter calls.

Он не является Manager и не владеет observed state.

`PayloadRulesState` остается payload-domain type. Общий `RulesState` пока не вводится.

После появления реального `ProbeRulesStateCalculator / ProbeRulesState` обязателен
отдельный review их фактического совпадения. Если semantics окажется принципиально
одинаковой, общий type следует вынести тогда, а не заранее.

## Evidence

NG2 Python CI on Python 3.13 completed successfully for commit
`e8684855624e350b41f3432a029fef980ff15390`.

Tests cover:

- unknown observation;
- stale known observation;
- exact active state;
- exact isolated state;
- exact partially serviced state;
- divergent proven isolation;
- divergent non-isolated conservative UNKNOWN.

No kernel experiment is required: this unit is pure semantic evaluation.

## Final verdict

**PASS.**

No unresolved finding blocks this review unit.

Next review unit: conservative `NetworkRulesSpec` relation proofs sufficient to classify
some divergent states as `SAFE/DEGRADED` or `UNSAFE` without relying on Linux
implementation details.
