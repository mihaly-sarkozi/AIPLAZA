# apps/auth/adapter/http/request/__init__.py
"""Adapter (HTTP) bejövő kérés modellek – csak auth (login). User CRUD: apps.users."""
from apps.auth.adapter.http.request.login_req import LoginReq

__all__ = ["LoginReq"]
