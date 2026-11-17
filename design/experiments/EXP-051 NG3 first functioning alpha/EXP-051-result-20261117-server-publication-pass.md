# EXP-051 extension result — installed server publication PASS

**Date:** 2026-11-17  
**Verdict:** **PASS**  
**Runtime/evidence commit:** `32167df614193baf6a6e2cc9b76dfdae710ad39c`  
**GitHub Actions run:** `44167358884`  
**Alpha smoke job:** `134336862209`

## Scope

This is an extension of the retained first-alpha EXP-051 result. It verifies the newly
materialized canonical Device `publish_vpn_server` path in the actual installed systemd
runtime; it does not rewrite the historical first-alpha evidence.

Configuration addition:

```toml
publish_vpn_server = "tcp/alpha-srv-host:14443>24443"
```

The Device remains active through the already enabled Profile. Publication is Device transport
policy and is materialized before a concrete VPN endpoint appears.

## Proven path

```text
alpha-srv netns
  198.19.254.2
      |
      | TCP -> 198.19.254.1:14443
      v
ordinary host
  alpha-srv-host 198.19.254.1
  table ip vpn_gate_publication
  fib daddr type local
  iifname "alpha-srv-host"
  tcp dport 14443
  dnat to 198.19.255.2:24443
      |
      v
managed vpn-gate-alpha netns
  vnga-inner0 198.19.255.2
  stack_input local-publication-v1
  TCP listener :24443
```

The managed listener observed the original external source `198.19.254.2`; the external
client observed the reply from `198.19.254.1:14443`.

## Lifecycle evidence

The publication is confirmed before the OpenVPN client unit starts, so it does not depend on
current VPN path discovery/binding.

After the ordinary VPN-only restart and two existing payload reconciliations, publication
remains valid.

On controller stop the runtime first converges empty host publication desired state and then
runs managed-domain teardown. The smoke confirms `table ip vpn_gate_publication` is absent
after stop.

## Observed markers

```text
EXP051_ALPHA_CONTROLLER_READY=PASS
EXP051_SERVER_PUBLICATION_E2E=PASS
EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS
EXP051_VPN_SYSTEMD_NAMESPACE=PASS:pid=4489
EXP051_FIRST_PAYLOAD=PASS
EXP051_FIRST_MANAGER_RECONCILE=PASS
EXP051_MANAGER_RECONCILE_COUNT=PASS:2
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS:old_pid=4489:new_pid=4620:old_ifindex=2:new_ifindex=3
EXP051_SERVER_PUBLICATION_STOP_CLEAN=PASS
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

## What is not claimed

- The runtime does not enable ordinary-host `net.ipv4.ip_forward`; the harness supplies the
  accepted external prerequisite.
- Exact IPv4/interface selectors must already exist; runtime only observes them.
- Removing the nft publication rule stops new flow classification through that rule. This
  result does not claim forced termination of transport sessions/conntrack entries that were
  already established before removal; no accepted requirement currently asks for that
  stronger session-lifecycle semantic.
