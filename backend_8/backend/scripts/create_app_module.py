from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent.parent
APPS_ROOT = BACKEND_ROOT / "apps"
TEMPLATE_ROOT = BACKEND_ROOT / "scaffolding"
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _module_class_name(module_name: str) -> str:
    return "".join(part.capitalize() for part in module_name.split("_"))


def _validate_module_name(module_name: str) -> str:
    normalized = module_name.strip().lower().replace("-", "_")
    if not NAME_PATTERN.match(normalized):
        raise SystemExit(
            "Érvénytelen modulnév. Használj kisbetűt, számot és aláhúzást, "
            "és betűvel kezdődjön."
        )
    if normalized in {"contracts", "template"}:
        raise SystemExit(f"Fenntartott modulnév: {normalized}")
    return normalized


def _render_text(source: str, module_name: str) -> str:
    class_name = _module_class_name(module_name)
    return (
        source.replace("template", module_name)
        .replace("Template", class_name)
        .replace("TEMPLATE", module_name.upper())
    )


def _target_relative_path(relative_path: Path, module_name: str) -> Path:
    rendered_parts = [
        _render_text(part, module_name)
        for part in relative_path.parts
    ]
    return Path(*rendered_parts)


def scaffold_module(module_name: str) -> list[Path]:
    module_name = _validate_module_name(module_name)
    target_root = APPS_ROOT / module_name
    if target_root.exists():
        raise SystemExit(f"A célmappa már létezik: {target_root}")
    if not TEMPLATE_ROOT.exists():
        raise SystemExit(f"Hiányzik a template mappa: {TEMPLATE_ROOT}")

    created: list[Path] = []
    for source_path in sorted(TEMPLATE_ROOT.rglob("*")):
        if "__pycache__" in source_path.parts:
            continue
        if source_path.name == "README.md":
            continue
        relative_path = source_path.relative_to(TEMPLATE_ROOT)
        target_path = target_root / _target_relative_path(relative_path, module_name)

        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = _render_text(source_path.read_text(encoding="utf-8"), module_name)
        target_path.write_text(rendered, encoding="utf-8")
        created.append(target_path)
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a new backend app module from scaffolding.",
    )
    parser.add_argument("module_name", help="Új modul neve, például `notifications`.")
    args = parser.parse_args(argv)

    created = scaffold_module(args.module_name)
    print(f"Létrehozott modul: apps/{args.module_name}")
    for path in created:
        print(f"- {path.relative_to(BACKEND_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
