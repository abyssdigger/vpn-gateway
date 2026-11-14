# NG2 probe conntrack remediation — 40-minute cycle checkpoint (draft)

Date: 2026-11-14
Branch: code-cycle-20261114-probe-conntrack-remediation-40m
Cycle interval: 40 minutes

CYCLE_START_COMMIT = 7d895303c55e14cf464c324f3c9eeace1216ca68
T0 = 2026-11-14T12:45:25Z

## External blocker

EXP-026 Debian 13 target confirmation is still pending.

Required target command from repository root:

    clear

    sudo python3 \
      design/NG2/code/python/rou/tests/integration_probe_conntrack_cleanup.py

Required: PASS K1..K4 and EXP_026_PROBE_CLASS_CLEANUP=PASS.

No production conntrack cleanup has been implemented before this target gate.

## Independent work completed

### Component model

The general normative design/component-model.md now defines:

- Executor as Machinery responsible for reaching/verifying a supplied desired state or postcondition;
- Runner as a low-level execution/transport primitive inside Machinery rather than a peer semantic role;
- the Runner / Driver semantic boundary;
- Driver commonly uses Runner; Executor may use Driver and/or Runner directly; Manager normally remains above raw Runner mechanics.

The model explicitly does not require one-command Driver wrappers between Executor and Runner.

### Current NG2 role corrections

Behavior-preserving role renames completed:

- LinuxIcmpProbeExecutor -> LinuxIcmpProbeDriver;
- linux_probe_executor.py -> linux_probe_driver.py;
- LinuxNetworkDriver -> LinuxNetworkExecutor.

No Driver wrapper was introduced merely for naming symmetry.

### Role audit

Current classification:

- Runner: LinuxCommandRunner, SubprocessLinuxRunner, NetworkNamespaceLinuxRunner;
- Driver: LinuxIcmpProbeDriver;
- Executor: LinuxNetworkExecutor plus procedural instance convergence in create_linux_instance(), ensure_linux_instance(), destroy_linux_instance();
- Manager: PayloadTrafficManager and future AvailabilityProbeManager;
- separate roles: NetworkRulesAdapter/LinuxNetworkRulesAdapter, Calculators, bootstrap/assembly, value/state types.

LinuxNetworkRulesAdapter remains an Adapter, not a Manager or physical Executor.

### Adapter / Executor boundary

Reviewed PASS without an additional split.

LinuxNetworkExecutor.observe_interfaces() is a Driver-style observation method, but extracting a one-method LinuxInterfaceDriver would add no reusable semantic boundary. Component role is determined by responsibility as a whole, not by forcing every public method into the same operation shape.

### Normative synchronization

- runtime-bootstrap.md now treats close_forwarding_verified() as an Executor convergence operation;
- network-rules-adapter.md uses Structural Executor terminology;
- runtime-event-model.md keeps Executor/Driver/Runner APIs outside the upper event contract;
- network-rules-adapter.md records EXP-025 target-confirmed STALE-INHERITANCE and EXP-026 privileged-CI PASS with target confirmation pending.

Historical review/checkpoint documents retain historical names where they describe earlier code state.

## Executable validation

Latest complete executable role-rename baseline:

    f37ac016ca83e96e219b2bbfdf2deef4e1dd56bb

GitHub Actions:

- NG2 Python: PASS, including privileged Linux integration;
- NG1 Python validation: PASS.

Subsequent cycle commits are documentation/model/review only.

Current active design/NG2 source and normative documents contain no stale LinuxIcmpProbeExecutor, linux_probe_executor, or LinuxNetworkDriver references.

## Scope audit

Comparison from baseline 2b64efeb921e2eda1d8b44d9030f96ca7439ba46 through the pre-checkpoint head is confined to design/component-model.md, NG2 code/tests, NG2 normative docs and NG2 reviews. No NG1/RC implementation file is modified.

## Deliberately not changed

- LinuxDriverResult and LinuxDriverError remain vocabulary debt only;
- no per-command Route/Nft/Sysctl Driver classes;
- no LinuxInterfaceDriver;
- no production conntrack cleanup before EXP-026 target PASS;
- no AvailabilityProbeManager interval/retry/hysteresis policy.

## Next after target EXP-026

If Debian 13 returns EXP_026_PROBE_CLASS_CLEANUP=PASS:

1. explicitly accept/reject probe-class-wide ephemeral conntrack invalidation;
2. if accepted, integrate mark-filtered ICMP cleanup into LinuxNetworkExecutor after new nft policy and before exact closed-state verification;
3. classify zero-match selective delete as idempotent success;
4. add production regression proving stale inheritance cannot cross the Adapter structural transition;
5. only then return to AvailabilityProbeManager timing/retry/hysteresis policy.