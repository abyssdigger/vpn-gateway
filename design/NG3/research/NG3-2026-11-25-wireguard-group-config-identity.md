# NG3 recoverable-group configuration identity — 2026-11-25

## Question

Should generalized WireGuard recovery introduce a new user-facing `recoverable_group` object
that repeats payload prefixes, or can the accepted Profile configuration already provide the
group identity and network bundle?

## Existing semantic overlap

A Profile already owns exactly the user semantics needed to identify one independently
recoverable payload bundle:

- stable Profile ID;
- one or more `destinations`;
- an ordered set of allowed Devices;
- optional availability description;
- ordinary/reserve failover semantics at the Device-membership layer.

A recoverable WireGuard group needs the same payload identity but one level lower: for one
managed WireGuard Device used by that Profile, select among that Device's peers.

Introducing an independent group with its own `prefixes` would create two user-facing sources
for the same remote-network set: `Profile.destinations` for payload policy and
`recoverable_group.prefixes` for WireGuard ownership. Keeping them equal would require extra
cross-object consistency rules and would violate the existing config principle that
derived/redundant quantities are not repeated.

## Selected identity

For the current accepted R8 scope:

```text
recoverable group identity := (profile_id, managed_wireguard_device_id)
payload bundle             := Profile.destinations
```

Every enabled Profile membership in an enabled managed WireGuard Device therefore creates one
recoverable group for that Device. A Profile with several destinations moves those destinations
as one peer-ownership bundle. Two Profiles using the same `wg0` are independent groups and may
simultaneously resolve to different peers.

If the user needs two destination sets to recover independently, they are separate Profiles.
A future requirement may justify binding different Profile policy domains into one atomic
WireGuard recovery group, but no accepted requirement currently requires that extra entity or
cross-Profile coupling.

This identity does **not** merge Profile runtime availability with D.002 peer/group state.
Profile/A.007 and D.002 remain different semantic owners; the configuration simply avoids
inventing a second user object for the same network bundle.

## Group endpoint reuse

A Profile availability description is also the natural optional group end-to-end description
when, for the relevant managed WireGuard Device:

- it resolves to the supported ICMP mechanism; and
- its exact target lies inside one of that Profile's `destinations`; and
- the target is not any managed peer's permanent `probe_target`.

When these conditions hold, the same normalized description may create both an A.007 Profile
probe demand and a D.002 group probe demand. Their evidence identities and readiness verdicts
remain distinct even if C.001 deduplicates physical lower state.

If the Profile has no active check, or its selected check does not satisfy the in-group target
conditions, the recoverable group simply has no group endpoint. Peer-failure recovery still
works as required by R8.R3.

This avoids a second `availability_check` knob with conflicting meaning.

## Peer membership policy

The Device's managed `peers` declaration remains the authoritative set and default baseline
order. For each Profile -> managed-WireGuard Device membership:

- absent peer override: all configured peers are allowed in Device peer declaration order,
  all ordinary;
- optional `peer_order`: a non-empty ordered subset of peer IDs; `:reserve` has the same
  local-membership meaning already used by `Profile.device_order`;
- the same peer ID occurs at most once in one `peer_order`;
- unknown peer IDs and unknown suffixes are config errors;
- a peer omitted from this group-local list is not a candidate for this group;
- reserve is local to this group; it does not mutate the peer object or its role for another
  Profile.

The minimal human-facing extension is therefore metadata on the existing Profile/Device
membership, not a new network-group object.

## Canonical surface direction

Keep `device_order` as the one source of Profile Device membership and baseline Device order.
Optional per-membership detail is keyed by the referenced Device ID:

```toml
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16", "10.30.0.0/16"]
device_order = ["wg-main", "oc-backup:reserve"]

[profile.corp.device_membership.wg-main]
peer_order = ["edge-a", "edge-b:reserve"]
```

The nested table does not create membership: `wg-main` must already occur exactly once in
`device_order`. It is invalid on a non-managed-WireGuard Device. Omission means the default
all-peer ordinary policy and therefore requires no verbose table for the common case.

The name `device_membership` is intentionally semantic rather than WireGuard-specific:
the table is Profile-local policy attached to one existing Device membership. Only
`peer_order` is currently accepted inside it, and only for managed WireGuard; unknown fields
remain errors. This does not authorize a generic option bag.

## Consequences for implementation

A.002 normalization should eventually emit a typed group policy conceptually containing:

```text
WireGuardRecoverableGroupConfig:
    profile_id
    device_id
    prefixes := Profile.destinations
    peer_memberships[] := { peer_id, reserve }
    optional availability description
```

The availability description is reused only when it qualifies as an in-group group endpoint.
The D.002 Manager need not know TOML or inspect Profile objects directly.

The current `ManagedWireGuardConfig.shared_prefixes` one-group projection remains temporary
prototype debt. Generalized normalization should replace it with typed group inputs rather than
adding a second independent prefix list.

## Compatibility

No binding release exists. Therefore the current pre-binding one-group representation and
internal `shared_prefixes` normalized shape need not be preserved as compatibility aliases
when this generalized parser is implemented. Migration should choose the simplest canonical
model rather than carry historical schema solely because it existed in development builds.
