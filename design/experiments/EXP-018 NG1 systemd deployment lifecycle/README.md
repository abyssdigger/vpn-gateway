# EXP-018 — NG1 systemd deployment and crash-recovery lifecycle

**Status:** PREPARED — live Debian 13 deployment gate  
**Architecture baseline:** NG1 Draft 5 after 2026-11-12 safety correction  
**Type:** real systemd/PID1/capability/sandbox lifecycle test

## Purpose

GitHub CI proves shell syntax, `systemd-analyze verify`, rootless behavior and privileged
network-namespace kernel behavior, but its hosted runner is not a trustworthy substitute
for the target Debian 13 PID1/systemd environment.

EXP-018 proves the installed `rouvpn@.service` lifecycle under its actual hardening,
capability bounding set and restart policy.

## Required host

Disposable Debian 13 VM with systemd as PID1, root access and no pre-existing
`vpn-gate-exp018` namespace or `rouexp0` interface.

No real VPN process is required. The test uses one enabled OUTBOUND Profile with no bound
Device interface, so the runtime must remain safe through table-local blackhole policy.

## Required checks

1. install the reference package/unit;
2. create schema-v1 router/instance configs;
3. `rou check exp018`;
4. `rou up exp018`:
   - service enabled + active;
   - namespace/veth exists;
   - local INPUT/FORWARD/OUTPUT default DROP;
   - Planner policy verifies through `rou show`;
5. normal `systemctl restart rouvpn@exp018.service` recovers;
6. kill the MainPID with SIGKILL and prove Restart=on-failure recovers to verified policy;
7. inspect journal for sandbox/capability denial;
8. `rou down exp018`:
   - unit disabled/inactive;
   - namespace/veth removed;
9. optionally reboot after `rou up` and prove enabled service recreates the appliance and
   returns to verified state before payload exposure.

## PASS criteria

- no manual namespace preparation is required after install/config;
- every service start enters through fail-closed `rou prepare`;
- post-crash restart returns to `policy_verified=true`;
- service hardening does not block required netns/ip/sysctl/iptables operations;
- teardown leaves no owned namespace/veth;
- unexpected failure does not leave forwarding usable without the supervised runtime.

## Artifact

Run `exp-018-systemd-smoke.sh` from this directory as root on the disposable target. It
writes a timestamped artifact directory with commands, status JSON and journal excerpts.
