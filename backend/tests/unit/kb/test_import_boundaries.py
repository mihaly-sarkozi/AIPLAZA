from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "apps" / "kb"

KB_MODULES = (
    "kb_crud",
    "kb_reading",
    "kb_training",
    "kb_understanding",
    "kb_search",
    "kb_testing",
    "kb_feedback",
    "kb_maintenance",
)

FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "kb_crud": set(KB_MODULES) - {"kb_crud"},
    "kb_reading": set(KB_MODULES) - {"kb_reading"},
    "kb_training": set(KB_MODULES) - {"kb_training"},
    "kb_understanding": set(KB_MODULES) - {"kb_understanding"},
    "kb_search": set(KB_MODULES) - {"kb_search"},
    "kb_testing": set(KB_MODULES) - {"kb_testing", "kb_search"},
    "kb_feedback": set(KB_MODULES) - {"kb_feedback"},
    "kb_maintenance": set(KB_MODULES) - {"kb_maintenance", "kb_understanding"},
    "shared": set(KB_MODULES),
}


def _module_py_files(module_name: str) -> list[Path]:
    base = ROOT / module_name
    if not base.is_dir():
        return []
    return [path for path in base.rglob("*.py") if path.name != "__init__.py"]


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("apps.kb."):
                    found.add(alias.name.split(".")[2])
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("apps.kb."):
            parts = node.module.split(".")
            if len(parts) >= 3:
                found.add(parts[2])
    return found


def test_kb_modules_do_not_forbid_cross_import() -> None:
    for module_name, forbidden in FORBIDDEN_IMPORTS.items():
        for path in _module_py_files(module_name):
            imports = _imports_in_file(path)
            assert not (imports & forbidden), f"{path.relative_to(ROOT)} imports forbidden: {imports & forbidden}"


def test_shared_does_not_import_kb_modules() -> None:
    for path in _module_py_files("shared"):
        imports = _imports_in_file(path)
        assert not imports, f"shared must not import kb modules: {path} -> {imports}"
