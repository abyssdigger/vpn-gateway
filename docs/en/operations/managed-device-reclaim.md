# Managed Device reclaim

[Русская версия](../../ru/operations/managed-device-reclaim.md) · [Documentation home](../README.md)

**Applicability:** current NG3 development, exact revision containing this page. **Development candidate — not accepted for release.** Configuration parsing, helper/model code and the startup/periodic reclaim call sites are implemented in this revision; integrated evidence and acceptance of [#41](https://github.com/abyssdigger/vpn-gateway/issues/41) remain pending. The behavior below states the accepted target contract, not a claim that the integrated runtime has passed verification. It is not an operator instruction for version 0.1.0.

## Purpose and configuration

Reclaim automatically frees surplus, already-present managed ordinary VPN Devices. It does not manage external Devices and does not change structural presence demand. Explicit Device disable/remove, product shutdown and stronger safety-owned cleanup are separate lifecycle operations; reclaim protection does not prevent them. Required reserve presence is a separate mandatory obligation. Once ordinary demand is satisfied, the reserve exception is withdrawn; safe release of an otherwise unnecessary reserve remains governed by that reserve lifecycle rule. If the same physical Device is also an ordinary member of another Profile, its ordinary contribution and protection must still be considered.

Use the top-level TOML setting `managed_reclaim` for the whole managed domain:

- `"careful"` (default): protects an exact, confirmed current ordinary path used by any enabled Profile.
- `"strict"`: may release a confirmed used Device if doing so preserves the required ordinary capacity across every affected enabled Profile; keeping the current path is a preference between equally valid choices, not an independent retention obligation.

`warm_paths` defines structural ordinary demand for its Profile; reclaim neither overrides that target nor starts or restarts an absent VPN to optimize the set. Retained presence and authorization to start a Device are different.

## How release decisions are made

After successful strict reconciliation, no individually releasable surplus managed ordinary Device may remain. For each affected enabled Profile, the retained ordinary capacity must be at least the smaller of its resolved numeric ordinary target and its fresh eligible ordinary capacity before release. A physical Device can contribute to several Profiles; consider all such contributions. This is a single-removal irreducibility rule, not a guarantee of a globally minimum set.

In careful mode, an already-present exact ordinary realization confirmed as currently used remains protected even if structural demand could be satisfied by another path. The decision is reconsidered using fresh observations on later triggers. Unknown or stale usage does not prove absence of use or safe retirement.

A deferred Device may remain physically present without gaining payload/probe eligibility. Independent exact structural demand can authorize eligibility, including cold startup. An already accepted deferred path can preserve exposure only while its exact binding and realization still match fresh evidence. A replacement or unknown identity does not inherit that exposure.

## Execution and failure handling

The intended normal trigger freezes one reclaim plan from fresh pre-prune state, converges replacement policy without its retirement candidates, confirms dependencies, and attempts a bounded retirement batch. It checks candidate identity/generation, affected Profile floors and required retained paths before cleanup and again before exact retirement. Managed WireGuard cleanup must be freshly confirmed: only permanent peer probe /32 prefixes may remain on the retiring Device, without Profile payload ownership.

Failure or drift stops further retirement attempts. An already successful earlier retirement is not automatically rolled back. A batch failure or lower-state touch requires one non-recursive fresh recovery of normal policy. A later trigger reassesses the fresh state; it does not replay the old retirement plan. A fresh status-only projection must never authorize another release in the same recovery.

## Reading runtime status

The target development status distinguishes:

| Field | Meaning |
| --- | --- |
| `configured_intent.managed_reclaim` | Configured domain policy, not proof of retirement |
| `managed_profile_demands` | Structural ordinary/reserve demand and observed capacity |
| `managed_reclaim_projection` | Fresh read-only reclaim projection: survivors, retirement candidates, deferred decisions, reasons and exact identities/generations where confirmed |
| `managed_device_realizations` | Actual lifecycle realization, including intent basis and payload eligibility |

A survivor is retained by the current reclaim projection; it is not necessarily structurally demanded. A retirement candidate is a proposed exact release, not confirmed absence. A deferred decision is unresolved and is not authorization to newly expose or retire a Device.

If the projection is unconfirmed, the JSON field is null; do not interpret that as an empty candidate set. An intentionally held exact present Device is not a failed absence solely because it has no structural demand. Explicit lifecycle failures and unknown identity/generation are real problems. A reserve can keep payload policy working while the primary start failure remains a DEGRADED condition. A batch problem must not disappear merely because normal policy recovery succeeded.

## Configuration illustration

This is a synthetic, incomplete TOML fragment, not a deployable configuration or an executed verification example. The actual configuration also needs valid Device, Profile and network settings.

```toml
managed_reclaim = "careful"

[profile.corp]
warm_paths = 1
```

Suppose two eligible ordinary managed VPNs are already present and the Profile needs one. If the currently used VPN is confirmed exact, careful protects it even when another would satisfy structural demand. Strict may release a used surplus VPN only when the fixed floors and other mandatory obligations remain satisfied; with equal valid choices it prefers to keep the used path. If relevant facts are unknown, do not infer safe retirement.

## Limitations and verification state

The normal runtime entrypoints now use the new reclaim path in this development candidate. Staged helper tests do not establish integrated runtime acceptance or release support. The final page must be reconciled with the exact integrated implementation, status rendering and Linux evidence before the #41 candidate is accepted. Wider NG3 documentation coverage remains incomplete.
