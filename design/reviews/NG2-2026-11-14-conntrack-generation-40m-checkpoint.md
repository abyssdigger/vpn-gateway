# NG2 conntrack-generation 40-minute cycle checkpoint (draft)

Date: 2026-11-14
Branch: code-cycle-20261114-conntrack-generation-40m
Cycle interval: 40 minutes

CYCLE_START_COMMIT = f13c13eef95f8438fc36989c68a883abc43d44c0
T0 = 2026-11-14T11:06:19Z

## Closed gates

- LinuxIcmpProbeExecutor with intended /usr/bin/ping passed on Debian 13 target: LP1..LP7 and NG2_LINUX_LOCAL_PROCESS_INTEGRATION=PASS.
- EXP-025 stale conntrack ambiguity is closed as a target-confirmed finding.

EXP-025 Debian 13 result:
- generation A ifindex=8, generation B ifindex=10;
- generation-A marked ICMP entry survived replacement;
- deliberate reuse of id=4242 produced NEW delta=0, ESTABLISHED delta=1;
- EXP_025_RESULT=STALE-INHERITANCE.

This proves ct mark is probe-class flow identity but is not itself an interface/rules generation token.

## EXP-026

Purpose: test narrow remediation by deleting only ICMP conntrack entries carrying the dedicated probe mark.

Privileged CI PASS:
- K1: two mark-0x26 probe entries plus different-mark control exist;
- K2: conntrack delete by probe mark removes exactly probe-class entries and preserves control;
- K3: after vpn0 replacement the cleaned fixed identifier uses NEW+mark-set;
- K4: different-mark control state remains usable;
- EXP_026_PROBE_CLASS_CLEANUP=PASS.

Debian 13 target confirmation is pending at this draft checkpoint.

Latest executable experiment baseline: da5474f74fd993161f2212572bc80db111d926eb. NG2 workflow PASS on that commit, including EXP-025, EXP-026 and the existing Linux integration suite.

## Remediation direction if target PASS

Preferred first mechanism: class-wide cleanup of ephemeral LOCAL_PROCESS probe conntrack state by dedicated ct mark.

Reasons:
- avoids generation-mark allocator / wrap / restart state;
- avoids conntrack zones;
- avoids leaking ping ICMP identifiers into NetworkRules lower domain;
- aligns with current owner-wide ProbeRulesState: structural generation change already invalidates current probe evidence as a whole;
- payload/unrelated conntrack state is not touched when the mark is exclusively owned by the probe class.

Cleanup must be part of structural convergence, not AvailabilityProbeManager or probe Driver.

Current recommended ordering under serialized control path:
1. existing protective transition;
2. materialize new routing/RPDB/nft policy;
3. delete stale ICMP conntrack entries carrying dedicated probe mark;
4. fresh exact verification;
5. publish/commit READY only after successful cleanup + verification.

Cleanup trigger if adopted: LOCAL_PROCESS intent exists before OR after the structural transaction. Do not add a probe-subtree diff detector. This covers first install, repair/replacement, last-owner removal and shared rebuild while probe ownership remains live.

Production cleanup must treat '0 flow entries have been deleted' as idempotent no-op success.

## Component terminology fixed

Driver: direct external action/observation without owning convergence.
Executor: owns reaching/verifying desired postcondition; may use Drivers or perform driver-level actions directly if a separate Driver adds no value.
Manager: owns desired lifecycle/policy.

Consequences after experiments close:
- current LinuxIcmpProbeExecutor is architecturally a Driver and should be reviewed for rename to LinuxIcmpProbeDriver;
- current LinuxNetworkDriver is Executor-like because it owns structural materialize+verify convergence; review its name separately.

Do not mix those renames into EXP-025/026 mechanism evidence.

## Branch-scope audit

Comparison from cycle baseline 900a8391172f93356f400e8a273a0e2b766e0587 shows no NG1/RC implementation-file changes. This cycle is confined to NG2, EXP-025/026, NG2 reviews and the NG2 workflow.

## Closure checks

- Both EXP-025 and EXP-026 harnesses clean their disposable namespaces in finally blocks.
- No TODO/FIXME/XXX markers were found in either harness.
- No global conntrack flush (`conntrack -F`) exists in either experiment.
- From executable baseline da5474f74fd993161f2212572bc80db111d926eb through the current pre-threshold head, all changes are documentation-only.

## Executable closure integrity

The latest executable artifact remains da5474f74fd993161f2212572bc80db111d926eb. Every subsequent change through the current pre-threshold head is documentation/review/checkpoint only; no Python or workflow file changed after the green EXP-026 run.

## Still open

- Debian 13 EXP-026 target result;
- explicit architecture acceptance of class-wide probe conntrack invalidation;
- production integration of cleanup into structural transition;
- naming refactor Driver/Executor;
- AvailabilityProbeManager timing/retry/hysteresis remains intentionally unchosen.