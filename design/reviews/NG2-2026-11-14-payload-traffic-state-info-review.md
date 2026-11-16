# NG2 — PayloadTrafficStateInfo contract review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** payload-domain InfoEvent projection published by PayloadTrafficManager

## Review criteria

Проверялись:

- достаточность event payload для RuntimeStateManager / ProfileStateCalculator;
- отсутствие raw network-stack state в верхнем event contract;
- различение fact vs verdict;
- stale/unknown observation handling;
- foreign/drift state handling;
- чистота component model и domain isolation;
- compatibility with future common rules-state type review.

## Findings

### T1 — materialized_paths overclaimed correctness

**Severity:** terminology/architecture  
**Disposition:** accepted and fixed.

При divergent rules routing domain с тем же logical name может существовать, но быть
неправильным по destinations/filter/NAT semantics.

Поле переименовано materialized_paths -> observed_paths.

Оно сообщает факт observed routing projection и само по себе не означает, что Profile
здоров или ruleset корректен.

### T2 — event must not expose raw NetworkRulesState

**Severity:** architecture  
**Disposition:** accepted and implemented.

Текущий contract:

    PayloadTrafficStateInfo
        rules_state: PayloadRulesState

        profiles[]
            profile_name
            observed_paths: tuple[InterfaceIdentity, ...] | UNKNOWN

Не публикуются:

- NetworkRulesState;
- routing-domain objects;
- dispatch/filter/NAT rules;
- Linux table/RPDB/nft details;
- Adapter diagnostics.

InterfaceIdentity допустим, потому что это нейтральный cross-domain identity уже
известного runtime interface, а не Linux materialization policy.

### T3 — unknown rules knowledge must invalidate current Profile paths

**Severity:** correctness  
**Disposition:** accepted and enforced.

Если PayloadRulesState.knowledge == UNKNOWN, event не имеет права утверждать текущие
observed paths. Все requested Profiles публикуются с observed_paths = UNKNOWN.

Cached/stale paths не выдаются как current facts.

### T4 — rules-state knowledge and observation authority must agree

**Severity:** correctness  
**Disposition:** accepted and fixed.

Projector теперь отвергает обе противоречивые формы:

- PayloadRulesState.knowledge = KNOWN при stale/unknown NetworkRulesState;
- PayloadRulesState.knowledge = UNKNOWN при fresh authoritative NetworkRulesState.

Это делает PayloadRulesStateCalculator единственным источником truth для knowledge
assessment и не позволяет event builder молча создавать невозможные combinations.

### T5 — PayloadRulesState itself required axis invariants

**Severity:** architecture/correctness  
**Disposition:** accepted and fixed.

До review dataclass позволял внутренне противоречивые combinations, например UNKNOWN
knowledge с DIVERGED convergence или MATCHED convergence с UNSAFE safety.

Добавлены минимальные invariants:

- knowledge=UNKNOWN -> dependent axes are UNKNOWN;
- knowledge=KNOWN -> convergence is defined;
- MATCHED -> SAFE;
- UNSAFE -> DIVERGED.

Более жесткие invariants не вводятся без доказанной необходимости.

### T6 — missing requested domain and foreign observed domain have different meanings

**Severity:** correctness  
**Disposition:** accepted and implemented.

При authoritative observation:

- requested logical domain отсутствует -> requested Profile получает observed_paths=();
- foreign observed logical domain не публикуется как новый Profile.

Foreign state остается видим через aggregate convergence/safety assessment.

Это не позволяет lower-domain drift создавать новые upper-domain subjects.

### T7 — per-Profile path facts are not Profile verdicts

**Severity:** architecture  
**Disposition:** accepted.

PayloadTrafficStateInfo намеренно не публикует отдельный READY/FAILED для каждого Profile.

Окончательный ProfileStateInfo принадлежит RuntimeStateManager и вычисляется из:

- Profile requirements;
- binding/availability facts;
- aggregate PayloadRulesState;
- observed_paths;
- publication state и других system-level facts.

Тем самым PayloadTrafficManager не забирает ownership системной Profile policy.

### T8 — intermediate red CI is preserved evidence

**Severity:** test process  
**Disposition:** accepted and fixed.

Commit f442742 добавил test на contradictory UNKNOWN rules state before projector
implementation was tightened и поэтому дал ожидаемый red NG2 CI.

Subsequent implementation fixed the contract; current NG2 CI is green.

## Component/domain review

project_payload_traffic_state() — small pure domain projection helper, not a new
architectural component.

Он:

- не выполняет I/O;
- не хранит state;
- не публикует Event самостоятельно;
- не создает нового synchronous dependency edge;
- не дублирует PayloadRulesState assessment logic.

Actual InfoEvent publication остается responsibility PayloadTrafficManager.

## Evidence

NG2 Python CI passed on commit e6aad31f570e65d3ccbb1132b31325f37c8c17dd.

Tests cover:

- known observed paths;
- requested Profile ordering;
- authoritative missing domain -> empty paths;
- unknown/stale rules -> unknown paths;
- foreign observed domain exclusion;
- contradictory knowledge/observation rejection;
- event invariant rejecting current path claims under unknown rules knowledge;
- PayloadRulesState axis invariants.

No kernel experiment is required; this unit is a pure semantic/event projection.

## Final verdict

**PASS.**

No unresolved finding blocks this review unit.

Next coherent work may move either to RuntimeStateManager Profile-state mapping or to the
lower NetworkRulesAdapter implementation. The event boundary itself is now sufficiently
specified for both directions.
