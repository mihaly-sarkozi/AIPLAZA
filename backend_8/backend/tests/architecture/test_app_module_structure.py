from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.kernel.interface.app_conventions import APP_MODULE_REQUIRED_PATHS
from core.kernel.interface.public_api import APP_PLATFORM_SUPPORT_DIRECTORIES
from tests.architecture._helpers import (
    APPS_ROOT,
    format_violations,
    iter_direct_child_directories,
    parse_python_file,
)

pytestmark = [pytest.mark.architecture, pytest.mark.must_pass]


def _feature_app_directories() -> list[Path]:
    directories: list[Path] = []
    for path in iter_direct_child_directories(APPS_ROOT):
        if path.name.startswith("__"):
            continue
        if path.name in APP_PLATFORM_SUPPORT_DIRECTORIES:
            continue
        directories.append(path)
    return directories


def _module_interface_errors(module_path: Path) -> list[str]:
    _, tree = parse_python_file(module_path)

    has_app_module_subclass = False
    has_get_module = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseAppModule":
                    has_app_module_subclass = True
                elif isinstance(base, ast.Attribute) and base.attr == "BaseAppModule":
                    has_app_module_subclass = True
        elif isinstance(node, ast.FunctionDef) and node.name == "get_module":
            has_get_module = True

    errors: list[str] = []
    if not has_app_module_subclass:
        errors.append("nem definiál `BaseAppModule` leszármazottat")
    if not has_get_module:
        errors.append("hiányzik a `get_module()` entrypoint")
    return errors


def test_each_app_directory_has_required_entrypoints() -> None:
    violations: list[str] = []

    for app_dir in _feature_app_directories():
        for relative_path in APP_MODULE_REQUIRED_PATHS:
            if not (app_dir / relative_path).exists():
                violations.append(
                    f"{app_dir.relative_to(APPS_ROOT.parent)} hiányzó kötelező útvonal: `{relative_path}`"
                )

    assert not violations, format_violations(
        rule="Architektúra-szabály sérült: minden app modulnak kötelező backend entrypointtal kell rendelkeznie.",
        guidance="Adj az apphoz legalább `module.py` és `web/module.tsx` fájlt az egységes modulplatform szerint.",
        violations=violations,
    )


def test_each_app_module_exposes_standard_module_interface() -> None:
    violations: list[str] = []

    for app_dir in _feature_app_directories():
        module_path = app_dir / "module.py"
        if not module_path.exists():
            violations.append(f"{module_path.relative_to(APPS_ROOT.parent)} hiányzó `module.py`")
            continue
        for error in _module_interface_errors(module_path):
            violations.append(f"{module_path.relative_to(APPS_ROOT.parent)} {error}")

    assert not violations, format_violations(
        rule="Architektúra-szabály sérült: az app `module.py` fájloknak egységes BaseAppModule interface-t kell követniük.",
        guidance="A `module.py` definiáljon egy `BaseAppModule` leszármazottat és egy `get_module()` függvényt.",
        violations=violations,
    )


def test_template_matches_the_same_module_interface() -> None:
    template_dir = APPS_ROOT.parent / "scaffolding"
    violations: list[str] = []

    for relative_path in APP_MODULE_REQUIRED_PATHS:
        if not (template_dir / relative_path).exists():
            violations.append(
                f"{template_dir.relative_to(APPS_ROOT.parent)} hiányzó template útvonal: `{relative_path}`"
            )

    template_module_path = template_dir / "module.py"
    if template_module_path.exists():
        for error in _module_interface_errors(template_module_path):
            violations.append(f"{template_module_path.relative_to(APPS_ROOT.parent)} {error}")

    assert not violations, format_violations(
        rule="Architektúra-szabály sérült: az app template nem követi a valós app-modul interface-t.",
        guidance="A `scaffolding` ugyanazt a `module.py` és `web/module.tsx` szerkezetet kövesse, mint a valódi appok.",
        violations=violations,
    )
