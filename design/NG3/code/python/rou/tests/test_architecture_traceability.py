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


def declared_python_implementations() -> tuple[tuple[str, Path], ...]:
    lines = ARCHITECTURE.read_text(encoding="utf-8").splitlines()
    current_spec = None
    in_implementation = False
    result = []
    for line in lines:
        heading = re.match(r"^## ([A-G]\.\d{3})\s+", line)
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
    text = ARCHITECTURE.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^## ([A-G]\.\d{3})\s+.+$", text, re.MULTILINE))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1)] = text[match.start():end]
    return result


class StructuredArchitectureTraceabilityTests(unittest.TestCase):
    def test_every_requirement_has_exactly_one_status(self):
        nodes = []
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*-\s+\*\*\[(VPNG[^\]]+)\]\*\*", line)
            if not match:
                continue
            statuses = [
                status
                for status in REQUIREMENT_STATUSES
                if f"[\x60{status}\x60]" in line
            ]
            nodes.append(match.group(1))
            with self.subTest(requirement=match.group(1)):
                self.assertEqual(
                    1,
                    len(statuses),
                    f"requirement must have exactly one status, found {statuses}",
                )
        self.assertTrue(nodes)

    def test_every_postponed_requirement_has_explicit_record(self):
        record_text = "\n".join(
            path.read_text(encoding="utf-8")
            for root in (DEFERRALS, REVIEWS)
            for path in root.glob("*.md")
        )
        postponed = []
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            match = re.match(
                r"^\s*-\s+\*\*\[(VPNG[^\]]+)\]\*\*.*\[\x60postponed\x60\]\s*$",
                line,
            )
            if match:
                postponed.append(match.group(1))
        self.assertTrue(postponed)
        missing = [item for item in postponed if f"\x60{item}\x60" not in record_text]
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

    def test_every_closed_requirement_has_structured_architecture_entry(self):
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        closed = []
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            match = re.match(
                r"^\s*-\s+\*\*\[(VPNG[^\]]+)\]\*\*.*\[\x60closed\x60\]\s*$",
                line,
            )
            if match:
                closed.append(match.group(1))
        self.assertTrue(closed)
        missing = [item for item in closed if f"\x60{item}\x60" not in architecture]
        self.assertEqual([], missing)

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

    def test_every_requirement_bearing_materialized_component_has_code_trace(self):
        mapping, _ = trace_manifest()
        reverse: dict[str, set[str]] = {}
        for path, targets in mapping.items():
            for spec_id in targets:
                reverse.setdefault(spec_id, set()).add(path)
        for spec_id, body in component_specs().items():
            if re.search(
                r"\*\*(?:Implements|Implements / supports|Supports implementation of):\*\*",
                body,
            ):
                with self.subTest(spec=spec_id):
                    self.assertIn(spec_id, reverse)
                    self.assertTrue(reverse[spec_id])


if __name__ == "__main__":
    unittest.main()
