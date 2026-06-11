from __future__ import annotations

import ast
from pathlib import Path

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction


_SERVICE_FILES = [
    Path("core/modules/auth/use_cases/login_service.py"),
    Path("core/modules/auth/use_cases/refresh_service.py"),
    Path("core/modules/auth/use_cases/logout_service.py"),
    Path("core/modules/users/service/user_service.py"),
    Path("core/modules/users/service/invite_service.py"),
    Path("core/modules/users/service/profile_service.py"),
    Path("core/modules/settings/service/settings_service.py"),
    Path("core/modules/brand/service/brand_service.py"),
    Path("admin/router/admin_router.py"),
    Path("apps/kb/kb_crud/service/KbCrudAuditLogger.py"),
    Path("core/modules/tenant/signup/new_demo_signup.py"),
]


def _collect_audit_action_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        action_expr = None

        # Közvetlen audit.log(AuditLogAction.X, ...) vagy belső self._log(AuditLogAction.X, ...)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"log", "_log"}:
            action_expr = node.args[0] if node.args else None
            if isinstance(action_expr, ast.Name):
                # Wrapper függvény belső továbbadása (pl. audit.log(action, ...)) itt nem ellenőrizhető.
                continue

        # Wrapper hívás: _audit_log(audit, AuditLogAction.X, ...)
        elif isinstance(node.func, ast.Name) and node.func.id == "_audit_log":
            action_expr = node.args[1] if len(node.args) > 1 else None
        else:
            continue

        assert action_expr is not None, f"Audit action missing in {path}"
        assert isinstance(action_expr, ast.Attribute), f"Audit action must be enum member in {path}"
        assert isinstance(action_expr.value, ast.Name), f"Audit action owner must be named in {path}"
        assert action_expr.value.id == "AuditLogAction", f"Audit action must use AuditLogAction in {path}"
        names.add(action_expr.attr)

    return names


def test_audit_log_calls_use_only_audit_action_enum_members():
    used_names: set[str] = set()
    for rel_path in _SERVICE_FILES:
        used_names.update(_collect_audit_action_names(rel_path))

    enum_names = {member.name for member in AuditLogAction}
    assert used_names <= enum_names


def test_all_audit_action_enum_members_are_accounted_for_in_service_usage():
    used_names: set[str] = set()
    for rel_path in _SERVICE_FILES:
        used_names.update(_collect_audit_action_names(rel_path))

    enum_names = {member.name for member in AuditLogAction}
    unused = enum_names - used_names

    # Compatibility/public contract constants: defined, de jelenleg nincs mindegyikhez aktív service kibocsátó.
    assert unused == {
        "ADMIN_ACTION",
        "API_CREDENTIAL_CREATED",
        "API_CREDENTIAL_REVOKED",
        "API_CREDENTIAL_ROTATED",
        "INTERNAL_ENDPOINT_ACCESSED",
        "KNOWLEDGE_PII_DEPERSONALIZED",
        "KNOWLEDGE_SOURCE_DELETED",
        "KNOWLEDGE_TRAINING_STARTED",
        "KNOWLEDGE_UPLOAD_REJECTED",
        "KNOWLEDGE_URL_INGEST_REJECTED",
        "LOGOUT_ERROR",
        "PERMISSION_DENIED",
        "SIGNED_REQUEST_REJECTED",
    }
