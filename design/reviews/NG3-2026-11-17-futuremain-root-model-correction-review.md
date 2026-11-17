# NG3 review — futuremain root-model correction

**Date:** 2026-11-17  
**Cycle:** `ng3-housekeeping-cycle-20261117-futuremain-root-correction-35m`  
**Baseline:** main snapshot 76, `c5537bc86755bfbb2f1814d5abd53f96ea953cd1`

## Trigger

The previous handoff proposed reconstructing futuremain by applying the exact original
`snapshot 30 -> snapshot 31` delta to an empty tree.

That model fails the owner's hard rule:

> if reconstructed snapshots do not match the preserved NG3 snapshot line, stop and correct
> the model rather than repairing the result heuristically.

Validation found the first mismatch at snapshot 32.

Original snapshot 32 modifies:

```text
CONTINUOUS-DEVELOPMENT.md
design/requirements-model.md
```

Those files already existed before NG3. A root containing only the four files added by
snapshot 31 would not contain them, so replaying snapshot 32 would necessarily turn
`modified` into `added`.

Therefore the empty-tree delta model is rejected.

## Correct reconstruction root

The reconstructed snapshot 31 remains the parentless root, but its tree is built from the
**full original snapshot-31 tree after deterministic removal of inherited generation
payload**.

Original snapshot 31:

```text
edeac340fab70bfe8df3a5f2a034fdf3ca7af8be
tree a53a82a582e310c399f597223281f0daf617a3a6
```

Generation payload excluded from the root:

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

The filter is path-class based and deterministic. It is not a hand-picked list of files to
make later commits pass.

## Shared baseline retained in root

Generation-independent files already present when NG3 starts are retained exactly with their
snapshot-31 bytes/modes, including:

```text
.gitignore
CHANGELOG.md
CONTINUOUS-DEVELOPMENT.md
PROJECT-CONVENTIONS.md
design/component-model.md
design/component-model-analogues.md
design/requirements-model.md
design/vpn-gateway-experiments.md
```

plus the NG3 subtree and NG3 review artifacts present in snapshot 31.

These files are part of the NG3 working baseline even though some contain historical
references/content. Their residue is an audit subject, not a reason to drop the file and
change later commit semantics.

## Replay invariant after root

After the filtered full snapshot-31 root is created, the original NG3-era commit sequence is
replayed in original order through preserved legacy snapshot 74.

For every later commit:

```text
delta(new parent -> new commit)
==
delta(original parent -> original commit)
```

including path status, mode and resulting bytes.

Meaningful inter-snapshot commits remain part of the sequence. In particular:

```text
211aefdc03a529162bb28385def6d21cc19db5aa
Process: add English AGENTS.md ...
```

between snapshots 44 and 45 must be replayed.

A transient process-review file added in snapshot 53 and removed in snapshot 54 is also
replayed exactly even though its filename does not carry the NG3 prefix. It is a real change
inside the preserved NG3-era sequence, not inherited pre-NG3 payload.

## Generation-boundary validation

The preserved NG3 commit sequence was inspected for changes to the root-excluded generation
payload classes.

No snapshot from 31 through 74 modifies:

```text
design/RC2/**
design/RC3/**
design/NG1/**
design/NG2/**
.github/workflows/rc3-python.yml
.github/workflows/ng1-python.yml
.github/workflows/ng2-python.yml
```

Therefore removing those classes once at the parentless root does not alter any later NG3
commit delta.

This is the key proof that the clean lineage can retain exact NG3-era commit semantics.

## Snapshot identity criterion

For reconstructed snapshot 31:

```text
tree(new #31)
==
filter_generation_legacy(tree(original #31))
```

For every subsequent preserved NG3-era commit through snapshot 74:

```text
delta(new commit)
==
delta(original commit)
```

The reconstruction manifest must record both the original and reconstructed identifiers and
the equality verdict. First mismatch is a hard stop.

## Current-main snapshots after legacy snapshot 74

Snapshots 75 and later were created after the repository-lineage split work started and are
not part of `legacy-main-ng3`'s preserved snapshot sequence.

They are therefore handled only after the exact 31..74 reconstruction is proven.

Their target is the completed current-main state, not retroactive alteration of the preserved
legacy NG3 sequence. No rule for replaying them is accepted by this correction review beyond
that separation of phases.

## Main safety

This correction does not create `futuremain` and does not move `main`.

The next cycle may construct `futuremain` only from this corrected root model. Current
`main` remains authoritative until a separately reviewed cutover.

## Verdict

**ACCEPT correction.**

The empty-tree root model is superseded.

The futuremain reconstruction root is the filtered full tree of original snapshot 31, with
generation-independent shared baseline retained and inherited RC/NG1/NG2 payload removed
once at the root. Exact commit-delta replay begins with the next commit after snapshot 31.
