from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.registry import load_app_modules

from core.kernel.app.app_manifest import AppManifest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]

_REQUIRED_PERMISSION_PATTERN = re.compile(r'requiredPermission:\s*"([^"]+)"')
_HAS_USER_PERMISSION_PATTERN = re.compile(r'hasUserPermission\(\s*[^,]+,\s*"([^"]+)"\s*\)')


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _collect_frontend_required_permissions() -> set[str]:
    root = _repo_root()
    targets = [
        *list((root / "frontend" / "src").rglob("*.ts")),
        *list((root / "frontend" / "src").rglob("*.tsx")),
        *list((root / "backend" / "apps").rglob("web/module.tsx")),
    ]
    permissions: set[str] = set()
    for file_path in targets:
        content = file_path.read_text(encoding="utf-8")
        permissions.update(match.strip() for match in _REQUIRED_PERMISSION_PATTERN.findall(content) if match.strip())
        permissions.update(match.strip() for match in _HAS_USER_PERMISSION_PATTERN.findall(content) if match.strip())
    return permissions


def _collect_backend_known_permissions() -> set[str]:
    manifest = AppManifest.init_app().add_modules(
        load_app_modules(),
    )
    return set(manifest.permissions)


def test_frontend_required_permissions_are_registered_on_backend_manifest() -> None:
    frontend_permissions = _collect_frontend_required_permissions()
    backend_permissions = _collect_backend_known_permissions()

    unknown_permissions = sorted(permission for permission in frontend_permissions if permission not in backend_permissions)
    assert not unknown_permissions, (
        "A frontend olyan jogosultságot hivatkozik, ami nincs regisztrálva a backend manifestben: "
        + ", ".join(unknown_permissions)
    )
