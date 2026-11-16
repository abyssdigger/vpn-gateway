# EXP-030 — NG3 managed-netns forwarding barrier

## Purpose

Validate the first-release root structural barrier selected for NG3:

```text
managed network namespace
net.ipv4.ip_forward = 0
```

The experiment tests packet behavior, not only sysctl syntax.

## Topology

```text
left namespace
10.30.1.2/24
      |
      | veth
      |
managed gate namespace
10.30.1.1/24
10.30.2.1/24
      |
      | veth
      |
right namespace
10.30.2.2/24
```

Both edge namespaces have explicit routes through the managed gate.

## Hypotheses

- **H1:** the managed namespace forwarding sysctl can be written and freshly reread;
- **H2:** changing it does not change the host namespace value;
- **H3:** verified `ip_forward=0` blocks real IPv4 transit packets;
- **H4:** verified `ip_forward=1` restores forwarding when routes/interfaces permit it;
- **H5:** the safety decision can use a direct reread of the effective namespace value.

## Safety

All packet-path objects are disposable network namespaces and veth pairs.

The experiment records the host `net.ipv4.ip_forward` value and never writes it.

## Acceptance

All hypotheses must pass in privileged GitHub CI before the managed-netns sysctl is accepted
as the executable NG3 structural root barrier.
