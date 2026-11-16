# NG2 LOCAL_PROCESS backend — 40-minute cycle start

Date: 2026-11-14

Baseline commit before this cycle:

```text
ec1ee1e056cd9cb112d94d7279c3072bf5d03ba5
```

Cycle interval: 40 minutes.

Current implementation boundary:

- EXP-024 is target-confirmed PASS on Debian 13;
- LOCAL_PROCESS semantic NetworkRules contract exists;
- Linux projection now tracks bound-output interface generation;
- Linux RPDB desired/observation/verification/materialization has been extended for
  LOCAL_PROCESS selectors using lower-domain UID + protocol + bound output interface;
- nft LOCAL_PROCESS OUTPUT/INPUT materialization with conntrack-carried flow identity is
  not yet implemented;
- ProbeRulesState remains intentionally deferred until real physical apply/renew evidence.

This file marks the GitHub-visible start of the new autonomous cycle.
