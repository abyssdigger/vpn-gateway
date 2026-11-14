# NG2 probe conntrack remediation — 40-minute cycle start

Date: 2026-11-14

Baseline commit before this cycle:

2b64efeb921e2eda1d8b44d9030f96ca7439ba46

Cycle interval: 40 minutes.

Primary goal:

- close Debian 13 target confirmation for EXP-026;
- if target PASS, integrate narrow probe-class conntrack cleanup into structural convergence;
- keep cleanup scoped to dedicated LOCAL_PROCESS probe ct mark and ICMP;
- preserve unrelated conntrack state;
- keep Driver/Executor naming refactor separate from mechanism integration unless mechanism work closes cleanly.