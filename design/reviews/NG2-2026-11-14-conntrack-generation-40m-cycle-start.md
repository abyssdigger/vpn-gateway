# NG2 stale conntrack-generation experiment — 40-minute cycle start

Date: 2026-11-14

Baseline commit before this cycle:

900a8391172f93356f400e8a273a0e2b766e0587

Cycle interval: 40 minutes.

Primary goal:

- confirm LinuxIcmpProbeExecutor with the intended Debian 13 /usr/bin/ping executable;
- design and run a focused disposable kernel experiment for stale conntrack-mark lifetime across LOCAL_PROCESS rules/interface generation replacement;
- do not introduce broad conntrack flushing or scheduler policy without evidence.

Only the Debian 13 testing host is required initially. Real OpenConnect pri/sec/ocserv topology is not required for these two gates.