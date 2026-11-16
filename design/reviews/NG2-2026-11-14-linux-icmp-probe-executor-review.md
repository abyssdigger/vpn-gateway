# NG2 — Linux single-shot ICMP probe executor review

**Date:** 2026-11-14  
**Type:** autonomous implementation / mechanism review  
**Scope:** first executable probe worker below AvailabilityProbeManager

## Result

**PASS on privileged Linux CI; Debian 13 production-binary confirmation pending.**

## Boundary

`LinuxIcmpProbeExecutor` is Direct Machinery. It executes one attempt only.

It does not own:

- scheduling cadence;
- retry count;
- hysteresis;
- result publication;
- Profile/binding policy;
- NetworkRules apply/reconcile.

Those remain AvailabilityProbeManager/runtime concerns.

## Input

The executor receives:

- one normalized `AvailabilityProbeRequest`;
- explicit positive integer `timeout_seconds`;
- an already namespace-scoped Linux command runner;
- `LinuxIcmpProbeExecutorConfig`.

The config contains:

```text
local_process: LinuxLocalProcessConfig
gid
ping_path
```

The same `LinuxLocalProcessConfig` instance can therefore be supplied to both the
NetworkRulesAdapter and the executor. The uid is not duplicated as an independent executor
configuration value.

The conntrack mark remains invisible to the executor.

## Generation check

Before process execution the executor reads the current interface with `ip -j link` and
requires exact `InterfaceIdentity(ifname, ifindex)` equality.

A same-name/new-ifindex replacement therefore returns local execution ERROR and is not
reported as remote NO_REPLY.

## Process prerequisite

Before every attempt the executor idempotently writes and freshly verifies:

```text
net.ipv4.ping_group_range = gid gid
```

Readback is compared as two whitespace-separated values because sysctl may serialize the
pair with tabs.

The executor does not guess or restore a previous ping_group_range value. The range is a
runtime prerequisite for the dedicated probe process class and remains valid until later
runtime/shutdown ownership is defined.

## Capability boundary

Execution uses argv only, no shell:

```text
setpriv
    --reuid=<configured uid>
    --regid=<configured gid>
    --clear-groups
    --bounding-set=-all
    --no-new-privs
    <explicit ping executable>
    -n -c 1 -W <timeout>
    -I <exact ifname>
    <target>
```

The executable path is explicit technical configuration. The executor does not assume a
distribution-specific file-capability layout.

## Result semantics

```text
ping rc=0 -> REPLY
ping rc=1 -> NO_REPLY
other rc -> ERROR
local generation/prerequisite/exec failure -> ERROR
```

NO_REPLY is a raw single-attempt observation, not a final availability verdict.
AvailabilityProbeManager must apply future timing/hysteresis policy before publication.

## Evidence

The production LOCAL_PROCESS integration now routes LP4 through the production executor,
using the same lower-domain process identity as the Adapter.

CI still uses a capability-free copied ping executable because GitHub runner packaging may
attach file capabilities that conflict with an empty capability bounding set.

The integration accepts `VPNG_NG2_PROBE_PING_PATH` so the Debian 13 target can confirm the
actual intended executable without changing production code.

## Target confirmation

From repository root on the Debian 13 target:

```bash
sudo env VPNG_NG2_PROBE_PING_PATH=/usr/bin/ping \
  python3 design/NG2/code/python/rou/tests/integration_linux_local_process.py
```

PASS requires LP1..LP7 and:

```text
NG2_LINUX_LOCAL_PROCESS_INTEGRATION=PASS
```

A target failure must retain the full traceback/diagnostic.

## Next boundary

After target confirmation, the executor mechanism is sufficient for the first
AvailabilityProbeManager sampling path.

Cadence, retry and hysteresis remain deliberately unchosen and require their own product
contract.
