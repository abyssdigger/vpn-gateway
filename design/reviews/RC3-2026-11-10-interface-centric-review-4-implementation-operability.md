# RC3 — interface-centric architecture review 4

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** daemon implementation / operations reviewer  
**Область:** deterministic materialization, committed state, RUN/DEGRADED behavior  
**Вердикт:** CHANGES REQUIRED

## Общая оценка

После networking, security и config passes interface-centric model уже пригодна для
реализации. Основные data-flow boundaries понятны:

```text
config + interface inventory
-> candidates
-> active bindings
-> desired policy/routes
-> apply/verify
-> ProfileResult + lifecycle state
```

Остались два implementability gaps.

## Finding 1 — ordering of exact policy/NAT blocks inside one profile is unspecified

EXP-001/firewall comparison relies on deterministic canonical desired chain content.

Architecture определяет:

- profile ordering;
- prefix route ordering;
- explicit-list route ordering;

но §9/§11 говорят лишь “для каждого active interface” и не закрепляют порядок exact
INPUT blocks, VPNG-INGRESS blocks, profile FORWARD blocks и MASQUERADE rules внутри
одного profile.

При двух `vpns00/vpns01` Python и Rust могут построить семантически эквивалентные, но
текстуально разные chains, что будет выглядеть как permanent drift.

**Required:** единый `active_order(profile, snapshot)`:

- exact: единственный active;
- prefix: case-sensitive bytewise ASCII;
- explicit list: config order, filtered to active;

и этот order используется routes, INPUT/FORWARD exact blocks, ingress blocks, NAT и
status.

**Severity:** HIGH для deterministic reconciliation.

## Finding 2 — verified binding state must not depend on ProfileResult SUCCESS

Architecture разрешает:

```text
no active path
+ fail-closed policy/routes verified
-> ProfileResult=FAIL
-> RUN/DEGRADED
```

При этом §8.8/§23.3 говорят, что candidate/active binding state фиксируется после
successful verification, но не говорят явно, что availability FAIL тоже является
успешно verified snapshot state.

Если implementation commit-ит binding state только для profile `SUCCESS`, профиль без
path будет на каждом periodic pass сравниваться со старым committed state и может
постоянно считаться transition.

Нужно разделить:

- **verification success** — desired fail-closed state достоверно проверен, snapshot
  binding state можно commit;
- **ProfileResult SUCCESS/FAIL** — functional availability result поверх verified state.

При verified zero-path FAIL candidates/active bindings должны быть committed.

**Severity:** HIGH.

## Finding 3 — startup wording should explicitly use the same separation

§8.2 уже разрешает successful startup into DEGRADED, но implementation contract следует
сказать явно: zero-path ProfileResult FAIL не является “route verification failure”.
Route verification может успешно подтвердить desired BLACKHOLE-only state, после чего
availability result = FAIL.

Это желательно закрепить рядом с startup sequence, чтобы реализация не делала
`if any(profile FAIL): startup error`.

**Severity:** MEDIUM; consequence of Finding 2.

## Проверенные положительные свойства

1. Generic RouteSpec may retain via/onlink for foreign routes while desired UNICAST fixes
   both to None/false.
2. Existing add/delete/replace route-plan abstraction can represent multiple same-prefix
   routes with distinct interface/metric identities.
3. Snapshot model naturally supports multiple active bindings.
4. Prefix metric renumbering is deterministic and inside policy-changing barrier.
5. Runtime IPv6 revalidation now precedes allowing policy.
6. Closed config schema has no compatibility ambiguity.

## Required disposition

Закрепить one active-order function for all binding-specific resources and explicitly
separate verified-state commit from functional ProfileResult. После этого архитектура
готова к финальному cross-domain audit.
