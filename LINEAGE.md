# Repository lineage

This branch is the active VPN-GATE development line.

The repository was split on 2026-11-17 so the active `main` tree no longer carries
historical generation implementations and their CI.

Historical lines are preserved as branches:

| Branch | Preserved boundary |
| --- | --- |
| `legacy-main-rc` | RC2/RC3 line through the last pre-NG1 main commit |
| `legacy-main-ng1-2` | NG1/NG2 line through main snapshot 30/44, immediately before NG3 |
| `legacy-main-ng3` | former mixed `main` through NG3 snapshot 74 |

The active `main` contains only:

- current NG3 normative/design/runtime artifacts;
- shared generation-independent project models;
- NG3 experiments, reviews and deferrals;
- current project/process documents;
- current NG3 CI and the actual-main lineage guard.

Historical evidence may be cited by branch-qualified reference, for example:

```text
legacy-main-ng1-2:design/NG2/availability-routing-model.md
legacy-main-rc:design/RC3/architecture.md
```

Legacy files are not copied back into active `main` merely to make a historical relative
link resolve. If historical evidence becomes materially relevant to a new NG3 decision,
reference the preserved legacy branch/commit explicitly.

## Closed active-main split cycle

The first active-line split is closed at main snapshot 75:

```text
b28f3e647d51b3c9f97190eb2daedaf253a68a88
tree 1297e5d42b7bb3816bfc6478b3ffc20549cf42e9
```

That snapshot proves the desired clean active tree and CI separation, but it deliberately
retains the old repository ancestry. It is therefore a safe working main and a reference
state, not yet the final ancestry shape.

Any future ancestry reconstruction is performed on a separate candidate branch and must not
move `main` until the complete candidate history has been independently reviewed.

### Future-main reconstruction invariant

The preserved former-main NG3 snapshot line begins at:

```text
snapshot 31/44  edeac340fab70bfe8df3a5f2a034fdf3ca7af8be
```

whose original parent is the last pre-NG3 snapshot:

```text
snapshot 30/44  d50652b7d2e8f671c18823ffcb588103257baa0d
```

A future clean-ancestry candidate must reconstruct the NG3 line from snapshot 31 onward.

Snapshot 31 becomes the parentless root from the **full snapshot-31 tree after one
deterministic generation-legacy filter**. The root keeps generation-independent shared files
that already existed when NG3 started, because later NG3 snapshots modify them. It excludes
only inherited generation payload present before NG3:

```text
design/RC2/**
design/RC3/**
design/NG1/**
design/NG2/**
.github/workflows/rc3-python.yml
.github/workflows/ng1-python.yml
.github/workflows/ng2-python.yml
pre-NG3 design/experiments/**
pre-NG3 non-NG3 design/reviews/**
```

At snapshot 31 the retained shared baseline includes, among other files,
`CONTINUOUS-DEVELOPMENT.md`, `PROJECT-CONVENTIONS.md`, `CHANGELOG.md`,
`design/requirements-model.md`, shared component-model documents and the shared experiment
journal. This is necessary: snapshot 32 already modifies
`CONTINUOUS-DEVELOPMENT.md` and `design/requirements-model.md`; a four-file
`30 -> 31` delta applied to an empty tree would therefore make snapshot 32 structurally
different from its source.

After the filtered parentless snapshot-31 root is established, every later reconstructed
commit through legacy snapshot 74 must preserve the exact original commit delta against its
corresponding original parent. The preserved NG3 sequence was checked for modifications to
the excluded RC/NG1/NG2 generation trees and legacy generation workflows; none occur.

This applies both to numbered snapshots and to meaningful inter-snapshot process commits.
In particular, the standalone `AGENTS.md` process commit
`211aefdc03a529162bb28385def6d21cc19db5aa` between snapshots 44 and 45 is part of the
reconstructed sequence because omitting it would change the delta of snapshot 45.

For each reconstructed commit the review manifest must contain:

```text
original identity / label
original parent
original commit
reconstructed parent
reconstructed commit
delta-equivalence verdict
```

Any delta mismatch is a stop condition. It must not be repaired by silently changing the
reconstructed snapshot.

The reconstruction candidate may be named `futuremain`; until a separate cutover decision,
the current `main` remains authoritative and unchanged.
