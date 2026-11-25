from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[6]
ARCHITECTURE = ROOT / "design/NG3/architecture-ng.md"
REQUIREMENTS = ROOT / "design/NG3/requirements.md"
PROJECT_CONVENTIONS = ROOT / "PROJECT-CONVENTIONS.md"
TRACE = ROOT / "design/NG3/implementation-traceability.md"
EVIDENCE_INDEX = ROOT / "design/NG3/evidence-index.md"
REFERENCE_IMPLEMENTATION = ROOT / "design/NG3/code/python/rou"
STATUS_BASIS = ROOT / "design/NG3/requirement-status-basis.md"
REQUIREMENT_STATUSES = (
    "open",
    "pending_closure",
    "closed",
    "rejected_closure",
    "postponed",
    "permanent",
)
MATERIALIZATION_STATUSES = ("full", "partial", "none")


def requirement_nodes() -> tuple[dict[str, object], ...]:
    result: list[dict[str, object]] = []
    stack: list[dict[str, object]] = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"^(\s*)-\s+\*\*\[(VPNG[^\]]+)\]\*\*.*"
            r"\[\x60decomposition\x60:\s*\x60(complete|incomplete)\x60\]",
            line,
        )
        if not match:
            continue
        indent, requirement_id, decomposition = match.groups()
        level = len(indent) // 4
        statuses = [
            status
            for status in REQUIREMENT_STATUSES
            if f"[\x60{status}\x60]" in line
        ]
        while len(stack) > level:
            stack.pop()
        parent = stack[level - 1]["id"] if level else None
        node: dict[str, object] = {
            "id": requirement_id,
            "kind": (
                "constraint"
                if re.search(r"\.C\d+$", requirement_id)
                else "requirement"
            ),
            "decomposition": decomposition,
            "statuses": tuple(statuses),
            "parent": parent,
        }
        result.append(node)
        if len(stack) == level:
            stack.append(node)
        else:
            stack[level] = node
            del stack[level + 1 :]
    return tuple(result)


def external_status_basis() -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for line in STATUS_BASIS.read_text(encoding="utf-8").splitlines():
        status_match = re.search(r"\| статус \x60([a-z_]+)\x60 \|", line)
        path_match = re.search(r"\| \x60([^\x60]+\.md)\x60 \|$", line)
        if status_match is None or path_match is None:
            continue
        status = status_match.group(1)
        path = path_match.group(1)
        requirement_ids = re.findall(r"\x60(VPNG-[^\x60]+)\x60", line)
        if not requirement_ids:
            raise AssertionError(f"external status basis row has no requirement IDs: {line}")
        for requirement_id in requirement_ids:
            key = (status, requirement_id)
            if key in result:
                raise AssertionError(f"duplicate external status basis: {key}")
            result[key] = path
    return result


def annex_text() -> str:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    marker = "# Annex A. STACK components"
    if marker not in text:
        raise AssertionError("canonical Annex A marker missing")
    return text[text.index(marker):]


def declared_python_implementations() -> tuple[tuple[str, Path], ...]:
    lines = annex_text().splitlines()
    current_spec = None
    in_implementation = False
    result = []
    for line in lines:
        heading = re.match(r"^## \[([A-G]\.\d{3})\]\s+", line)
        if heading:
            current_spec = heading.group(1)
            in_implementation = False
            continue
        if line == "Implementation":
            if current_spec is None:
                raise AssertionError("Implementation block outside component spec")
            in_implementation = True
            continue
        if in_implementation:
            if line.startswith("#") or (line and not line.startswith("    ")):
                in_implementation = False
                continue
            match = re.match(r"^\s{4}(design/\S+\.py)(?:\s|$)", line)
            if match:
                result.append((current_spec, ROOT / match.group(1)))
    return tuple(result)


def trace_manifest() -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    mapping: dict[str, tuple[str, ...]] = {}
    debt: dict[str, str] = {}
    current_specs: tuple[str, ...] | None = None
    in_debt = False
    for line in TRACE.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^## Trace: (.+)$", line)
        if heading:
            current_specs = tuple(re.findall(r"\x60([A-G]\.\d{3})\x60", heading.group(1)))
            if not current_specs:
                raise AssertionError(f"trace heading has no specs: {line}")
            in_debt = False
            continue
        if line == "## Architecture debt":
            current_specs = None
            in_debt = True
            continue
        item = re.match(r"^- \x60(design/NG3/code/python/rou/[^\x60]+\.py)\x60(?: — (.*))?$", line)
        if not item:
            continue
        path, reason = item.groups()
        if path in mapping or path in debt:
            raise AssertionError(f"duplicate trace entry: {path}")
        if in_debt:
            debt[path] = reason or ""
        elif current_specs is not None:
            mapping[path] = current_specs
        else:
            raise AssertionError(f"trace item outside section: {line}")
    return mapping, debt


