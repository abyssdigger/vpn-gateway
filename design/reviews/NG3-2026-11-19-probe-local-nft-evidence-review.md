# NG3 2026-11-19 — probe local nft evidence review

## Verdict

**PASS — current nft representation evidence is sufficient for the next probe-local owner
implementation unit.**

## Scope

This review does not implement probe local nft observation/mutation yet. It closes the lower
representation uncertainty that had to be resolved first.

EXP-066 materializes the already accepted EXP-024 local-admission shape in a disposable
namespace and records current nftables 1.1.6 JSON.

## Confirmed OUTPUT representation

Selected semantic rule:

```text
probe uid + exact current oif + exact target + ICMP
    -> set dedicated probe conntrack mark
    -> accept
```

Current JSON contains, in order:

- exact `meta skuid` match;
- exact `meta oif` match;
- IPv4 destination match;
- IPv4 protocol = 1;
- `ct mark` mangle assignment;
- terminal ACCEPT.

## Confirmed INPUT representation

Selected semantic rule:

```text
exact current iif + exact remote source + ICMP + probe conntrack mark
    -> accept
```

Current JSON contains:

- exact `meta iif`;
- IPv4 source;
- IPv4 protocol = 1;
- exact `ct mark` match;
- terminal ACCEPT.

As required by EXP-024, INPUT does not use `meta skuid`.

## Same-name/new-ifindex evidence

Initial `path0` had ifindex 2. After delete/recreate, new `path0` had ifindex 3.

The original nft rules survived, but JSON no longer displayed `"path0"` for their interface
selector. It exposed the stale raw ifindex as string `"2"`.

Therefore:

```text
resolved current name
    -> can map to current InterfaceIdentity

raw numeric old ifindex
    -> stale generation
```

A probe-local authoritative observer can distinguish interface replacement without adding a
second identity mechanism or depending on lexical ifname continuity.

## Deletion evidence

Both owner-commented rules exposed handles and were removed by exact chain + handle.

```text
EXP066_HANDLE_DELETE=PASS
EXP066_RESULT=PASS
```

This supports the same handle-based local nft mutation pattern already used by publication
and supported-integration owners.

## Architecture consequence

No separate nft table or new Manager is justified.

The next implementation should extend the existing `ip vpn_gate` composite owner with a
probe-local rule class identified by a dedicated comment and exact semantic decoder.

The implementation must preserve:

- exact current `InterfaceIdentity`;
- dedicated non-root probe UID only on OUTPUT;
- target/source specificity;
- ICMP-only Release-1 protocol;
- dedicated probe conntrack mark;
- no packet-mark restoration;
- no namespace-wide conntrack cleanup.

## Requirement-state inventory

No requirement or constraint changed. No active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

## Conclusion

The probe local nft layer no longer has a kernel/json representation unknown. Its next
observer/comparison/mutation unit can be implemented against direct current evidence rather
than guessed nft syntax.
