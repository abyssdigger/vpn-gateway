# NG3 2026-11-18 — sticky/reserve reference code review

## Verdict

**PASS for the bounded reference-code slice.**

This review covers canonical `:reserve` parsing/normalization and the pure
`AvailabilityPriorityCalculator` behavior accepted by
`NG3-2026-11-18-sticky-active-route-reserve-review.md`.

It does **not** claim that the production runtime already owns or persists
`current_active_path`, nor that availability probing is activated end to end.

## Reviewed implementation

### ConfigurationAdapter

`release1_config.py` accepts Profile-local Device memberships in canonical forms:

```text
<deviceid>
<deviceid>:reserve
```

For enabled Profiles it normalizes the human-facing list before the lower structural parser:

```text
device_order[]       -> plain Device IDs
reserve_device_ids[] -> Profile-local subset of those Device IDs
```

The lower structural parser therefore remains unaware of suffix syntax.

Validated behavior:

- unsuffixed membership is ordinary/sticky;
- `:reserve` is local to one Profile and does not mutate Device identity;
- the same Device may be reserve in one Profile and ordinary in another;
- unknown/multiple membership suffix syntax is rejected;
- duplicate underlying Device membership after suffix normalization is rejected;
- disabled Profile placeholders keep the existing shallow-validation boundary.

### AvailabilityPriorityCalculator

`availability_priority.py` now accepts:

```text
configured_paths
problem_paths
active_path?
reserve_device_ids[]
```

and returns exactly the same structural path membership in effective order.

Reviewed rule:

```text
no usable current active
    -> usable paths in baseline order

usable ordinary active
    -> active first
    -> all other usable paths in baseline order

usable reserve active
    -> if a higher-baseline usable path exists, baseline usable order wins
    -> otherwise reserve active remains first

problem paths
    -> remain structurally present after usable paths in baseline relative order
```

The calculator is pure. It owns no history, flow table, conntrack lifecycle or timer.

## Review correction made during the slice

The first implementation draft accepted `reserve_paths`. That API could express a state
forbidden by the accepted model: one logical path of a Device could be reserve while another
path of the same Profile-local Device membership was not.

The API was corrected to `reserve_device_ids`. The calculator derives reserve behavior from
`LogicalPathId.device_id`, so all current logical paths produced by one reserve Device
membership inherit the role. A reserve Device with no currently bound path remains valid
configuration state.

The public sidecar field was also aligned with the architecture name
`reserve_device_ids`.

## Tests

Unit coverage includes:

- ordinary recovery keeps a healthy active path first;
- standby paths keep baseline relative order;
- reserve active yields to a higher-baseline usable path;
- reserve active remains first while all higher paths are problematic;
- problematic active loses sticky position;
- structural path membership is unchanged;
- invalid/duplicate problem, active and reserve inputs are rejected where applicable;
- canonical `:reserve` parsing is Profile-local;
- unknown suffix and duplicate underlying Device membership are rejected;
- end-to-end pure projection:
  `canonical config -> reserve_device_ids -> Device binding -> logical paths -> reserve failback`.

GitHub Actions run `44397723275` on code commit
`10bb14d2d2fdb33bf93d5c38afe40e10ba539cab` reports the `unit` job **PASS**.

A prior intermediate run failed because tests still used the superseded
`reserve_paths` keyword after the API review correction; that mismatch was fixed before the
reviewed commit.

## Unrelated CI baseline

The same workflow contains privileged historical experiments unrelated to this pure/config
slice. `linux-nft-marked-host-bootstrap` / EXP-057 still fails at its known namespace ping
step in the reviewed run. The same job already failed on pre-change main run
`44346051308`, while that run's `unit` job passed.

This review therefore does not treat that pre-existing privileged experiment failure as a
regression or as evidence about sticky/reserve logic.

## Complexity / resource boundary

The implementation adds:

- one Profile-local reserve Device-ID set in normalized configuration;
- one optional Profile-level active path input to the pure ordering function.

It adds no per-flow table, tuple tracking, timeout/GC lifecycle, conntrack ownership or
connection migration machinery.

This is consistent with the non-normative resource-efficiency declaration without promoting
that declaration into a Requirement or Constraint.

## Requirement-state inventory

This code slice creates no active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

The normative semantics remain those already closed in the preceding sticky-active-route
design review.

## Remaining implementation boundary

Production availability activation still needs a bounded Manager/runtime owner that supplies
the current active path and current confirmed problem set to the pure calculator, then
converges the resulting effective order through the existing route-priority machinery.

That is a separate implementation unit. It does not reopen the accepted route-selection
semantics and does not require per-flow tracking.

## Conclusion

The reference implementation now represents the accepted simplification directly:

- default recovery is sticky at Profile route level;
- reserve is an explicit Profile-local Device-membership opt-out;
- canonical configuration reaches the calculator without leaking suffix syntax downward;
- outbound availability stability no longer depends on conntrack/per-flow affinity.
