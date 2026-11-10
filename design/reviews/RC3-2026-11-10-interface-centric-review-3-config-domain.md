# RC3 — interface-centric architecture review 3

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** configuration / domain-model reviewer  
**Область:** closed schema, selector semantics, deterministic metric derivation  
**Вердикт:** CHANGES REQUIRED

## Общая оценка

После двух предыдущих passes конфигурационная модель существенно проще прежней и
внутренне согласована:

- transport peers отсутствуют;
- exact / prefix+ / ordered exact list имеют разные, явные semantics;
- explicit-list order является частью config contract;
- prefix order выводится только из current snapshot;
- local_address является единым applicability predicate;
- overlap guard namespaces является config error.

Найдены два узких, но важных deterministic-contract gaps.

## Finding 1 — prefix metric overflow cannot be a config-validator rule

§14 корректно может проверить maximum metric explicit list, поскольку list length известна
из config.

Но §18 говорит обобщенно: “Validator проверяет, что максимальная вычисляемая metric
помещается в unsigned 32-bit route priority.”

Для `prefix+` число active interfaces известно только из runtime inventory. Поэтому
`--check-config` не может доказать этот predicate.

Нужно разделить:

- exact / explicit list: overflow проверяется при config validation;
- prefix+: metric range проверяется при построении reconciliation snapshot/desired routes;
  overflow должен быть явной ошибкой reconciliation/domain projection, без integer wrap
  или silent truncation.

Практически такой count недостижим, но контракт реализации должен быть полным.

**Severity:** MEDIUM.

## Finding 2 — ASCII ordering needs an implementation-independent comparator

Architecture несколько раз говорит “ASCII-лексикографически”. Это правильное направление,
но для future Rust/Python equivalence желательно закрепить:

- exact interface names сравниваются case-sensitively;
- порядок по последовательности ASCII code values/bytes;
- locale/natural numeric sorting запрещены;
- `vpns10` может предшествовать `vpns9`, и это intentional.

Иначе implementation может соблазниться “natural sort” numeric suffix, что изменит
route priority.

**Severity:** MEDIUM.

## Проверенные положительные свойства

1. Explicit list duplicates correctly fatal.
2. Missing explicit-list element preserves later metric slot.
3. Prefix history/order of arrival is not policy input.
4. Managed selector overlap is checked by guard namespace, not only by current candidates.
5. Unknown legacy `peers` is rejected by closed schema.
6. Legacy `%` is invalid syntax, not a compatibility alias.
7. One profile intentionally requires one stable expected local IPv4 across all active
   interfaces; heterogeneous transports can be separate profiles.

## Required disposition

Развести config-time/runtime metric range validation и закрепить exact comparator.
После этого следующий review должен смотреть implementation mapping: может ли текущий
Python code выразить architecture без скрытого возврата к single-binding assumptions.
