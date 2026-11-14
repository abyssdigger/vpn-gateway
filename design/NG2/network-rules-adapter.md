# VPN-GATE NG2 — NetworkRulesAdapter lower-domain design

**Статус:** active NG2 implementation design  
**Дата:** 2026-11-14  
**Область:** concrete lower domain behind `NetworkRulesAdapter`

## 1. Boundary

Public caller contract remains:

```text
apply(owner, spec: NetworkRulesSpec) -> ActionResult
renewState(owner) -> ActionResult
getLastState(owner) -> NetworkRulesState
cleanup(owner) -> ActionResult
```

`owner` is opaque caller-instance identity. `NetworkRulesSpec` remains independent from
owner/scope usage.

The lower domain owns:

- owner lifetime and physical composition;
- technical Linux allocation;
- route/RPDB/nft/sysctl materialization;
- safe transition ordering;
- fresh observation and semantic reconstruction;
- per-owner `NetworkRulesState`.

## 2. Internal owner identity

The Adapter assigns a monotonically increasing internal `owner_token` to each live caller
instance.

Properties:

- same Python object identity -> same token for its registered lifetime;
- equal-but-distinct objects -> different tokens;
- token has no payload/probe/domain meaning;
- Adapter keeps a strong reference while the owner is registered;
- cleanup releases the owner and its token registration;
- tokens are not reused during one Adapter instance lifetime.

The token exists only below the public Adapter boundary.

## 3. Owner-scoped logical identity

Routing-domain names are caller-local.

Physical/internal identity is therefore:

```text
(owner_token, logical_domain_name)
```

Two callers may both use `"default"` or `"corp"` without collision.

No owner name, type name or semantic caller label is used for technical identity.

## 4. Composition

The Adapter maintains one current desired `NetworkRulesSpec` per registered owner and
composes all live owners for the common physical backend.

Composition rules:

- routing domains remain owner-scoped;
- dispatch rules are considered in one common dispatch space;
- exact duplicate dispatch selectors owned by different owners are ambiguous and rejected;
- different destination prefix lengths remain deterministic through longest-prefix
  ordering;
- allow-only filtering intents from owners compose positively; one owner cannot delete
  another owner's permission by omission;
- flow-initiation allows follow the same positive composition rule;
- source-NAT intents remain owner-scoped during compilation so observation/cleanup can
  preserve provenance;
- no inter-owner priority is invented.

A backend may deduplicate physically equivalent rules, but such optimization must not
destroy the ability to reconstruct each owner's semantic state or to cleanup one owner
without changing another owner's effective state.

## 5. First implementation unit

The first executable unit contains only:

- owner registration/token lifetime;
- owner-scoped composed desired representation;
- deterministic composition;
- dispatch conflict detection;
- removal/recomposition semantics.

It performs no Linux I/O and allocates no tables/priorities/metrics.

This is not a speculative generic helper: it is the concrete state needed by the
multi-owner `NetworkRulesAdapter` before one shared Linux backend can be materialized.

## 6. Next lower units

After the composition unit passes review:

1. Linux technical allocation for composed routing domains/dispatch;
2. nft filter/NAT compilation with generation-aware ifindex markers;
3. observation -> per-owner semantic reconstruction;
4. safe transition/materialization with fail-closed barrier;
5. fresh verification and full public Adapter operations.

Existing NG1 code and EXP-012/017 are evidence sources, not code to copy wholesale.
