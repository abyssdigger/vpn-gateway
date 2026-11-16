# NG2 review — payload/probing decoupling cleanup

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-payload-probing-decoupling-40m`  
**Scope:** payload-domain cleanup, quantitative assessment, available automated testing,
then payload-management documentation revision

## Verdict

**PASS.**

The remaining coupling from superseded "probing as part of payload intent" designs was
removed without adding a replacement event/evidence layer.

## Cleanup results

### Structural payload contract

Removed from `PayloadProfileRequest`:

```text
no_problem_prefix_length
```

`PayloadTrafficStateRequest` is now structural/admin payload intent only.

Availability-derived route priority is injected internally after
`PayloadRulesCalculator` has produced the structural `NetworkRulesSpec`.

### Probe-independent payload availability boundary

Payload now consumes:

```text
AvailabilityPriorityConfig
AvailabilityPriorityChannel
AvailabilityGoodNews
AvailabilityTick
```

A payload priority channel contains only:

```text
channel_id
path
enabled
failure_ticks
recovery_good_news
```

It does not contain target, mechanism, cadence, generation, attempt id or timestamp.

`PayloadTrafficManager` has zero imports from `probe_rules` or `probe_transport`.

### Cadence / hysteresis separation

Probe execution owns:

```text
interval_seconds
```

Payload availability owns:

```text
failure_ticks
recovery_good_news
```

A hysteresis-only change resets payload hysteresis progress but preserves probe tick
cadence.

### Inactive availability

When a Profile has no enabled assigned availability channel:

- effective order is configured order;
- no auxiliary routing prefix is active;
- lower `preferred_prefix_length` is `None`.

Availability disabled/absent is therefore a true payload priority no-op.

### Lower routing terminology

The generic lower routing field is now:

```text
preferred_prefix_length
```

The NetworkRules/Linux layers no longer expose availability-specific
`no_problem_prefix_length` / confirmed-live vocabulary.

## Quantitative result before testing

Measured against cycle base
`ccfb625cbe7d60274991c920bd960f91f4cbec5a` at tested code head
`c861c26295790ce923163b37cae0be7a0f0b4155`:

```text
production Python: +348 / -377 => net -29 lines
tests:             +252 / -261 => net  -9 lines
production files changed: 9
test/integration files changed: 13
new production modules: 0
removed production modules: 0
```

`PayloadTrafficManager` specifically:

```text
before: 625 lines
after:  565 lines
delta:  -60 lines

methods before/after: 21 / 21
probe-domain import lines: 2 -> 0
old physical-probe type references: 33 -> 0
```

`payload_rules.py`:

```text
422 -> 409 lines
```

The cleanup therefore reduced coupling and code volume rather than replacing old types
with an equally large adapter layer.

## Testing

Temporary draft PR #19 exposed PR-only CI.

Tested code head:

`c861c26295790ce923163b37cae0be7a0f0b4155`

Workflow:

`NG2 Python` run **617**

Results:

- compile: PASS;
- rootless unit suite: **279 tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025 stale probe conntrack generation: PASS;
- EXP-026 probe-class conntrack cleanup: PASS;
- EXP-027 route-priority transition: PASS;
- nft ICMP selector syntax: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter integration: PASS;
- Linux LOCAL_PROCESS integration: PASS;
- Linux dataplane integration: PASS.

These are existing automated gates; no new external/target experiment was required.

## Documentation revision after green tests

Only after the positive test result, active payload/runtime documentation was updated.

Revised:

- `design/NG2/payload-traffic-manager.md` — rewritten around the tested contracts;
- `design/NG2/runtime-event-model.md` — split physical probe demand, optional
  AvailabilityPriorityConfig and structural payload intent;
- `design/NG2/availability-routing-model.md` — preferred-prefix terminology;
- `design/NG2/network-rules-adapter.md` — source-neutral lower route priority;
- `design/NG2/availability-collector-materializer.md` — probe-independent priority
  channel and hysteresis-only policy;
- `design/NG2/availability-probe-manager.md` — cadence/hysteresis split;
- `design/NG2/probe-execution-agent.md` — AvailabilityGoodNews/AvailabilityTick output;
- `design/NG2/code/python/rou/README.md`;
- `CHANGELOG.md`.

A final terminology scan found zero occurrences in the active architecture set of:

- `no_problem_prefix_length`;
- `confirmed_live_prefix_length`;
- `AvailabilityChannelPolicy`;
- `ProfileProbeAssignment`;
- `ProbeGoodNewsInfo`;
- `ProbeTickInfo`;
- `availability_probe_states`.

## Remaining work

The payload/probing boundary has no open cleanup gate.

Next work is runtime assembly:

1. project `AvailabilityProbeSetRequest` for physical probing;
2. independently project `AvailabilityPriorityConfig` for payload priority;
3. publish structural `PayloadTrafficStateRequest`;
4. wire ProbeExecutionAgent good-news/tick directly to PayloadTrafficManager;
5. project probe diagnostics into status;
6. add ordinary audit/retry scheduling.

No availability evidence bus or payload/probe coupling should be reintroduced.
