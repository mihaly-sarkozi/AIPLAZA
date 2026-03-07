# apps/audit/infrastructure/db/models/audit_log_orm.py
# Egy tábla: minden auth + user CRUD esemény. Tenantonként külön séma (TenantSchemaBase).
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey

from apps.auth.infrastructure.db.models.base import TenantSchemaBase


class AuditLogORM(TenantSchemaBase):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)  # null pl. sikertelen belépés
    action = Column(String(64), nullable=False, index=True)  # login_success, login_failed, logout, refresh, user_created, stb.
    details = Column(Text, nullable=True)  # JSON string opcionális részletekkel
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
