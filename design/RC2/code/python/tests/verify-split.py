#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


def top_level_defs(tree: ast.Module):
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def simple_assignments(tree: ast.Module):
    result = {}
    for node in tree.body:
        name = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            name = node.target.id
            value = node.value
        if name is not None:
            result[name] = ast.dump(value, include_attributes=False)
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify-split.py MONOLITH PACKAGE_DIR", file=sys.stderr)
        return 2

    monolith = Path(sys.argv[1])
    package_dir = Path(sys.argv[2])
    source_tree = ast.parse(monolith.read_text(encoding="utf-8"), filename=str(monolith))

    split_trees = []
    for path in sorted(package_dir.glob("*.py")):
        if path.name in {"__init__.py", "__main__.py"}:
            continue
        split_trees.append((path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))))

    source_defs = top_level_defs(source_tree)
    split_defs = {}
    owners = {}
    for path, tree in split_trees:
        for name, dump in top_level_defs(tree).items():
            if name in split_defs:
                raise SystemExit(f"duplicate top-level definition {name}: {owners[name]} and {path}")
            split_defs[name] = dump
            owners[name] = path

    if source_defs.keys() != split_defs.keys():
        missing = sorted(source_defs.keys() - split_defs.keys())
        extra = sorted(split_defs.keys() - source_defs.keys())
        raise SystemExit(f"definition set differs: missing={missing!r}, extra={extra!r}")

    changed = [name for name in sorted(source_defs) if source_defs[name] != split_defs[name]]
    if changed:
        raise SystemExit(f"AST differs for definitions: {changed!r}")

    source_assign = simple_assignments(source_tree)
    split_assign = {}
    for path, tree in split_trees:
        for name, dump in simple_assignments(tree).items():
            if name in split_assign:
                raise SystemExit(f"duplicate assignment {name!r} in split package")
            split_assign[name] = dump

    missing_assign = sorted(source_assign.keys() - split_assign.keys())
    changed_assign = sorted(
        name for name in source_assign.keys() & split_assign.keys()
        if source_assign[name] != split_assign[name]
    )
    if missing_assign or changed_assign:
        raise SystemExit(
            f"top-level assignments differ: missing={missing_assign!r}, changed={changed_assign!r}"
        )

    print(
        f"split convergence PASS: {len(source_defs)} definitions; "
        f"{len(source_assign)} top-level assignments"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
