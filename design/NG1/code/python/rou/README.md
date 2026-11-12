# VPN-GATE NG1 ROU production reference

Status: **active Python production implementation of NG1 Draft 5**

This package implements the ROU control plane after the ROU v0 / EXP-010..013 evidence.

## Implemented

- strict schema-v1 router and instance TOML parsing;
- immutable typed Device/Profile/NAT/publication/envelope domain model;
- disabled-placeholder and active cross-object validation;
- INBOUND/BIDIRECTIONAL production guard: active capacity exactly 1 plus restrictive
  Device envelopes with terminal `default=drop`;
- DeviceEngine binding by stable `(ifname,ifindex)` identity, survivor order and quota;
- durable candidate/metric history with atomic validated state persistence;
- deterministic Profile metric ranges and RPDB/table allocation;
- Profile dispatch longest-prefix ordering;
- normal, persistent shadow fallback and terminal blackhole route projection;
- complete live EnvironmentSnapshot collection with churn detection;
- default-DROP INPUT/FORWARD/OUTPUT filter projection;
- bound-interface-only state acceptance;
- cumulative Device traffic envelopes;
- config-derived Device NAT;
- TCP/UDP publication range projection and supervised relay workers;
- semantic kernel desired-state verification;
- structural fail-closed route/RPDB repair;
- incremental ordinary binding lifecycle route diff that preserves each Profile table's
  terminal blackhole continuously;
- namespace prerequisite apply/verify;
- Planner `observe -> plan -> apply -> fresh observe -> verify -> durable commit`;
- long-running event/audit reconcile loop;
- RTNETLINK `ip monitor` wakeup source;
- normalized namespace/veth instance lifecycle;
- crash-recoverable runtime composition and single-instance locking;
- `rou check|prepare|contain|up|down|show|run` CLI;
- reference installer and hardened `rouvpn@.service`.

## Deliberately deferred / experimentally gated

- positive production `UNAVAILABLE` trigger: routing mechanism exists now; DeviceManager
  health detection is intentionally deferred;
- multi-interface INBOUND/BIDIRECTIONAL flow pinning: EXP-014;
- real payload MTU/MSS policy: EXP-015;
- concrete `fib_multipath_hash_policy` production value before availability-triggered
  ECMP becomes effective: EXP-016;
- strict ifindex-generation firewall admission for rapidly reused dynamic interface names:
  EXP-017;
- DeviceManager VPN process lifecycle/configuration;
- live config reload/CandidateConfig protocol;
- explicit SNAT and IPv6 payload policy.

## Tests

Rootless:

```sh
python3 -m compileall -q design/NG1/code/python/rou
python3 -m unittest discover -s design/NG1/code/python/rou/tests -p 'test_*.py' -v
```

GitHub kernel integration additionally exercises disposable namespaces for:

- instance create/verify/repair/destroy;
- iptables filter + config-derived NAT round-trip;
- lifecycle route diff with overlapping Profiles and persistent table-local blackhole.

## Reference deployment

```sh
sudo design/NG1/deploy/install.sh
sudoedit /etc/vpn-gateway/routers/rou0.toml
sudoedit /etc/vpn-gateway/instances/rou0.toml

rou check rou0
sudo rou up rou0
rou show rou0
```

`rou up` enables the corresponding `rouvpn@rou0.service`; `rou down` disables it and
removes the owned appliance after proving the service inactive.