def component_specs() -> dict[str, str]:
    text = annex_text()
    matches = list(
        re.finditer(r"^## \[([A-G]\.\d{3})\]\s+.+$", text, re.MULTILINE)
    )
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        spec_id = match.group(1)
        if spec_id in result:
            raise AssertionError(f"duplicate canonical component spec: {spec_id}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[spec_id] = text[match.start():end]
    return result


def component_requirement_edges(body: str) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    in_edges = False
    for line in body.splitlines():
        if line == "**Implements:**":
            in_edges = True
            continue
        if not in_edges:
            continue
        if line.startswith("- \x60VPNG-"):
            match = re.match(
                r"^- \x60(VPNG-[^\x60]+)\x60 — \[\x60(full|partial|none)\x60\]$",
                line,
            )
            if match is None:
                raise AssertionError(
                    f"requirement edge lacks materialization status: {line}"
                )
            result.append((match.group(1), match.group(2)))
            continue
        if not line.strip() or line.startswith("**"):
            in_edges = False
    return tuple(result)


def component_constraint_edges(body: str) -> tuple[str, ...]:
    result: list[str] = []
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("**Constrained by:**"):
            continue
        result.extend(re.findall(r"\x60(VPNG-[^\x60]+)\x60", line))
        if line.strip() != "**Constrained by:**":
            continue
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].startswith("- \x60VPNG-"):
            match = re.fullmatch(
                r"- \x60(VPNG-[^\x60]+)\x60",
                lines[cursor],
            )
            if match is None:
                raise AssertionError(
                    f"constraint edge has non-canonical form: {lines[cursor]}"
                )
            result.append(match.group(1))
            cursor += 1
    return tuple(result)


def explicit_coverage_index_ids() -> frozenset[str]:
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    start = architecture.index(
        "## 2.10. Closed requirement architecture coverage index"
    )
    end = architecture.index("\n## 3.", start)
    section = architecture[start:end]
    result: set[str] = set()
    in_requirements = False
    for line in section.splitlines():
        if line.startswith("**Coverage nodes:**"):
            in_requirements = True
            result.update(
                re.findall(r"\x60(VPNG-[^\x60]+)\x60", line)
            )
            continue
        if not in_requirements:
            continue
        if not line.strip():
            in_requirements = False
            continue
        result.update(re.findall(r"\x60(VPNG-[^\x60]+)\x60", line))
    return frozenset(result)


def explicit_architecture_coverage_ids() -> frozenset[str]:
    result: set[str] = set(explicit_coverage_index_ids())
    for body in component_specs().values():
        result.update(item[0] for item in component_requirement_edges(body))
        result.update(component_constraint_edges(body))

    return frozenset(result)


def architecture_evidence_ids() -> tuple[str, ...]:
    lines = ARCHITECTURE.read_text(encoding="utf-8").splitlines()
    result: list[str] = []
    for index, line in enumerate(lines):
        if not line.startswith("**Evidence:**"):
            continue
        payload = line.removeprefix("**Evidence:**").strip()
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].strip():
            if lines[cursor].startswith("**") or lines[cursor].startswith("#"):
                break
            payload += " " + lines[cursor].strip()
            cursor += 1
        ids = re.findall(r"\x60(EV-\d{5})\x60", payload)
        remainder = re.sub(r"\x60EV-\d{5}\x60", "", payload)
        remainder = remainder.translate(str.maketrans("", "", " ,.;"))
        if remainder.strip():
            raise AssertionError(
                "stable architecture Evidence field contains non-EV content: "
                + payload
            )
        if not ids:
            raise AssertionError(
                "stable architecture Evidence field has no stable EV address"
            )
        result.extend(ids)
    return tuple(result)


def component_name(body: str) -> str:
    heading = re.match(r"^## \[[A-G]\.\d{3}\]\s+([^\n]+)", body)
    if heading is None:
        raise AssertionError("component spec has no canonical heading")
    return heading.group(1).strip()


