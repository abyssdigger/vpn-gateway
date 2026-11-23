from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[6]
ARCHITECTURE = ROOT / "design/NG3/architecture-ng.md"
REQUIREMENTS = ROOT / "design/NG3/requirements.md"
TRACE = ROOT / "design/NG3/implementation-traceability.md"
PRODUCTION = ROOT / "design/NG3/code/python/rou"
DEFERRALS = ROOT / "design/deferrals"
REVIEWS = ROOT / "design/reviews"
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
        if re.match(
            r"^\*\*(?:Implements|Implements / supports|Supports implementation of):\*\*$",
            line,
        ):
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
                raise AssertionError(f"requirement edge lacks materialization status: {line}")
            result.append((match.group(1), match.group(2)))
            continue
        if not line.strip() or line.startswith("**"):
            in_edges = False
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

    def test_pending_closure_requirements_have_structured_architecture_entry(self):
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        pending = [
            str(node["id"])
            for node in requirement_nodes()
            if node["statuses"] == ("pending_closure",)
        ]
        missing = [item for item in pending if f"\x60{item}\x60" not in architecture]
        self.assertEqual([], missing)

    def test_every_postponed_requirement_has_explicit_record(self):
        record_text = "\n".join(
            path.read_text(encoding="utf-8")
            for root in (DEFERRALS, REVIEWS)
            for path in root.glob("*.md")
        )
        postponed = [
            str(node["id"])
            for node in requirement_nodes()
            if node["statuses"] == ("postponed",)
        ]
        self.assertTrue(postponed)
        missing = [item for item in postponed if f"\x60{item}\x60" not in record_text]
        self.assertEqual([], missing)

    def test_rejected_closure_requirements_have_explicit_record(self):
        record_text = "\n".join(
            path.read_text(encoding="utf-8")
            for root in (DEFERRALS, REVIEWS)
            for path in root.glob("*.md")
        )
        rejected = [
            str(node["id"])
            for node in requirement_nodes()
            if node["statuses"] == ("rejected_closure",)
        ]
        missing = [item for item in rejected if f"\x60{item}\x60" not in record_text]
        self.assertEqual([], missing)

    def test_declared_python_implementations_have_reverse_architecture_marker(self):
        declarations = declared_python_implementations()
        self.assertTrue(declarations)
        for spec_id, path in declarations:
            with self.subTest(spec=spec_id, path=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file(), f"missing implementation file: {path}")
                content = path.read_text(encoding="utf-8")
                self.assertIn("Architecture:", content)
                self.assertIn(spec_id, content)

    def test_every_production_python_unit_is_traced_or_explicit_debt(self):
        mapping, debt = trace_manifest()
        actual = {str(path.relative_to(ROOT)) for path in PRODUCTION.glob("*.py")}
        self.assertEqual(actual, set(mapping) | set(debt))
        for path, reason in debt.items():
            with self.subTest(debt=path):
                self.assertTrue(reason.strip(), "architecture debt requires an explicit reason")

    def test_closed_requirements_have_direct_or_aggregate_architecture_closure(self):
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        nodes = requirement_nodes()
        children: dict[str, list[dict[str, object]]] = {}
        for node in nodes:
            parent = node["parent"]
            if parent is not None:
                children.setdefault(str(parent), []).append(node)

        closed = [node for node in nodes if node["statuses"] == ("closed",)]
        self.assertTrue(closed)
        for node in closed:
            requirement_id = str(node["id"])
            if f"\x60{requirement_id}\x60" in architecture:
                continue
            immediate = children.get(requirement_id, [])
            with self.subTest(requirement=requirement_id):
                self.assertEqual("complete", node["decomposition"])
                self.assertTrue(immediate, "aggregate closure requires immediate children")
                self.assertTrue(
                    all(child["statuses"] == ("closed",) for child in immediate),
                    "aggregate closure requires every immediate child to be closed",
                )

    def test_every_trace_target_is_a_requirement_bearing_component_spec(self):
        mapping, _ = trace_manifest()
        specs = component_specs()
        for path, targets in mapping.items():
            for spec_id in targets:
                with self.subTest(path=path, spec=spec_id):
                    self.assertIn(spec_id, specs)
                    self.assertRegex(
                        specs[spec_id],
                        r"\*\*(?:Implements|Implements / supports|Supports implementation of):\*\*",
                    )

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
            if re.search(
                r"\*\*(?:Implements|Implements / supports|Supports implementation of):\*\*",
                body,
            ):
                with self.subTest(spec=spec_id):
                    self.assertTrue(component_requirement_edges(body))

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
