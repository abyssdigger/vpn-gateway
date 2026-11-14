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

## 7. Required next experiment

Before changing `NetworkRulesSpec` or the nft compiler, add a disposable-netns experiment
that proves a selective local-process firewall boundary in a shared namespace.

The experiment must establish:

- ordinary local process traffic remains unaffected;
- probe-identity traffic is fail-closed until its rule set is armed;
- only bound-interface + exact target + protocol probe traffic is admitted;
- reply admission is limited to the intended probe process/flow;
- alternate path cannot create a false positive;
- same-name/new-ifindex remains fail-closed;
- the mechanism works without adding capabilities to the probe process beyond the existing
  ping-socket model.

If Linux cannot reliably identify the receiving probe socket/process in INPUT without a
global default-DROP policy, the architecture must choose another isolation mechanism before
ProbeRules implementation.

## 8. Rules-state comparison remains intentionally pending

This review does **not** create `ProbeRulesState` yet.

A state calculator without an executable/observable ProbeRules materialization would only
copy PayloadRulesState shape by assumption, exactly the premature abstraction the earlier
review prohibited.

The common-state review remains mandatory after real ProbeRules observation exists.

## Final verdict

**BLOCKED BY ONE KERNEL/MECHANISM EXPERIMENT, not by user policy.**

Do not implement a fake ProbeRulesCalculator against the forwarding-only NetworkRulesSpec.
Do not introduce a second Linux policy reconciler.

Next unit: selective shared-namespace local-process probe isolation experiment.
