# EXP-033 — NG3 exact-ifindex payload masquerade

## Purpose

Validate the lower realization selected for normalized Device
`NatIntent.MASQUERADE`:

```text
meta iif == current host-boundary ifindex
meta oif == current path-endpoint ifindex
masquerade
```

The experiment does not select final TOML syntax.

## Packet proof

The remote-side namespace deliberately has **no route back** to either ordinary-side test
subnet.

Therefore an ordinary -> remote ping can complete only if the gateway source-NATs the
request to its path-side address and conntrack reverses that NAT on the reply.

## Hypotheses

- **H1:** nft accepts exact numeric meta iif/oif matches in postrouting;
- **H2:** the rule has an unambiguous JSON representation;
- **H3:** the matching ordinary-boundary/path flow is actually masqueraded;
- **H4:** a different ingress interface does not match the payload NAT rule;
- **H5:** replacing the path interface with the same name and a new ifindex does not match
  the stale numeric rule; a new rule using the new ifindex restores the behavior.

## Filter setup

The experiment uses the accepted `payload_forward policy drop` scaffold plus explicit
test-only interface allow rules so forwarding permission is not the variable under test.

## Safety

All namespaces, interfaces and nft state are disposable.

## Acceptance

All hypotheses must pass in privileged GitHub CI before exact-ifindex masquerade becomes the
executable lower NAT contract.
