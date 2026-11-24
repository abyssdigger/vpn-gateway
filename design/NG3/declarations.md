# NG3 — Development declarations

These declarations record current engineering intent that is deliberately **not** promoted to
the normative requirement tree yet. They do not create product acceptance criteria,
architecture closure gates or implementation obligations by themselves. The project may
revisit and, where justified by working-code evidence and product need, convert them into
formal Requirements/Constraints later.

A declaration is an exploratory, non-normative record, not an approved deferral:
it does not authorize independent design, implementation, testing or release
acceptance of the described capability. Work may investigate or discuss a
declaration, but promotion to executable scope requires the applicable normative
Requirements/Constraints, architecture and human-acceptance gates. By contrast, a deferral records already accepted work that has been explicitly
postponed with a defined re-entry condition; see `CONTINUOUS-DEVELOPMENT.md` (§ Blocking and deferral).
Neither a declaration nor a deferral can silently supersede current normative
requirements.

## Promoted declarations

The former declarations for resource efficiency / weak-device suitability and the compact
human current-state view were promoted to normative operational-cost requirements
`VPNG-M001-R3` and `VPNG-M001-R2.R2` respectively. Their current wording and acceptance
state now belong only to `design/NG3/requirements.md`; Git history retains the preliminary
declaration text.

## Post-first-release external Profile network sources

Preliminary future expectation outside the current release scope. Revisit it **after the
first release**, together with managed Devices / VPN lifecycle automation.

A future Profile may be able to combine:

```text
inline network prefixes
+ one or more external network-list files
    -> one normalized runtime prefix bundle
```

Candidate reload semantics for this **post-first-release external-source feature** remain:

- external files are reread on explicit reload;
- the currently published runtime state continues operating while the candidate reload is
  parsed/normalized;
- only after reload processing completes is a new desired state published;
- malformed individual source lines should be warnings + skipped entries rather than
  automatically disabling the whole Profile.

This external-source feature is intentionally not part of first-release planning. `VPNG-M001-R1.R1.R6` requires a supported way to apply changed configuration but does not require a distinct `reload` operation; the current alpha may therefore require restart. If a future management interface exposes `reload`, its behavior and result belong to that interface/architecture contract rather than to a separate product capability. This section additionally keeps rereading/merging external Profile network-list sources post-first-release. Without managed Device/VPN
configuration ownership its near-term value does not justify the external-source complexity.
File-level failure semantics, syntax, provenance and atomicity scope are therefore left
unspecified until that post-first-release discussion rather than treated as an accepted
deferral.

## Promoted: VPN configuration and lifecycle automation

The former future declaration for VPN configuration generation and lifecycle automation was
promoted on 2026-11-24 to normative requirement branch `VPNG-U001-R1.R3.R7*`.

The current requirement tree now owns the product decision: Device management is explicit,
externally prepared Devices remain supported when management is not enabled, and managed
WireGuard multi-peer work is an open requirement rather than a declaration. Detailed design
remains unresolved and is tracked by the current research/review artifacts.

