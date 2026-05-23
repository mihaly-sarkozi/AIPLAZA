# backend/core/infrastructure/audit/models/audit_log_orm.py
# Feladat: A tenant schema `audit_log` táblájának SQLAlchemy modellje. Felhasználó, actor, action, event/outcome, target, correlation id, details, IP és user-agent mezőket tárol audit eseményekhez. Audit perzisztencia modell, amelyet tenant hook telepít és repository ír.
# Sárközi Mihály - 2026.05.21

from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey

from core.kernel.runtime.clock import utc_now
from core.kernel.db.model_bases import TenantSchemaBase


class AuditLogORM(TenantSchemaBase):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True) # Bejegyzés Azonosító
    created_at = Column(DateTime, default=utc_now, nullable=False) # Dátum és idő    
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)  # User azonosító
    actor_type = Column(String(32), nullable=False, default="system")
    action = Column(String(64), nullable=False, index=True)  # Milyen esemény történt:  login_success, login_failed, logout, refresh, user_created, stb.
    event_name = Column(String(128), nullable=True, index=True)
    outcome = Column(String(32), nullable=True, index=True)
    target_type = Column(String(64), nullable=True, index=True)
    target_id = Column(String(128), nullable=True, index=True)
    correlation_id = Column(String(128), nullable=True, index=True)
    details = Column(Text, nullable=True)  # Extra adatok JSON-ban
    ip = Column(String(64), nullable=True) # IP cím
    user_agent = Column(String(512), nullable=True) # User agent
