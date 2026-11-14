# NG2 — whole semantic-slice code audit

**Дата:** 2026-11-14  
**Тип:** autonomous whole-slice implementation review  
**Scope:** current NG2 Python semantic baseline above the concrete NetworkRulesAdapter backend

## Review criteria

Проверялись:

- неиспользуемые artifacts, state fields and helper APIs;
- необоснованная сложность;
- противоречия component model;
- subject-domain isolation;
- расхождения с EXP-012 / EXP-017 and current NG2 architecture;
- premature abstractions before a real consumer exists;
- Python -> Rust alignment without preserving Python-only convenience as architecture.

## Findings

### W1 — original PayloadTrafficStateRequest was retained without a consumer

**Severity:** cleanup/architecture  
**Disposition:** accepted and fixed.

PayloadTrafficManager stored both the original request and the derived NetworkRulesSpec,
while all implemented control-loop behavior uses only the derived desired rules.

The duplicate representation created no current value and introduced a future risk of two
forms of the same current intent drifting apart.

Fix:

- removed _latest_request;
- current managed intent is latest_desired NetworkRulesSpec;
- invalid request still fails before replacing current desired rules or mutating Adapter;
- architecture text was aligned.

The original RequestEvent remains an input contract, not persistent Manager state.

### W2 — packet predicate evaluator leaked into the production semantic contract

**Severity:** architecture/cleanup  
**Disposition:** accepted and fixed.

PacketView plus TrafficSelector.matches()/TrafficPredicate.matches() were used only by unit
tests to prove predicate construction semantics.

A real NetworkRulesAdapter will compile semantic predicates to its backend; it does not
need a userspace packet interpreter in the production contract.

Fix:

- removed PacketView and runtime matches() methods from network_rules.py;
- moved the small evaluator to tests/predicate_eval.py;
- production TrafficPredicate is again declarative semantic AST only.

The AST itself remains justified: first-match Device envelopes, default allow/drop and
more-specific Profile exclusions require boolean composition without leaking nft syntax.

### W3 — DesiredRulesByOwner was premature unused production code

**Severity:** dead/preparatory artifact  
**Disposition:** accepted and fixed.

network_rules_owner.py and its tests were not consumed by any production component because
the concrete NetworkRulesAdapter does not yet exist.

Although the previous focused review correctly proved the intended owner-identity
semantics, keeping one speculative internal storage implementation violated the current
minimal-coherent-change rule.

Fix:

- removed network_rules_owner.py;
- removed test_network_rules_owner.py.

The normative Adapter API remains:

    apply(owner, spec)
    renew_state(owner)
    get_last_state(owner)
    cleanup(owner)

and owner is still opaque caller-instance identity. The concrete Adapter review unit will
choose its internal registry/composition structure when there is a real consumer and real
backend constraints.

The earlier owner-registry review remains historical evidence about the removed candidate
implementation; it is not a requirement to recreate that exact data structure.

### W4 — stale documentation lagged behind implementation

**Severity:** documentation  
**Disposition:** accepted and fixed.

Corrected:

- PayloadTrafficManager docstring no longer says audit is unimplemented;
- payload traffic projector no longer says materialized_paths after the field became
  observed_paths;
- README status now describes an executable payload semantic control-loop baseline rather
  than only the initial filtering slice;
- decomposition document no longer lists latest_request as current Manager state.

### W5 — predicate AST is nontrivial but justified, not accidental complexity

**Severity:** complexity review  
**Disposition:** retained with justification.

TrafficPredicate supports ALWAYS / NEVER / MATCH / ALL / ANY / NOT.

This is required by already accepted payload semantics:

- ordered first-match envelope rules;
- default allow with explicit drop exceptions;
- default drop with explicit allow exceptions;
- exclusion of more-specific Profile destinations from broader Profile permissions.

Replacing it with backend-specific nft expressions would violate the Adapter boundary;
expanding every complement into flat CIDR/port rule sets would create greater complexity.

No generic boolean-implication engine is added. PayloadRulesStateCalculator proves only a
small conservative subset of relations and leaves the rest UNKNOWN.

### W6 — PayloadRulesState relation logic remains payload-local intentionally

**Severity:** abstraction review  
**Disposition:** retained.

The current relation helpers are private to PayloadRulesStateCalculator.

They are not promoted to a generic RulesState/RulesRelation abstraction before the future
ProbeRulesState model exists.

This follows the explicit agreement: after real ProbeRulesCalculator /
ProbeRulesStateCalculator semantics exist, perform a separate common-type review.

### W7 — ActionResult and diagnostic fields are contract surface, not dead state

**Severity:** dead-code review  
**Disposition:** retained.

ActionResult.diagnostic and NetworkRulesState.diagnostic are not yet consumed by the small
PayloadTrafficManager implementation, but they are explicit Adapter contract outputs for
operational diagnosis and future logging/status.

They do not encode hidden policy or lower-domain control.

The boolean implementation representation of SUCCESS/FAILURE is not treated as a separate
architectural concept; no extra enum is introduced merely for spelling.

### W8 — TerminalDisposition.REJECT is currently unused by payload but belongs to the
generic network-rules domain

**Severity:** dead-code review  
**Disposition:** retained.

Payload currently emits DROP only.

REJECT is a semantic network disposition, not a Linux route type, and is expected to be
usable by other network-rules callers such as the probe plane. It does not force any
particular Linux unreachable/prohibit implementation.

### W9 — no current experiment contradiction found

**Severity:** evidence review  
**Disposition:** PASS.

Current semantic code preserves relevant evidence boundaries:

- EXP-017: concrete dynamic path identity remains (ifname, ifindex);
- same-name/new-ifindex remains distinct;
- EXP-012: Adapter SUCCESS still requires fresh verified materialization by contract;
- Manager does not implement Linux mutation order/barrier logic above Adapter;
- zero-path remains semantic fail-close intent;
- no userspace sequential-fallback semantics were reintroduced;
- no conntrack/nft/RPDB implementation mechanics leaked into payload domain.

Concrete Linux claims are intentionally deferred until the actual Adapter/backend exists,
where kernel integration evidence becomes mandatory.

## Current component-model check

Visible graph:

    PayloadTrafficManager
        -> PayloadRulesCalculator
        -> PayloadRulesStateCalculator
        -> NetworkRulesAdapter
        -> Event Delivery Environment publisher port

is acyclic.

PayloadTrafficManager is the Engine/Manager.

PayloadRulesCalculator and PayloadRulesStateCalculator are Direct Calculators.

NetworkRulesAdapter is the Direct semantic boundary.

No current production module above the Adapter owns:

- Linux table IDs;
- RPDB priorities;
- route metrics;
- nft chain/hook syntax;
- conntrack states;
- mutation/barrier phases;
- owner-composition backend mechanics.

## Evidence

NG2 Python CI is green after:

- removing the speculative owner registry and its tests;
- moving packet-predicate evaluation to a test-only helper;
- removing unused Manager request state.

Intermediate red runs are visible where a source/test half of a sequential cleanup commit
temporarily existed; the completed cleanup baseline is green.

No new kernel experiment was required for this audit because no concrete kernel backend was
added.

## Final verdict

**PASS after cleanup.**

No unresolved finding of minor severity or higher remains in the current NG2 semantic
slice.

The next implementation boundary is the concrete NetworkRulesAdapter lower domain.
That review unit must choose owner storage/composition together with actual materialization
requirements rather than restoring speculative helpers by default.
