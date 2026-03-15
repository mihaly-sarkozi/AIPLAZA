# Beállítások: alapértékek ITT, felülírás a .env-ből (loader tölti).
# Mindkettő kell: base.py = mezők + fallback, .env = tényleges érték ha megadod.
# 2026.02.14 - Sárközi Mihály

import os
import secrets
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # API (api_host = bind cím, pl. 0.0.0.0; port pl. 8001)
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    # CORS: frontend origin(s), vesszővel elválasztva. acme.local esetén pl. :5173 (Vite)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origin_regex: str = r"https?://[^.]+\.app\.test(:\d+)?"
    
    # Jelszó beállító link (emailben): path + opcionális frontend port (ha a kérés a backend portjára jön, pl. proxy).
    # Pl. path=/set-password, port=5173 → link: http://demo.local:5173/set-password?token=...
    frontend_set_password_path: str = "/set-password"
    frontend_set_password_port: int | None = 5173  # A link ezt a portot használja (frontend). Élesben írd felül .env-ben (pl. 443) vagy töröld.
    frontend_base_url: str = ""  # Opcionális fix frontend base URL (pl. https://app.example.com)

    # Multi-tenant: base domain a Host-ból (acme.local → base=local → slug=acme)
    tenant_base_domain: str = "app.test"
    trusted_hosts: str = "localhost,127.0.0.1,*.app.test"

    # DB: élesben .env-ben (database_url – jelszó ne legyen kódban). PostgreSQL.
    database_url: str = "postgresql+psycopg2://localhost:5432/aiplaza"
    # pool_pre_ping: kapcsolat ellenőrzés használat előtt (élesben True). Dev-ben False = kevesebb round-trip, gyorsabb.
    database_pool_pre_ping: bool = True

    # LLM
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # Redis: token allowlist (bejelentkezett tokenek jti). Üres = in-memory fallback (dev).
    redis_url: str = ""

    # Auth/JWT: élesben .env-ben JWT_SECRET kötelező (pl. openssl rand -hex 64)
    jwt_secret: str = secrets.token_hex(64)
    # jwt_audience: opcionális "aud" claim; ha megadva, token verify ellenőrzi (policy: iss + aud + nbf)
    jwt_audience: str = ""
    # Cookie: Secure = csak HTTPS (élesben True); SameSite = lax | strict (subdomain izoláció + CSRF)
    # Domain NINCS beállítva → host-only: demo.local cookie nem megy acme.local-ra (tenant → tenant nem szivárog).
    cookie_secure: bool = True
    cookie_samesite: str = "lax"  # lax | strict
    access_ttl_min: int = 15
    refresh_ttl_days: int = 30  # auto_login esetén a refresh cookie max_age (nap)
    refresh_ttl_session_hours: int = 24  # nincs auto_login: refresh cookie max_age (óra); session cookie helyett, ne dobjon ki ~5 perc inaktivitás után

    # Security/audit: True = queue + háttér worker (kisebb request latency), False = szinkron log/audit (pl. tesztek)
    audit_events_async: bool = True

    # Invite / set-password token TTL (óra); 1–4 óra ajánlott (rövid életű link).
    invite_ttl_hours: int = 4

    # 2FA policy: max próbálkozás / ablak, lock (központi réteg).
    two_fa_max_attempts: int = 5
    two_fa_attempt_window_minutes: int = 15
    two_fa_code_expiry_minutes: int = 10

    # Rate limit: login IP alapú (5/perc élesben; tesztekben magasabb limit lehet env-ből)
    rate_limit_login_per_minute: int = 5

    # Auth light path: path prefixek, ahol NINCS DB user fetch (token+allowlist+role elég).
    # Teljes user csak write/admin/settings/permission végpontokra. Tudatosan szűk: docs/Auth_light_paths.md
    # Vesszővel elválasztott; üres = minden route full auth. Alap: csak /api/chat.
    auth_light_paths: str = "/api/chat"
    kb_upload_max_mb: int = 40
    kb_store_raw_content: bool = False
    pii_encryption_key: str = ""  # Fernet kulcs (urlsafe base64, 32 bytes)
    pii_retention_days: int = 90
    pii_allow_legacy_plaintext_read: bool = True

    # Retrieval/rerank súlyok (P3 tuning)
    rerank_semantic_match_weight: float = 0.22
    rerank_entity_match_weight: float = 0.20
    rerank_lexical_match_weight: float = 0.08
    rerank_time_match_weight: float = 0.16
    rerank_place_match_weight: float = 0.08
    rerank_graph_proximity_weight: float = 0.10
    rerank_strength_weight: float = 0.10
    rerank_confidence_weight: float = 0.10
    rerank_recency_weight: float = 0.04
    rerank_status_weight: float = 1.0
    rerank_relation_confidence_weight: float = 0.06

    # Hybrid recall tuning (Qdrant score blending)
    qdrant_fusion_semantic_weight: float = 0.72
    qdrant_fusion_lexical_weight: float = 0.28
    qdrant_lexical_overlap_weight: float = 0.72
    qdrant_lexical_substring_weight: float = 0.28

    # Context/runsize korlátok (P3 adaptive threshold)
    kb_max_seed_assertions: int = 8
    kb_max_expanded_assertions: int = 12
    kb_max_relation_hops: int = 2
    kb_min_confidence: float = 0.20
    kb_min_current_strength: float = 0.03
    kb_context_token_budget: int = 2200
    kb_context_max_evidence_per_assertion: int = 2
    kb_context_max_key_assertions: int = 8
    kb_context_max_supporting_assertions: int = 10
    kb_context_max_source_chunks: int = 3
    kb_context_include_conflicts: bool = True
    kb_context_include_superseded: bool = False

    # Debug/trace persistence
    kb_debug_trace_persist: bool = True
    kb_debug_trace_path: str = "logs/retrieval_traces.jsonl"

    # Email (SMTP): jelszót .env-ben (smtp_password)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "sarkozi.mihaly@gmail.com"
    smtp_password: str = ""
    smtp_from_email: str = "sarkozi.mihaly@gmail.com"
    smtp_from_name: str = "AIPLAZA"

    @model_validator(mode="after")
    def validate_security_settings(self):
        env = os.getenv("APP_ENV", "dev").lower()
        origins = [o.strip() for o in (self.cors_origins or "").split(",") if o.strip()]
        if env == "prod":
            if not self.frontend_base_url:
                raise ValueError("frontend_base_url kötelező production környezetben.")
            if not self.smtp_password:
                raise ValueError("smtp_password kötelező production környezetben.")
            if not self.database_url or self.database_url == "postgresql+psycopg2://localhost:5432/aiplaza":
                raise ValueError("database_url kötelező és nem lehet default productionben.")
            if not self.cookie_secure:
                raise ValueError("cookie_secure nem lehet False production környezetben.")
            if "*" in origins:
                raise ValueError("CORS wildcard origin ('*') nem engedélyezett production környezetben.")
            if any(origin.startswith("http://") for origin in origins):
                raise ValueError("Production CORS origin-ekhez kötelező a HTTPS.")
            if not (self.trusted_hosts or "").strip():
                raise ValueError("trusted_hosts kötelező production környezetben.")
            if not (self.pii_encryption_key or "").strip():
                raise ValueError("pii_encryption_key kötelező production környezetben.")
            if int(self.pii_retention_days) <= 0:
                raise ValueError("pii_retention_days productionben 0-nál nagyobb kell legyen.")
        return self