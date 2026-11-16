# NG2 — AvailabilityProbeManager rules boundary review

**Дата:** 2026-11-14  
**Тип:** autonomous architecture / experiment-boundary review  
**Scope:** relation between future ProbeRules and the current NetworkRulesAdapter

## 1. Trigger

После закрытия PayloadRules state model был оставлен обязательный follow-up:

```text
ProbeRulesCalculator
ProbeRulesStateCalculator
ProbeRulesState
```

а после появления реальной probe state-модели — сравнение с `PayloadRulesState` на предмет
возможного общего rules-state type.

Перед реализацией ProbeRules выполнена проверка текущего `NetworkRulesSpec` против
EXP-021/022/023.

## 2. Proven probe-plane requirements

EXP-021/022/023 доказали, что active availability condition должна:

- исполняться как локальный process в ROU namespace;
- быть связана с конкретным interface generation;
- использовать isolated routing plane, независимый от payload/main routing;
- иметь selector, который не позволяет unbound probe уйти через alternate path;
- иметь narrow request/reply firewall admission;
- продолжать работать, когда Profile payload pair OFF;
- полностью пересобираться после observation discontinuity / generation change;
- не наследовать availability result across restart.

EXP-022 materialized working selector conceptually as:

```text
local probe identity
+ protocol
+ target
+ bound output interface
    -> dedicated probe table
```

with a fail-closed terminal path.

## 3. Current NetworkRulesSpec cannot represent this plane

Current semantic contract has endpoint kinds:

```text
LOCAL_NETWORK
INTERFACE
```

where `LOCAL_NETWORK` means traffic entering/leaving through the infrastructure-side
`host0` path.

Current Linux backend correspondingly supports:

- RPDB dispatch only from `LOCAL_NETWORK` / `iif host0`;
- nft only for `LOCAL_NETWORK <-> INTERFACE`;
- one FORWARD base chain;
- source NAT only from `LOCAL_NETWORK`.

A probe is not forwarded host0 payload traffic. It is local INPUT/OUTPUT traffic.

Therefore a direct implementation:

```text
ProbeRulesCalculator -> NetworkRulesSpec
```

is currently impossible without weakening the EXP-022 isolation contract.

## 4. A separate physical ProbeRulesAdapter is also wrong

The structural Linux NetworkRulesAdapter deliberately owns an exclusive nft policy
inventory in the dedicated ROU namespace. Foreign nft tables are drift and are removed
behind the forwarding barrier.

A second independent Linux adapter owning probe nft/RPDB state would therefore create two
physical reconcilers that classify each other's state as foreign/drift.

That violates the single physical-policy ownership boundary already reviewed and tested.

Consequently the future ProbeRules machinery should remain a **semantic owner** above the
same composed physical NetworkRulesAdapter, not become a competing Linux policy adapter.

## 5. Required generic semantic extension

To make the common physical Adapter capable of serving probe rules without leaking Linux
UIDs into the upper domain, the semantic contract needs a local-process traffic class.

Minimum direction:

```text
EndpointKind:
    LOCAL_NETWORK
    LOCAL_PROCESS
    INTERFACE
```

`LOCAL_PROCESS` means traffic generated/consumed by the managed local process class for
this deployment boundary. The semantic spec does not carry a numeric uid/gid.

Probe dispatch additionally needs selectors that current `DispatchRuleSpec` lacks:

- destination;
- protocol;
- bound output concrete interface;
- local-process source class.

This is necessary to preserve the proven non-escape property when multiple paths can reach
the same target.

Linux maps the local-process class to a technical process identity. The exact mechanism
(uid, cgroup, mark, or another kernel selector) is lower-domain machinery and must be
coordinated with probe execution without appearing in `AvailabilityProbeSetRequest`.

## 6. Firewall coexistence ambiguity

EXP-021/022 used default-DROP INPUT/OUTPUT in a disposable probe-focused namespace.

Production ROU will also host VPN transport processes. Blindly adding default-DROP INPUT
and OUTPUT to the current nft table before transport-local policy exists could break the
underlay/control plane.

A production probe policy therefore needs one of:

1. selective local-process isolation (for example by a proven socket/process identity),
   leaving unrelated local processes unaffected; or
2. a complete common local INPUT/OUTPUT policy model covering probe and VPN transport
   processes together.

The current experiments prove narrow probe admission, but not selective coexistence with an
unrelated local process in the same namespace.

This is a mechanism gap, not a product-policy question.

## 7. Selective local-process experiment result

EXP-024 tested the missing shared-namespace boundary.

Direct INPUT socket-owner matching was rejected experimentally: the intended reply arrived
on the exact interface/source/protocol path, but `meta skuid` did not identify the
receiving ping socket at INPUT.

A second mechanism passed:

1. OUTPUT observes the dedicated probe uid;
2. exact admitted probe request sets a conntrack mark;
3. INPUT requires the same conntrack mark plus exact interface/source/protocol;
4. all other probe-uid OUTPUT is dropped;
5. unrelated local uid traffic remains on ordinary policy.

The privileged CI run proved bound success, unbound alternate-path rejection, wrong-target
rejection and unaffected unrelated local traffic.

This supplies a concrete lower-domain implementation direction without putting uid or
conntrack mark into the semantic probe request.

The same EXP-024 harness subsequently passed on the Debian 13 target. The selected
OUTPUT process-identity + conntrack-carried reverse-flow mechanism is therefore
target-confirmed.

## 8. Rules-state follow-up completed

This original boundary review did **not** create `ProbeRulesState` at that stage.

At the time of this review a state calculator was intentionally deferred because no real
ProbeRules materialization existed. That evidence gate is now closed: the production
LOCAL_PROCESS backend has passed real apply, exact renew and dataplane integration.

That follow-up is now complete: ProbeRulesStateCalculator was implemented after real
physical apply/renew evidence, and the mandatory PayloadRulesState / ProbeRulesState
comparison rejected a common RulesState because the domain semantics differ.

## Final verdict

**PASS for the architecture boundary; EXP-024 target mechanism confirmation is complete.**

Do not introduce a second Linux policy reconciler.

The common NetworkRules semantic contract has since been extended with local-process
traffic and bound-output/protocol dispatch semantics. Linux uid and conntrack mark remain
technical lower-domain state.

The completed PayloadRulesState / ProbeRulesState comparison was based on the real
ProbeRules state calculator.
