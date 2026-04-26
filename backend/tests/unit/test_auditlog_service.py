import json

from core.capabilities.audit.service.audit_service import AuditService
from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.capabilities.audit.repositories.audit_log_repository import AuditLogRepository
from core.kernel.logging.observability import bind_observability_context, reset_observability_context


class _FakeRepo:
    def __init__(self):
        self.entries = []

    def append(self, **entry) -> None:
        self.entries.append(entry)


def test_audit_service_passes_sanitized_domain_entry_to_repo():
    repo = _FakeRepo()
    service = AuditService(repo)

    token = bind_observability_context(correlation_id="corr-123")
    try:
        service.log(
            AuditLogAction.LOGIN_FAILED,
            user_id=12,
            details={"email": "teszt@example.com", "password": "secret"},
            ip="127.0.0.1",
            user_agent="pytest",
        )
    finally:
        reset_observability_context(token)

    assert len(repo.entries) == 1
    entry = repo.entries[0]
    assert entry["action"] == AuditLogAction.LOGIN_FAILED
    assert entry["user_id"] == 12
    assert entry["actor_type"] == "user"
    assert entry["event_name"] == AuditLogAction.LOGIN_FAILED
    assert entry["outcome"] == "failure"
    assert entry["target_type"] == "user"
    assert entry["target_id"] == "12"
    assert entry["correlation_id"] == "corr-123"
    assert entry["ip"] == "127.0.0.1"
    assert entry["user_agent"] == "pytest"
    assert entry["details"] == {"email": "te***@******e.com", "password": "[REDACTED]"}


class _FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.committed = True


class _FakeSessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_audit_repository_serializes_domain_entry():
    session = _FakeSession()
    repo = AuditLogRepository(lambda: _FakeSessionContext(session))
    repo.append(
        action=AuditLogAction.USER_CREATED,
        user_id=3,
        details={"email": "***@example.com"},
        ip="10.0.0.1",
        user_agent="pytest",
        actor_type="user",
        event_name="user_created",
        outcome="success",
        target_type="user",
        target_id="3",
        correlation_id="corr-1",
    )

    assert session.committed is True
    assert len(session.added) == 1
    row = session.added[0]
    assert row.action == AuditLogAction.USER_CREATED
    assert row.user_id == 3
    assert row.actor_type == "user"
    assert row.event_name == "user_created"
    assert row.outcome == "success"
    assert row.target_type == "user"
    assert row.target_id == "3"
    assert row.correlation_id == "corr-1"
    assert row.ip == "10.0.0.1"
    assert row.user_agent == "pytest"
    assert json.loads(row.details) == {"email": "***@example.com"}


def test_audit_service_keeps_original_entry_and_handles_missing_details():
    repo = _FakeRepo()
    service = AuditService(repo)
    service.log(
        AuditLogAction.LOGOUT,
        user_id=None,
        details=None,
        ip="127.0.0.1",
        user_agent="pytest-none",
    )

    assert len(repo.entries) == 1
    stored = repo.entries[0]
    assert stored["details"] is None
    assert stored["user_id"] is None
    assert stored["actor_type"] == "system"
    assert stored["outcome"] == "success"


def test_audit_repository_serializes_null_details_as_null():
    session = _FakeSession()
    repo = AuditLogRepository(lambda: _FakeSessionContext(session))

    repo.append(
        action=AuditLogAction.LOGOUT,
        user_id=None,
        details=None,
        ip=None,
        user_agent=None,
        actor_type="system",
        event_name="logout",
        outcome="success",
        target_type=None,
        target_id=None,
        correlation_id="corr-2",
    )

    row = session.added[0]
    assert row.details is None
    assert row.user_id is None
    assert row.correlation_id == "corr-2"


def test_audit_repository_keeps_empty_details_distinct_from_null():
    session = _FakeSession()
    repo = AuditLogRepository(lambda: _FakeSessionContext(session))

    repo.append(
        action=AuditLogAction.LOGOUT,
        user_id=None,
        details={},
        ip=None,
        user_agent=None,
        actor_type="system",
        event_name="logout",
        outcome="success",
    )

    row = session.added[0]
    assert json.loads(row.details) == {}
