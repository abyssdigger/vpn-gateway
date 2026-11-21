from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[6]
STRUCTURED = ROOT / "design/NG3/structured-architecture.md"


def declared_python_implementations() -> tuple[tuple[str, Path], ...]:
    lines = STRUCTURED.read_text(encoding="utf-8").splitlines()
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
            if line.startswith("#") or (
                line and not line.startswith("    ")
            ):
                in_implementation = False
                continue
            match = re.match(r"^\s{4}(design/\S+\.py)(?:\s|$)", line)
            if match:
                result.append((current_spec, ROOT / match.group(1)))

    return tuple(result)


class StructuredArchitectureTraceabilityTests(unittest.TestCase):
    def test_declared_python_implementations_have_reverse_architecture_marker(self):
        declarations = declared_python_implementations()
        self.assertTrue(declarations)

        for spec_id, path in declarations:
            with self.subTest(spec=spec_id, path=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file(), f"missing implementation file: {path}")
                content = path.read_text(encoding="utf-8")
                self.assertIn("Architecture:", content)
                self.assertIn(
                    spec_id,
                    content,
                    f"{path} does not point back to structured spec {spec_id}",
                )


if __name__ == "__main__":
    unittest.main()
