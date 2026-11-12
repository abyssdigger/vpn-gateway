# NG1 nftables production-backend migration

Status: normative deployment note for the first NG1 production baseline.

## Production backend

NG1 production owns IPv4 packet policy through nftables:

- `table ip vpng_filter`
- `table ip vpng_nat`

Dynamic Device interfaces are matched by numeric ifindex. Full policy semantics and the
numeric iif/oif generation reference multiset are both verified.

Legacy `iptables-legacy` projectors remain in the source tree only as historical/regression
evidence. They are not a production runtime backend.

## Pre-production migration boundary

In-place migration of an already-running namespace created by a pre-nft development build
is **not supported**.

Before deploying the nft production baseline over such a development instance:

```text
rou down <instance>
install/update code
rou up <instance>
```

The down/up boundary deletes and recreates the dedicated network namespace, so no legacy
iptables filter/NAT state survives into the nft-owned appliance.

The production runtime deliberately does not depend on `iptables-legacy` solely to detect
or clean historical development state.

## Runtime ownership

Inside a production ROU namespace, the nft ruleset is exclusive ROU state.

Only the two owned tables above are permitted. Any additional nft table is structural
drift:

1. forwarding is closed;
2. foreign tables are removed;
3. owned routing/RPDB/nft state is rebuilt;
4. complete state is freshly verified;
5. forwarding may reopen.

Ordinary verified binding lifecycle transitions do not use the global barrier.

## Evidence

EXP-017 proves numeric nft iif/oif generation isolation and JSON numeric generation
observation across same-name/new-ifindex replacement.

The privileged NG1 CI additionally applies and verifies the production nft filter/NAT
tables in a disposable namespace.
