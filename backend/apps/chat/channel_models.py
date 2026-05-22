from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import PublicBase
from shared.utils.clock import utc_now


def _utcnow() -> datetime:
    return utc_now()


class ChannelCredentialORM(PublicBase):
    __tablename__ = "channel_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_channel_credentials_tenant_name"),
        {"schema": "public"},
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_type = Column(String(16), nullable=False, default="widget", index=True)
    name = Column(String(120), nullable=False)
    key_prefix = Column(String(32), nullable=False, index=True)
    active_secret_hash = Column(String(255), nullable=True)
    secret_hash = Column(String(255), nullable=False)
    next_key_prefix = Column(String(32), nullable=True, index=True)
    next_secret_hash = Column(String(255), nullable=True)
    secret_version = Column(String(16), nullable=False, default="active")
    rotating_until = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, default="active", index=True)
    allowed_kb_uuids = Column(JSONB, nullable=False, default=list)
    daily_limit = Column(Integer, nullable=False, default=200)
    per_minute_limit = Column(Integer, nullable=False, default=30)
    allowed_origins = Column(JSONB, nullable=False, default=list)
    allowed_ip_ranges = Column(JSONB, nullable=False, default=list)
    require_signed_requests = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now())
    updated_by = Column(Integer, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, nullable=True)


class ChannelUsageEventORM(PublicBase):
    __tablename__ = "channel_usage_events"
    __table_args__ = ({"schema": "public"},)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id = Column(Integer, ForeignKey("public.channel_credentials.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_type = Column(String(16), nullable=False, default="widget", index=True)
    period_key = Column(String(16), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="ok", index=True)
    question = Column(Text, nullable=False, default="")
    kb_uuid = Column(String(64), nullable=True, index=True)
    query_run_id = Column(String(64), nullable=True, index=True)
    response_ms = Column(Integer, nullable=False, default=0)
    llm_ms = Column(Integer, nullable=False, default=0)
    context_build_ms = Column(Integer, nullable=False, default=0)
    total_ms = Column(Integer, nullable=False, default=0)
    remote_ip = Column(String(64), nullable=True)
    origin = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True)


class ChannelFeedbackEventORM(PublicBase):
    __tablename__ = "channel_feedback_events"
    __table_args__ = ({"schema": "public"},)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id = Column(Integer, ForeignKey("public.channel_credentials.id", ondelete="SET NULL"), nullable=True, index=True)
    channel_type = Column(String(16), nullable=False, default="widget", index=True)
    query_run_id = Column(String(64), nullable=True, index=True)
    trace_id = Column(String(96), nullable=True, index=True)
    helpful = Column(Boolean, nullable=True, index=True)
    reason = Column(String(120), nullable=True)
    note = Column(Text, nullable=True)
    triage_status = Column(String(24), nullable=False, default="new", index=True)
    triage_owner = Column(String(120), nullable=True)
    triage_note = Column(Text, nullable=True)
    triaged_at = Column(DateTime(timezone=True), nullable=True)
    triaged_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now(), index=True)

