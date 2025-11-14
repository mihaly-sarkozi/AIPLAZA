from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from datetime import datetime

AuthBase = declarative_base()


class UserORM(AuthBase):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), nullable=False, server_default="user")
    created_at = Column(DateTime, default=datetime.utcnow)


class SessionORM(AuthBase):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    jti = Column(String(128), unique=True, index=True, nullable=False)
    token_hash = Column(String(255), nullable=False)
    ip = Column(String(64))
    user_agent = Column(String(255))
    valid = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("ix_refresh_user_valid", "user_id", "valid"),)
