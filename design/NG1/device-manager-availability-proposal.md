# NG1 DeviceManager availability policy proposal

Status: **HUMAN DESIGN DECISION REQUIRED BEFORE IMPLEMENTATION**

Evidence baseline:

- EXP-016: ECMP hash policy prerequisite PASS; production owns
  `net.ipv4.fib_multipath_hash_policy=1`.
- EXP-019: WireGuard can remain bound on the same `(ifname,ifindex)` while the payload
  path is unavailable and later recover without a new generation.
- EXP-020: OpenConnect shows the same retained-generation outage/recovery behavior.
- Therefore binding identity and process/interface presence are not positive availability
  evidence for either first-class transport.

This proposal deliberately stops before changing schema or production code.

## 1. Normalized ownership boundary

Availability belongs to one concrete bound interface generation:

```text
AvailabilityKey = (device_name, ifname, ifindex)
```

The provider returns only the normalized enum already used by the routing core:

```text
UNKNOWN
AVAILABLE
UNAVAILABLE
```

Transport/probe/process details never enter TrafficEngine/route projection.

A new generation always begins at UNKNOWN. Availability evidence from a retired generation
is never inherited by a same-name/new-ifindex replacement.

## 2. Safety semantics

Positive UNAVAILABLE changes routing behavior and can make the persistent shadow fallback
effective. Therefore it requires **positive path-failure evidence** rather than absence of
recent success metadata.

Proposed state machine:

```text
new binding
    -> UNKNOWN

UNKNOWN
    -- sufficient consecutive successes --> AVAILABLE
    -- sufficient consecutive failures  --> UNAVAILABLE

AVAILABLE
    -- sufficient consecutive failures  --> UNAVAILABLE

UNAVAILABLE
    -- sufficient consecutive successes --> AVAILABLE

binding generation disappears
    -> state discarded
```

No timeout based solely on interface/process presence, WireGuard handshake age or
OpenConnect process state may produce AVAILABLE or UNAVAILABLE.

## 3. Proposed evidence primitive for schema version 1

The smallest cross-transport primitive proven by both EXP-019 and EXP-020 is an active
IPv4 path probe forced through the concrete bound interface.

Candidate schema:

```toml
[device.oc-main.availability]
mode = "icmp"
target = "172.20.130.1"
interval = "2s"
timeout = "750ms"
failures = 3
successes = 2
```

Equivalent WireGuard example:

```toml
[device.wg-backup.availability]
mode = "icmp"
target = "172.20.126.1"
interval = "2s"
timeout = "750ms"
failures = 3
successes = 2
```

The exact values above are examples only and are **not proposed defaults**.

### Probe routing requirement

A probe must be tied to the concrete interface generation being evaluated, not merely to a
destination that ordinary routing might send through another Device.

Implementation must therefore use an interface-bound probe mechanism proven to select the
intended generation. For Python this may be iputils `ping -I <ifname>`, a socket using
SO_BINDTODEVICE, or a protocol-specific equivalent, but the exact mechanism is an
implementation experiment rather than schema semantics.

If the probe mechanism cannot prove generation-specific egress, availability remains
UNKNOWN.

## 4. Target ownership alternatives

### Option A — explicit administrator target per Device

The administrator provides one IPv4 target known to represent the remote path.

Advantages:

- transport-neutral;
- explicit trust/operational semantics;
- easy to explain and diagnose;
- no need for DeviceManager to infer protocol-specific peer addresses.

Costs:

- another required configuration field;
- target availability may fail independently of the tunnel;
- operator must choose a stable target.

### Option B — transport-derived target

DeviceManager derives a natural peer/tunnel endpoint:

- WireGuard: selected peer tunnel address;
- OpenConnect: server-side tunnel/local address.

Advantages:

- less configuration;
- directly tied to transport topology.

Costs:

- transport-specific inference rules;
- WireGuard Device may eventually have multiple peers;
- OpenConnect server-side probe address may not always be discoverable or reachable in the
  same way;
- introduces hidden policy into DeviceManager.

### Option C — explicit target with optional transport-derived default

Advantages:

- convenient for common cases;
- operator can override.

Costs:

- schema semantics become more complex immediately;
- inferred defaults can be surprising and harder to keep Rust/backend-independent.

**Recommendation:** Option A for the first availability implementation. Keep target
selection explicit and transport-neutral. Transport-derived convenience can be added later
without changing normalized Availability semantics.

## 5. Cadence and hysteresis alternatives

Availability must avoid both slow failover and flap-induced route churn.

Candidate configuration concepts:

- `interval`: time between probe rounds;
- `timeout`: maximum time for one probe;
- `failures`: consecutive failed rounds required for UNAVAILABLE;
- `successes`: consecutive successful rounds required for AVAILABLE/recovery.

