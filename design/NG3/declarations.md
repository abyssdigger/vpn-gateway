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

## Future VPN configuration and lifecycle automation

Preliminary future-product expectation: VPN-GATE may eventually support automation of
supported VPN implementations using data already present in the gate configuration.

Potential future scope includes:

```text
VPN config templates / rendered configuration
start command
reload command
restart command
stop command
```

The intent is to make automatic VPN setup and lifecycle control possible without treating
those concrete commands/templates as part of the core Profile/Device policy model.

This capability is **not proposed as part of the current release scope**. Current releases
may continue to consume externally managed VPN interfaces/processes. Before any implementation,
a later requirement/design cycle must define supported integrations, template inputs and
ownership, command execution/security boundaries, idempotency, failure handling, privilege
model, and the exact relationship between VPN lifecycle state and VPN-GATE desired-state
publication.
