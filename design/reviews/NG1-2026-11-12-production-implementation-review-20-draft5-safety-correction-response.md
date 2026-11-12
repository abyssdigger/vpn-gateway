# Disposition — Production implementation review 20

All ordinary implementation findings F1–F15 were already corrected in the reviewed
correction cycle.

F16 was accepted and implemented:

- DeviceEngine emits stable `device-*` DEBUG events for observed interfaces, selector
  candidate order, quota projection, bound and over-quota result;
- TrafficEngine emits `traffic-*` events for committed metric history, per-range
  reservations/members and final assignment/waiting state;
- PlannerEngine emits `planner-*` events for initial observation, pure projection,
  steady/reopen/lifecycle/structural decisions, transition reasons, mutation command count,
  verification failures and commit outcome.

Logs contain identifiers, interface identities, counts, metrics and verifier reasons, not
raw TOML, credentials, private keys, publication payload or full subprocess argv.

A follow-up review of the logging function itself found one issue: the first Planner DEBUG
record evaluated `active_device_names` before normalized configuration validation and
outside the fail-closed exception boundary. That was fixed by moving the record after
`validate_active_config`.

External experiment gates remain unchanged:

- EXP-014: future capacity>1 remote-init flow pinning;
- EXP-015: real TCP MTU/MSS production policy;
- EXP-016: concrete ECMP hash policy before positive UNAVAILABLE trigger;
- EXP-017: strict ifindex-generation firewall backend;
- EXP-018: real Debian 13 systemd deployment lifecycle.

No review finding was waived.
