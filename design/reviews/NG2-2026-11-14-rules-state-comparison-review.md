# NG2 — PayloadRulesState vs ProbeRulesState comparison

**Date:** 2026-11-14  
**Type:** mandatory common-state abstraction review  
**Scope:** decide whether the two executable/observable rules-state models justify a common RulesState

## Result

**DO NOT introduce a common RulesState.**

Both models now have real callers' semantics and executable lower-domain evidence. Their
similar shape is not semantic equivalence.

## Shared facts

Both calculators:

- consume desired NetworkRulesSpec plus observed NetworkRulesState;
- require fresh KNOWN observation before claiming domain knowledge;
- distinguish MATCHED from DIVERGED;
- use the same generic semantic equality notion for exact convergence;
- are pure Direct Calculators.

Those commonalities justify, at most, sharing a generic NetworkRules semantic-equality
helper.

They do not justify a common state type.

## Payload semantics

PayloadRulesState has four independent axes:

```text
knowledge
convergence
safety
service
```

A divergent payload ruleset can still be useful and positively classified:

- proven restriction may be SAFE;
- no allowed payload bytes may be SAFE + ISOLATED;
- exact partial path availability may be DEGRADED;
- permission widening may be UNSAFE.

Payload service is about what forwarding capability remains.

## Probe semantics

ProbeRulesState has:

```text
knowledge
convergence
usability
```

For availability probing, a divergent local network plane is not a degraded measurement
plane whose result can still be interpreted normally.

- restrictive drift can create a false negative;
- widening/alternate-path escape can create a false positive.

Therefore authoritative divergence is `usability = INVALID` regardless of whether the
difference would be security-safe for payload forwarding.

Probe usability is about whether the measurement itself is trustworthy.

## Why a common RulesState would be harmful

A common `service` axis would force probe semantics into payload concepts such as
DEGRADED/ISOLATED.

A common `safety` axis would not answer whether a probe result is valid: a restrictive
probe plane can be permission-safe while still invalidating availability evidence.

Conversely, reducing PayloadRulesState to probe-style READY/INVALID would discard useful
payload distinctions already required by its Manager.

The two types therefore encode different domain questions.

## Allowed common extraction

The exact semantic-equality helper is duplicated in the two calculators and is genuinely a
NetworkRules-domain relation, not payload/probe policy.

It may be extracted into common NetworkRules machinery without merging the state types.

No broader relation lattice is justified yet.

## Decision

Keep:

```text
PayloadRulesState
ProbeRulesState
```

as separate domain types.

Do not add:

```text
RulesState
```

at this stage.

Revisit only if future concrete consumers cause the domain semantics themselves to
converge, not merely because field names overlap.
