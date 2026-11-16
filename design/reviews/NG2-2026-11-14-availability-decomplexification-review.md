# NG2 — availability de-complexification review

**Date:** 2026-11-14
**Scope:** availability semantics, probe rules boundary, payload path ordering, Linux route-priority materialization
**Branch:** code-cycle-20261114-availability-decomplexification-40m

## 1. Review question

Проверен текущий NG2 после отказа от модели «availability probe управляет binding membership / per-attempt verdict lifecycle».

Искались:

- неиспользуемые concepts/types/modules/tests;
- необоснованная state/scheduler сложность;
- противоречия Linux experiments;
- domain leakage между probe, binding, payload и NetworkRules;
- неоднозначности, способные вернуть старую архитектуру скрытым путем.

## 2. Findings and disposition

### F1 — per-attempt cadence/hysteresis был сложнее реальной задачи

**Finding:** прежний run_due(), retry_interval_seconds, timeout_seconds как verdict policy, failure_threshold/recovery_threshold и per-attempt REPLY/NO_REPLY/ERROR моделировали generic health-check framework, а не требуемое автоматическое предпочтение рабочего канала.

**Disposition:** accepted and fixed.

Production policy теперь:

    good news in window -> immediately confirmed live, reset missed_intervals
    no good news        -> increment missed_intervals
    threshold reached   -> no longer confirmed live

Отдельные retry cadence, recovery threshold и attempt correlation удалены.

### F2 — availability ошибочно управляла binding membership

**Finding:** старый feedback loop мог интерпретировать UNREACHABLE как снятие binding. Это позволяло probing ухудшить connectivity и убрать последний настроенный path.

**Disposition:** accepted and fixed.

Eligibility/binding теперь structural/admin domain. Availability влияет только на PayloadProfileRequest.ordered_paths. Если подтвержденно лучшей альтернативы нет, текущий порядок не меняется.

### F3 — ERROR был связан с немедленным verdict transition

**Finding:** единичная локальная ошибка probe machinery не доказывает ни remote outage, ни устойчивую невозможность наблюдать path.

**Disposition:** accepted and fixed.

ERROR для routing означает только отсутствие good news в данном observation window. Подтвержденный path теряет live status только через общий integral missed_intervals >= failure_intervals.

Диагностическое различие local error / remote no-good-news остается задачей publication, но не меняет routing policy.

### F4 — configured disable был смешан с timing policy

**Finding:** enabled внутри timing policy и последующий policy=None manual mode создавали два способа выразить «не запускать probe».

**Disposition:** accepted and fixed.

AvailabilityProbeRequest.enabled является отдельным logical flag. AvailabilityWindowPolicy(interval_seconds, failure_intervals) обязателен для каждого normalized probe. Policy-less mode удален.

Enable/disable сохраняет logical config. Physical plane существует только пока есть хотя
бы один enabled logical consumer: disable последнего consumer закрывает plane, а disable
одного shared consumer не вызывает лишней перестройки.

### F5 — route priority протекал в nft/NAT ordering

**Finding:** PayloadRulesCalculator обходил paths в ordered_paths order не только для routing, но и при построении filter/NAT tuples. Pure priority permutation поэтому могла выглядеть как policy change.

**Disposition:** accepted and fixed.

Routing domain сохраняет semantic ordered_paths, а path-dependent filter/NAT generation canonicalized по concrete interface identity. Regression test доказывает, что route reorder не меняет dispatch/filter/flow/NAT projection.

### F6 — pure reorder запускал полный structural fail-closed rebuild

**Finding:** существующий Linux materializer закрывал forwarding, flush/rebuilt tables и nft даже при изменении только path metrics.

**Disposition:** accepted and fixed after evidence.

EXP-027 PASS подтвердил для ordinary prefix и default:

    A10 B20 C30 D40
    B10 B20 C30 D40
    B10 C20 C30 D40
    B10 C20 A30 D40

ip route replace меняет fixed metric slot и сохраняет копию того же interface на другом metric. Terminal blackhole остается.

Linux backend теперь имеет verified route-priority fast path:

1. fresh verification current compiled state;
2. strict proof that only unicast path-slot assignment changes;
3. top-down ip route replace;
4. fresh verification desired state;
5. any failure -> existing structural fail-closed rebuild.

Adapter API не получил отдельной caller-selected transition команды.

### F7 — отдельный ProbeRulesState стал информационно пустым

**Finding:** ProbeRulesState.Usability полностью выводился из convergence, а Knowledge/Convergence дублировали payload.

**Disposition:** accepted and fixed.

Общий нижний state теперь NetworkRulesConvergenceState + StateKnowledge + RulesConvergence с общим assess_network_rules_convergence().

