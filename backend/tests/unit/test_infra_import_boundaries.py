from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.architecture, pytest.mark.must_pass]

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and ".venv" not in path.parts and "venv" not in path.parts
    ]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_infra_does_not_import_app_service_router_or_use_case_layers() -> None:
    forbidden_fragments = (".service", ".router", ".application", ".bootstrap", ".web")
    violations: list[str] = []
    for path in _python_files(BACKEND_ROOT / "infra"):
        for imported in _imports(path):
            if not imported.startswith("apps."):
                continue
            if any(fragment in imported for fragment in forbidden_fragments):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []


def test_app_domain_and_service_do_not_import_concrete_infra_adapters() -> None:
    allowed_port_imports = {"infra.storage.object_storage"}
    forbidden_prefixes = (
        "infra.ai",
        "infra.audit",
        "infra.cache",
        "infra.db",
        "infra.email",
        "infra.persistence",
        "infra.security",
        "infra.vector",
    )
    violations: list[str] = []
    for app_root in (BACKEND_ROOT / "apps").iterdir():
        for layer in ("domain", "service"):
            root = app_root / layer
            if not root.exists():
                continue
            for path in _python_files(root):
                for imported in _imports(path):
                    if imported in allowed_port_imports:
                        continue
                    if imported.startswith(forbidden_prefixes):
                        violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []


def test_core_does_not_import_apps_layer() -> None:
    violations: list[str] = []
    for path in _python_files(BACKEND_ROOT / "core"):
        for imported in _imports(path):
            if imported.startswith("apps."):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []


def test_apps_do_not_import_removed_knowledge_modules() -> None:
    """A törölt apps.knowledge / apps.knowledge_engine modulokra nem maradhat hivatkozás."""
    forbidden_prefixes = ("apps.knowledge", "apps.knowledge_engine")
    violations: list[str] = []
    for root in (BACKEND_ROOT / "apps", BACKEND_ROOT / "core", BACKEND_ROOT / "infra", BACKEND_ROOT / "shared"):
        if not root.exists():
            continue
        for path in _python_files(root):
            for imported in _imports(path):
                if imported.startswith(forbidden_prefixes):
                    violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")

    assert violations == []
