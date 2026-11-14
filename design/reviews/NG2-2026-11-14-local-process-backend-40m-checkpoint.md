# NG2 — LOCAL_PROCESS backend / probe executor 40-minute checkpoint

Date: 2026-11-14
Branch: code-cycle-20261114-local-process-backend-40m
Cycle interval: 40 minutes

## Cycle clock

CYCLE_START_COMMIT = b072e73df00cc5dd53b3e964eec6220026a7337a
T0 = 2026-11-14T10:07:02Z

This file is the recovery anchor. Final closure commit/time is recorded when the cycle threshold is reached.

## Completed

- Linux LOCAL_PROCESS materialization inside the existing common NetworkRulesAdapter.
- Exact ICMP /32 probe plane only; broader LOCAL_PROCESS forms fail closed.
- Explicit LinuxLocalProcessConfig(uid, ct_mark); Linux identity stays outside semantic NetworkRulesSpec.
- Exact RPDB observation using uid_start/uid_end/ipproto/oif and bound-output ifindex verification.
- Selective nft OUTPUT/INPUT with conntrack-carried reverse identity.
- LOCAL_PROCESS-only policy keeps IPv4 forwarding closed.
- Critical LP7 fix: pre-projection owner intent retains the dedicated uid guard across another owner's structural reconcile after generation loss.
- Independent ProbeRulesStateCalculator: KNOWN/MATCHED/READY only makes probe evidence authoritative; divergence is INVALID.
- Mandatory PayloadRulesState vs ProbeRulesState comparison completed; common RulesState rejected.
- Only generic network_rules_semantically_equal() was extracted as common machinery.
- Single-shot LinuxIcmpProbeExecutor implemented and used by privileged production LOCAL_PROCESS integration.
- AvailabilityProbeManager executable boundary and normative design document added without inventing scheduler/hysteresis.

## Already closed target mechanism gate

EXP-024 already passed on the real Debian GNU/Linux 13 (trixie) target, kernel 6.12.116+deb13-amd64. All P1..P5 and NG2_SELECTIVE_PROBE_PROCESS_ISOLATION=PASS were observed. That proves the selected OUTPUT-process-identity / conntrack-mark reverse-path mechanism on the target. Do not confuse this closed gate with the still-open production /usr/bin/ping executor confirmation or the newly discovered stale-conntrack generation-lifetime question.

## Green evidence

Green implementation baseline 70ebd870b22b41782c0c6bef55ce18adfc0f25ef:
- NG2 compile/unit PASS.
- full privileged NG2 Linux integration PASS.
- LOCAL_PROCESS LP1..LP7 PASS.
- existing payload dataplane PASS.
- NG1 validation PASS.

Latest green code/test baseline after closure audit is 9a95384b7b43121b2914e1df7b903c6da5e20518.
It includes executor prerequisite fail-close and the internal RPDB non-root uid invariant; NG2 and NG1 are PASS.

## Branch-scope integrity

Comparison from pre-cycle baseline ec1ee1e056cd9cb112d94d7279c3072bf5d03ba5 shows 38 changed files and no NG1/RC implementation file. Changes are confined to NG2 plus the NG2 workflow/reviews. NG1/RC evidence was not used as a source tree for modification.

## Closure integrity

From green executable baseline 9a95384b7b43121b2914e1df7b903c6da5e20518 through documentation head 713520609ae4e4788231e15332cdff3520aa8191, the branch contains only documentation changes; no Python/workflow code changed after the green run. Therefore the current executable baseline is exactly the tested 9a95384b state.

## Reviews

- NG2-2026-11-14-linux-local-process-backend-review.md
- NG2-2026-11-14-probe-rules-state-review.md
- NG2-2026-11-14-rules-state-comparison-review.md
- NG2-2026-11-14-availability-probe-manager-boundary-review.md
- NG2-2026-11-14-linux-icmp-probe-executor-review.md
- NG2-2026-11-14-local-process-probe-executor-whole-slice-audit.md

## Unresolved kernel ambiguity A17

Conntrack-carried process identity has a lifetime independent of RPDB/nft generation.
A marked ICMP conntrack entry may outlive one single-shot ping and an interface/rules generation transition.
Interface identity is not part of the ordinary conntrack tuple.

A focused disposable kernel experiment must determine:
1. whether the marked ICMP conntrack entry survives the relevant generation transition;
2. whether a later ping can deliberately reuse the same tuple/ICMP identifier;
3. whether a delayed or synthetic reply can then satisfy the new INPUT rule through the stale mark;
4. if yes, what narrow generation mechanism is viable without flushing unrelated conntrack state.

Do not guess a fix and do not add broad/global conntrack flushing before evidence.

## External target gate

Debian 13 target confirmation of the intended production ping executable is still pending.

Run on testing from this branch:

sudo env VPNG_NG2_PROBE_PING_PATH=/usr/bin/ping \
  python3 design/NG2/code/python/rou/tests/integration_linux_local_process.py

Required: LP1..LP7 and NG2_LINUX_LOCAL_PROCESS_INTEGRATION=PASS.
Retain complete output on failure.

## AvailabilityProbeManager policy still intentionally open

- attempt interval;
- timeout policy supplied to the executor;
- retry count;
- success/failure thresholds;
- hysteresis;
- jitter;
- parallelism/cancellation;
- exact Manager observation-generation token;
- shutdown cleanup policy for process prerequisites.

Do not invent scheduler/hysteresis defaults.

## Resume protocol

Do not reopen these decisions without contradictory evidence:
- NG1/RC* are evidence/reference, not source code for NG2 modifications;
- one common physical NetworkRulesAdapter remains;
- no second LOCAL_PROCESS reconciler;
- uid/ct-mark remain Linux lower-domain configuration;
- root uid is forbidden;
- current physical LOCAL_PROCESS support is ICMP exact-/32 echo only;
- pre-projection owner intent retains the uid guard during unrealizable projection;
- ProbeRulesState stays independent from PayloadRulesState;
- common RulesState is rejected;
- probe evidence requires fresh KNOWN + MATCHED + READY rules;
- the single-shot executor does not own scheduling/hysteresis.

On resume:
1. incorporate Debian 13 production-ping target result if available;
2. resolve stale conntrack-mark generation lifetime with a focused disposable kernel experiment;
3. only after both mechanism gates close, move to AvailabilityProbeManager sampling/timing policy;
4. bring timing/retry/hysteresis product choices for human agreement rather than guessing.