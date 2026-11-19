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
Requirements/Constraints, architecture and human-acceptance gates. By contrast,
a deferral records already accepted or explicitly gated work with a defined
re-entry condition; see `CONTINUOUS-DEVELOPMENT.md` (§ Blocking and deferral).
Neither a declaration nor a deferral can silently supersede current normative
requirements.

## Resource efficiency and weak-device suitability

VPN-GATE should remain practically suitable not only for powerful hosts but also for
resource-constrained gateways and weak devices.

Where several designs provide the required observable behavior, prefer the simpler design
with lower steady-state CPU, memory, allocation and state-tracking cost. In particular,
per-flow/conntrack-like state, large lifecycle tables, background bookkeeping and other
resource-expensive machinery should not be introduced merely for theoretical completeness
when bounded Profile/path-level state provides the needed behavior.

This declaration is supporting engineering guidance only. It is intentionally not a current
Requirement or Constraint; quantitative limits and acceptance thresholds are deferred until
working implementation evidence provides a useful basis for them.


## Runtime transparency / human current-state view

Preliminary user expectation: once the basic alpha functionality is operational and there is
meaningful runtime state to observe, VPN-GATE should provide a compact human-readable current
state view for testing and operational transparency.

This is a **presentation of current runtime state**, not an effective configuration dump and
not a round-trippable config format.

The primary text view is expected to have exactly two user-facing sections.

```text
Devices
    wg-main: wg0
    oc-office: tun0, tun1
    spare: not discovered
    old-vpn: disabled
Profiles
    corp
        01. wg0 available (icmp/10.20.0.1)
        02. tun0 not available (icmp/10.20.0.1)
        03. tun1 unchecked
    internet
        01. tun3 unknown (icmp/1.1.1.1)
        02. wg2 unchecked
    legacy: disabled
```

Formatting intent:

- every nesting level uses four spaces;
- there is no blank line between a section heading and its first row;
- one Device occupies one line;
- a disabled Profile is one line: `<profile>: disabled`;
- enabled Profile interfaces are listed on indented lines;
- Profile interface rows are explicitly numbered `01.`, `02.`, ... to emphasize that
  their order is the **current effective routing order**, not merely configured membership.

For Devices, the first-release/current view should show the Device name and currently
discovered interface name(s), or an explicit state such as `not discovered` / `disabled`.
If another current Device fact later proves operationally important it may be added, but
internal Linux implementation details are not the purpose of this compact view. Future
managed Devices may extend the same row with their operational status.

For enabled Profile paths:

- no configured availability check -> `unchecked`;
- check configured but no current confirmed availability result -> `unknown (<normalized-check>)`;
- confirmed usable -> `available (<normalized-check>)`;
- confirmed unusable -> `not available (<normalized-check>)`.

The text inside parentheses is the normalized availability-check expression, effectively the
normalized config form such as `icmp/10.20.0.1`. Low-level probe failure details belong in
logs rather than this compact view.

The implementation is deliberately blocked until the basic alpha runtime is operational:
before routing/binding/probing produce meaningful current state, there is little useful state
to render and little value in testing the renderer itself. Once the basic alpha path works,
this view becomes an alpha testing/debugging aid.

After the first release, the same semantic runtime snapshot may gain JSON and/or TOML
renderers. Those are alternative serializations of one authoritative snapshot model, not
separate diagnostic state models.

This remains a preliminary user expectation, not a normative Requirement/Constraint, until
the alpha runtime provides enough working evidence to promote it cleanly.

## Post-first-release external Profile network sources

Preliminary future expectation, explicitly deferred until **after the first release** and to
be discussed together with managed Devices / VPN lifecycle automation.

A future Profile may be able to combine:

```text
inline network prefixes
+ one or more external network-list files
    -> one normalized runtime prefix bundle
```

Candidate future reload semantics remain:

- external files are reread on explicit reload;
- the currently published runtime state continues operating while the candidate reload is
  parsed/normalized;
- only after reload processing completes is a new desired state published;
- malformed individual source lines should be warnings + skipped entries rather than
  automatically disabling the whole Profile.

This feature is intentionally not part of first-release planning. Without managed Device/VPN
configuration ownership its near-term value does not justify the source/reload complexity.
File-level failure semantics, syntax, provenance and atomicity scope are therefore postponed
for the same post-first-release discussion rather than specified now.

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

This capability is explicitly **not required for the first releases**. Current releases may
continue to consume externally managed VPN interfaces/processes. Before any implementation,
a later requirement/design cycle must define supported integrations, template inputs and
ownership, command execution/security boundaries, idempotency, failure handling, privilege
model, and the exact relationship between VPN lifecycle state and VPN-GATE desired-state
publication.
