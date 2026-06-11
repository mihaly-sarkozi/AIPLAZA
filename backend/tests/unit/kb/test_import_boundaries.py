from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "apps" / "kb"

KB_MODULES = (
    "kb_crud",
    "kb_ingest",
)

FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "kb_crud": set(KB_MODULES) - {"kb_crud"},
    "kb_ingest": set(KB_MODULES) - {"kb_ingest"},
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