Отдельные ProbeRulesState, ProbeRulesStateCalculator и их tests удалены. Payload сохраняет только действительно предметные дополнительные axes Safety/Service.

### F8 — AvailabilityProbeManager сохранял synchronous ProbeDriver dependency

**Finding:** после перехода к good-news/window semantics методы attempt_once()/evaluate_once() и injected ProbeDriver были ложной production boundary.

**Disposition:** accepted and fixed.

Manager больше не зависит от synchronous Driver и сейчас владеет только logical desired probe set, ProbeRules ownership/reconcile, rules-readiness generation и invalidation/publication boundary.

### F9 — standalone Linux single-shot Driver

**Finding:** LinuxIcmpProbeDriver больше не используется production Manager.

**Disposition:** retained intentionally as diagnostic/evidence-only machinery, not as production availability architecture.

Его API дополнительно очищен: он принимает только InterfaceIdentity, IPv4 target и technical timeout и больше не зависит от AvailabilityProbeRequest, probe_id, enabled или timing policy.

Он сохраняет уже проверенную механику exact interface generation, capability-free ping, ping_group_range и raw execution classification.

Re-entry condition для удаления/замены: production sender/receiver реализует те же необходимые Linux prerequisites и generation guarantees.

### F10 — Bubble model должен различать probe history и admin intent

**Finding:** если effective order сохраняет history, административное изменение configured priority не должно быть проигнорировано при отсутствии confirmed-live paths.

**Disposition:** accepted and fixed in normative model.

Startup, binding-set change и configured-priority change rebase effective order на новый configured eligible order. Только после этого применяется current positive evidence.

### F11 — BindingCalculator после удаления availability

**Finding:** проверено, не стал ли BindingCalculator пустым pass-through.

**Disposition:** rejected as deletion candidate.

Он сохраняет отдельную structural/admin responsibility: selected concrete interfaces + Profile applicability/eligibility -> binding matrix. Удалена только availability condition.

### F12 — production good-news execution пока не wired

**Finding:** clean AvailabilityWindowState и bubble ordering существуют как pure core, но production sender/receiver еще не доставляет generation-bound good-news events в Manager/runtime.

**Disposition:** accepted and deferred to the next review unit.

Следующий execution unit должен обеспечивать только generation-bound good-news notification, interval boundary notification, enabled lifecycle и local execution diagnostics. Semantic attempt id / reply-to-send correlation запрещены без нового конкретного требования.

### F13 — per-flow continuity при global route reorder

**Finding:** EXP-027 и текущий fast path доказывают FIB transition, но не обещают сохранение existing flows при failover/failback между paths.

**Disposition:** accepted as an explicit scope boundary, not a blocker for current routing priority semantics.

Current NG2 availability policy chooses path priority for routing lookups. Per-flow pinning must not be inferred from route ordering. Если product scope позже потребует сохранять уже здоровый established flow при priority changes, это требует отдельного conntrack/mark evidence gate.

## 3. Experiment consistency

No contradiction found with current evidence:

- EXP-024 remains evidence for selective LOCAL_PROCESS routing/filtering;
- EXP-025 remains evidence that same-name/new-ifindex can inherit stale probe conntrack;
- EXP-026 remains evidence for selective probe-class conntrack cleanup;
- EXP-027 newly proves fixed-metric route-slot bubble materialization.

Historical EXP-013 common-metric fallback remains valid Linux/FIB evidence but its shadow/UNAVAILABLE tier is not current NG2 architecture.

## 4. Unused-artifact audit

Removed from active implementation:

- availability_probe_policy.py;
- cadence/hysteresis scheduler tests;
- one-attempt verdict-policy tests;
- ProbeRulesState module/tests;
- Manager ProbeDriver dependency;
- Manager attempt_once()/evaluate_once();
- policy-less logical probe mode;
- stale ProbeRulesState type annotations.

Retained intentionally:

- probe_attempt.py result enum/data only for standalone diagnostic driver;
- linux_probe_driver.py as executable diagnostic/evidence machinery;
- historical review/checkpoint documents as evidence, not active normative architecture.

## 5. Final verdict

**PASS for the de-complexification scope.**

The current design is materially smaller and its remaining boundaries correspond to real responsibilities:

    ProbeRules safety/generation
            |
    good-news window evidence
            |
    stable bubble path ordering
            |
    Payload ordered_paths
            |
    verified route-slot fast path

No remaining active code requires per-attempt availability semantics, availability-driven binding removal, shadow fallback or a dedicated probe-rules state model.

The next coherent review unit is production good-news/window execution integration. It must build on this model rather than reintroduce attempt correlation.