class StructuredArchitectureTraceabilityTests(unittest.TestCase):
    def test_every_requirement_has_exactly_one_status(self):
        nodes = requirement_nodes()
        self.assertTrue(nodes)
        for node in nodes:
            with self.subTest(requirement=node["id"]):
                self.assertEqual(
                    1,
                    len(node["statuses"]),
                    f"requirement must have exactly one status, found {node['statuses']}",
                )

    def test_current_governing_docs_have_no_stale_cycle_or_release_identity(self):
        requirements = REQUIREMENTS.read_text(encoding="utf-8")
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertNotIn("**Cycle:**", requirements)
        self.assertNotIn("design-cycle draft", requirements)
        self.assertIsNone(
            re.search(
                r"\bRelease-\d+\s*/\s*\d+\.\d+\.\d+\b",
                architecture,
            )
        )
        self.assertIsNone(
            re.search(r"\brelease/\d+\.\d+\.\d+/", architecture)
        )

    def test_release_methodology_is_scope_driven_not_technology_specific(self):
        conventions = PROJECT_CONVENTIONS.read_text(encoding="utf-8")
        start = conventions.index(
            "### 10.4. QA и предрелизная проверка фактического исполнения"
        )
        end = conventions.index("\n### 10.5.", start)
        methodology = conventions[start:end]
        for technology in ("WireGuard", "OpenConnect", "L2TP"):
            with self.subTest(technology=technology):
                self.assertNotIn(technology, methodology)
        self.assertIn("release/<version>/RELEASE-SCOPE.md", methodology)

    def test_projectholder_term_is_canonical_in_current_governing_docs(self):
        text = (
            PROJECT_CONVENTIONS.read_text(encoding="utf-8")
            + "\n"
            + REQUIREMENTS.read_text(encoding="utf-8")
        )
        self.assertIsNone(re.search(r"\bproject holder\b", text, re.IGNORECASE))
        self.assertIsNone(re.search(r"\bproject-holder\b", text, re.IGNORECASE))
        self.assertNotIn("владелец разработки", text.lower())

    def test_stable_architecture_uses_only_stable_evidence_addresses(self):
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(r"\bEXP-\d+\b", architecture),
            "stable architecture must reference experiment evidence only through EV IDs",
        )
        ids = architecture_evidence_ids()
        self.assertTrue(ids)
        registered = set(
            re.findall(
                r"^## (EV-\d{5}) \u2014 ",
                EVIDENCE_INDEX.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )
        self.assertTrue(registered)
        self.assertEqual(set(), set(ids) - registered)

    def test_pending_closure_requirements_have_structured_architecture_entry(self):
        pending = [
            str(node["id"])
            for node in requirement_nodes()
            if node["statuses"] == ("pending_closure",)
        ]
        direct = explicit_architecture_coverage_ids()
        missing = [item for item in pending if item not in direct]
        self.assertEqual([], missing)

    def test_external_requirement_status_basis_is_explicit(self):
        requirements_text = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertIn(
            "\x60design/NG3/requirement-status-basis.md\x60",
            requirements_text,
        )
        basis = external_status_basis()

        for status in ("postponed", "rejected_closure"):
            expected = {
                str(node["id"])
                for node in requirement_nodes()
                if node["statuses"] == (status,)
            }
            actual = {
                requirement_id
                for basis_status, requirement_id in basis
                if basis_status == status
            }
            self.assertEqual(expected, actual, status)

            for requirement_id in sorted(expected):
                path = ROOT / basis[(status, requirement_id)]
                with self.subTest(status=status, requirement=requirement_id):
                    self.assertTrue(path.is_file(), f"missing basis document: {path}")
                    content = path.read_text(encoding="utf-8")
                    self.assertIn(f"\x60{requirement_id}\x60", content)

    def test_declared_python_implementations_have_reverse_architecture_marker(self):
        declarations = declared_python_implementations()
        self.assertTrue(declarations)
        for spec_id, path in declarations:
            with self.subTest(spec=spec_id, path=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file(), f"missing implementation file: {path}")
                content = path.read_text(encoding="utf-8")
                self.assertIn("Architecture:", content)
                self.assertIn(spec_id, content)

    def test_every_reference_python_unit_is_traced_or_explicit_debt(self):
        mapping, debt = trace_manifest()
        actual = {
            str(path.relative_to(ROOT))
            for path in REFERENCE_IMPLEMENTATION.glob("*.py")
        }
        self.assertEqual(actual, set(mapping) | set(debt))
        for path, reason in debt.items():
            with self.subTest(debt=path):
                self.assertTrue(
                    reason.strip(),
                    "architecture debt requires an explicit reason",
                )

    def test_closed_requirements_have_direct_or_aggregate_architecture_closure(self):
        nodes = requirement_nodes()
        by_id = {str(node["id"]): node for node in nodes}
        children: dict[str, list[str]] = {}
        for node in nodes:
            parent = node["parent"]
            if parent is not None:
                children.setdefault(str(parent), []).append(str(node["id"]))

        direct = explicit_architecture_coverage_ids()
        self.assertEqual(set(), direct - set(by_id))
        cache: dict[str, bool] = {}

        def covered(requirement_id: str) -> bool:
            if requirement_id in cache:
                return cache[requirement_id]
            if requirement_id in direct:
                cache[requirement_id] = True
                return True
            node = by_id[requirement_id]
            immediate = children.get(requirement_id, [])
            value = (
                node["decomposition"] == "complete"
                and bool(immediate)
                and all(covered(child_id) for child_id in immediate)
            )
            cache[requirement_id] = value
            return value

        closed = [node for node in nodes if node["statuses"] == ("closed",)]
        self.assertTrue(closed)
        for node in closed:
            requirement_id = str(node["id"])
            with self.subTest(requirement=requirement_id):
                self.assertTrue(
                    covered(requirement_id),
                    "closed node lacks structured direct coverage "
                    "or complete-child aggregation",
                )

    def test_every_trace_target_is_a_requirement_bearing_component_spec(self):
        mapping, _ = trace_manifest()
        specs = component_specs()
        for path, targets in mapping.items():
            for spec_id in targets:
                with self.subTest(path=path, spec=spec_id):
                    self.assertIn(spec_id, specs)
                    self.assertIn("**Implements:**", specs[spec_id])

    def test_component_ids_are_unique_and_match_annex(self):
        text = annex_text()
        current_annex = None
        seen: set[str] = set()
        for line in text.splitlines():
            annex = re.match(r"^# Annex ([A-G])\.", line)
            if annex:
                current_annex = annex.group(1)
                continue
            heading = re.match(r"^## \[([A-G]\.\d{3})\]\s+", line)
            if heading:
                spec_id = heading.group(1)
                self.assertNotIn(spec_id, seen)
                seen.add(spec_id)
                self.assertIsNotNone(current_annex)
                self.assertEqual(current_annex, spec_id[0])
        self.assertEqual(set(component_specs()), seen)

    def test_every_requirement_edge_has_materialization_status(self):
        specs = component_specs()
        self.assertTrue(specs)
        for spec_id, body in specs.items():
            if "**Implements:**" in body:
                with self.subTest(spec=spec_id):
                    self.assertTrue(component_requirement_edges(body))

    def test_coverage_index_uses_neutral_node_label(self):
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertNotIn("**Covers:**", architecture)
        start = architecture.index(
            "## 2.10. Closed requirement architecture coverage index"
        )
        end = architecture.index("\n## 3.", start)
        section = architecture[start:end]
        self.assertNotIn("**Requirements:**", section)
        self.assertIn("**Coverage nodes:**", section)

    def test_component_edges_are_typed_requirement_vs_constraint(self):
        nodes = {str(node["id"]): node for node in requirement_nodes()}
        for spec_id, body in component_specs().items():
            self.assertNotIn("**Implements / supports:**", body)
            self.assertNotIn("**Supports implementation of:**", body)
            for requirement_id, _ in component_requirement_edges(body):
                with self.subTest(spec=spec_id, implements=requirement_id):
                    self.assertIn(requirement_id, nodes)
                    self.assertEqual(
                        "requirement",
                        nodes[requirement_id]["kind"],
                    )
            for constraint_id in component_constraint_edges(body):
                with self.subTest(spec=spec_id, constrained_by=constraint_id):
                    self.assertIn(constraint_id, nodes)
                    self.assertEqual(
                        "constraint",
                        nodes[constraint_id]["kind"],
                    )

    def test_non_full_requirement_edges_explain_the_gap(self):
        for spec_id, body in component_specs().items():
            edges = component_requirement_edges(body)
            non_full = [edge for edge in edges if edge[1] != "full"]
            if non_full:
                with self.subTest(spec=spec_id):
                    self.assertRegex(
                        body,
                        r"\*\*Пробел(?:ы)? материализации:\*\*",
                    )

    def test_component_local_implementation_edges_are_in_full_manifest(self):
        mapping, _ = trace_manifest()
        for spec_id, path in declared_python_implementations():
            rel = str(path.relative_to(ROOT))
            with self.subTest(spec=spec_id, path=rel):
                self.assertIn(rel, mapping)
                self.assertIn(spec_id, mapping[rel])

    def test_every_materialized_component_has_code_trace(self):
        mapping, _ = trace_manifest()
        reverse: dict[str, set[str]] = {}
        for path, targets in mapping.items():
            for spec_id in targets:
                reverse.setdefault(spec_id, set()).add(path)
        for spec_id, body in component_specs().items():
            edges = component_requirement_edges(body)
            if any(status in {"full", "partial"} for _, status in edges):
                with self.subTest(spec=spec_id):
                    self.assertIn(spec_id, reverse)
                    self.assertTrue(reverse[spec_id])


if __name__ == "__main__":
    unittest.main()