No values should be guessed from EXP-019/020 because those experiments prove only the raw
signal, not production timing.

Two possible product directions:

### Direction 1 — all values explicit

No production defaults.

Advantages:

- no hidden operational policy;
- exact behavior visible in config.

Costs:

- verbose configuration;
- operator must understand four timing parameters.

### Direction 2 — named policy presets plus optional overrides

Example:

```toml
policy = "normal"
target = "172.20.130.1"
```

with documented preset timing.

Advantages:

- simpler common configuration.

Costs:

- presets are user-visible product policy and require their own evidence/maintenance;
- harder to change later without compatibility implications.

**Recommendation:** explicit values in the first implementation unless the maintainer
prefers a deliberately opinionated default policy.

## 6. UNKNOWN semantics

UNKNOWN is not failure.

Proposed behavior:

- a newly bound interface immediately participates in the normal tier, matching the current
  architecture;
- probes begin asynchronously;
- first positive evidence may normalize it to AVAILABLE;
- only the configured failure threshold moves it to UNAVAILABLE;
- inability to execute the detector itself (missing binary, permission error, malformed
  response, provider exception) produces UNKNOWN, not UNAVAILABLE.

This preserves the distinction between "path proved bad" and "detector cannot decide".

A persistent detector malfunction is operationally visible and should be surfaced in status
and logs.

## 7. Failure/recovery counters and event timing

Counters are scoped to `AvailabilityKey` and reset on generation change.

Suggested semantics:

- success resets failure counter;
- failure resets success counter;
- transition occurs only when the relevant threshold is reached;
- after transition, counters reset to zero;
- event timing is monotonic-clock based;
- probe scheduler must not use wall-clock time for thresholds.

Availability changes wake Planner, but Planner still collects fresh environment state and
does not treat the probe event payload itself as authoritative kernel state.

## 8. Probe admission and firewall

A locally generated probe exits through a Device interface.

Current ROU OUTPUT policy intentionally denies locally generated Device-interface traffic.

Therefore implementing active probes requires one explicit generated OUTPUT admission
limited to the availability probe itself:

```text
-o <bound-ifindex>
-d <target>/32
-p icmp
ICMP echo-request
-> ACCEPT
```

This rule is generation-scoped and exists only while that binding is under availability
management.

No broad Device-interface OUTPUT allowance is introduced.

This is a security-boundary change and must be approved together with the availability
schema.

## 9. Status/diagnostics

For each bound interface status should expose at least:

- normalized availability;
- last probe result;
- consecutive success/failure counters;
- last successful probe monotonic age / human-readable elapsed duration;
- last failed probe elapsed duration;
- detector health/error text, without secrets;
- configured target and timing policy.

Routing/status consumers use only normalized Availability; detailed evidence remains
diagnostic.

## 10. DeviceManager execution boundary

First implementation should keep process lifecycle and availability as two separable
providers under DeviceManager:

```text
DeviceProcessProvider
AvailabilityProvider
```

A transport can initially use only AvailabilityProvider against an externally supervised
VPN process. This avoids making VPN process launching a prerequisite for availability
work.

Later DeviceManager can compose both without changing Planner/TrafficEngine contracts.

## 11. Required implementation experiment

Before production code commits to the generic ICMP provider, prove on a disposable
namespace that the selected probe primitive:

1. sends through the specified concrete interface;
2. does not escape through an alternate route when the intended path is down;
3. handles same-name/new-ifindex replacement without transferring probe ownership;
4. behaves correctly with current OUTPUT default-DROP policy plus the narrow generated
   admission;
5. returns bounded success/failure within the configured timeout.

This should become EXP-021 if the design is approved.

## 12. Human decisions required

Implementation should not proceed past the normalized provider skeleton until the
maintainer chooses:

1. **target ownership**
   - A: explicit per-Device target;
   - B: transport-derived target;
   - C: explicit target with inferred default.

2. **timing policy**
   - explicit interval/timeout/failure/success values;
   - or named presets/defaults.

3. **probe protocol for first implementation**
   - ICMP echo as the common primitive proposed here;
   - or another deliberately selected protocol.

4. **security policy**
   - approve the narrow generation-scoped OUTPUT exception for availability probes.

## Recommendation

For the first production availability slice:

- explicit per-Device IPv4 target;
- ICMP echo;
- all timing/hysteresis values explicit;
- generation-scoped narrow OUTPUT admission;
- detector failures -> UNKNOWN;
- Device process lifecycle remains a separate future provider.

This is intentionally simple, visible in configuration and compatible with a later Rust
trait/provider implementation.
