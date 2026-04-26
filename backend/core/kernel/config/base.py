# Beállítások: alapértékek ITT, felülírás a .env-ből (loader tölti).
# Mindkettő kell: base.py = mezők + fallback, .env = tényleges érték ha megadod.
# 2026.02.14 - Sárközi Mihály

import os
import secrets
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DATABASE_URL = "postgresql+psycopg2://localhost:5432/aiplaza"
_DEFAULT_SMTP_HOST = ""
_DEFAULT_SMTP_PORT = 587
_DEFAULT_SMTP_USER = ""
_DEFAULT_SMTP_FROM_EMAIL = ""
_DEFAULT_SMTP_FROM_NAME = ""


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
    multi_tenant_enabled: bool = True
    tenant_base_domain: str = "app.test"
    install_host: str = "localhost"
    single_tenant_slug: str = "demo"
    trusted_hosts: str = "localhost,127.0.0.1,*.app.test"

    # DB: élesben .env-ben (database_url – jelszó ne legyen kódban). PostgreSQL.
    database_url: str = _DEFAULT_DATABASE_URL
    # pool_pre_ping: kapcsolat ellenőrzés használat előtt (élesben True). Dev-ben False = kevesebb round-trip, gyorsabb.
    database_pool_pre_ping: bool = True
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_sec: int = 30
    database_pool_recycle_sec: int = 1800

    # Redis: token allowlist (bejelentkezett tokenek jti). Üres = in-memory fallback (dev).
    redis_url: str = ""

    # Auth/JWT: élesben .env-ben JWT_SECRET kötelező (pl. openssl rand -hex 64)
    jwt_secret: str = secrets.token_hex(64)
    # jwt_issuer: "iss" claim (TokenService); prod-ban policy ellenőrzi (security_policy).
    jwt_issuer: str = "AIPLAZA"
    # jwt_audience: "aud" claim; dev-ben opcionális, prod-ban kötelező (startup + Pydantic).
    jwt_audience: str = ""
    # Cookie: Secure = csak HTTPS (élesben True); SameSite = lax | strict (subdomain izoláció + CSRF)
    # Domain NINCS beállítva → host-only: demo.local cookie nem megy acme.local-ra (tenant → tenant nem szivárog).
    cookie_secure: bool = True
    cookie_samesite: str = "lax"  # lax | strict
    access_ttl_min: int = 15
    refresh_ttl_days: int = 30  # auto_login esetén a refresh cookie max_age (nap)
    refresh_ttl_session_hours: int = 24  # nincs auto_login: refresh cookie max_age (óra); session cookie helyett, ne dobjon ki ~5 perc inaktivitás után

    # Jelszopolicy: basic | standard | high. A validacio ezt a szintet hasznalja alapertelmezeskent.
    password_security_level: str = "standard"

    # Security/audit: True = queue + háttér worker (kisebb request latency), False = szinkron log/audit (pl. tesztek)
    audit_events_async: bool = True
    platform_event_outbox_max_retries: int = 10
    platform_event_outbox_retry_delay_sec: int = 5
    platform_event_outbox_poll_interval_sec: float = 1.0
    # Lejárt lock után más worker újra claimelheti a sort (összeomlott feldolgozó).
    platform_event_outbox_stale_lock_sec: int = 300
    # Üres = hostname:pid; több workerben állíts egyedi értéket (pl. Kubernetes pod name).
    platform_event_outbox_worker_instance_id: str = ""

    # Invite / set-password token TTL (óra); 1–4 óra ajánlott (rövid életű link).
    invite_ttl_hours: int = 4

    # 2FA policy: max próbálkozás / ablak, lock (központi réteg).
    two_fa_max_attempts: int = 5
    two_fa_attempt_window_minutes: int = 15
    two_fa_code_expiry_minutes: int = 10

    # Rate limit: login IP alapú (5/perc élesben; tesztekben magasabb limit lehet env-ből)
    rate_limit_login_per_minute: int = 10

    # Mention pipeline debug: True esetén minden sentence után részletes mention debug print fut.
    debug_mention: bool = True
    # Claim pipeline debug: True esetén a claim extractor részletes debug printet és type debugot ír.
    debug_claim: bool = True
    # Space-time pipeline debug: True esetén a frame extractor részletes debug printet ír.
    debug_space_time: bool = True
    # Claim extractor verzió: "legacy" = jelenlegi út, "v1" = új extractor.
    claim_extractor_version: str = "v1"

    # Auth light path: path prefixek, ahol NINCS DB user fetch (token+allowlist+role elég).
    # Vesszővel elválasztott; üres = minden route full auth. Az app-specifikus light path-ok az app manifestből jönnek.
    auth_light_paths: str = ""

    # Email (SMTP): jelszót .env-ben (smtp_password)
    smtp_host: str = _DEFAULT_SMTP_HOST
    smtp_port: int = _DEFAULT_SMTP_PORT
    smtp_user: str = _DEFAULT_SMTP_USER
    smtp_password: str = ""
    smtp_from_email: str = _DEFAULT_SMTP_FROM_EMAIL
    smtp_from_name: str = _DEFAULT_SMTP_FROM_NAME

    # ---------------------------------------------------------------------------
    # Biztonsági konfiguráció validátorok (Pydantic model szint)
    # ---------------------------------------------------------------------------
    # FONTOS: ezek a validátorok a settings objektum betöltésekor futnak.
    # Az alkalmazás indítása előtti explicit startup guard-ok (JWT entrópia,
    # CSRF env var, rate limit, TTL konzisztencia, 2FA, invite TTL) a
    # core/kernel/security/startup_guards.py fájlban találhatók és az
    # app_factory.py hívja meg őket a FastAPI app létrehozása előtt.
    # ---------------------------------------------------------------------------

    @model_validator(mode="after")
    def validate_password_policy_level_field(self) -> "BaseConfig":
        """Jelszó policy szint: csak megengedett értékek."""
        level = (self.password_security_level or "").strip().lower()
        if level not in {"basic", "standard", "high"}:
            raise ValueError(
                f"password_security_level érvénytelen: {level!r}. "
                "Megengedett értékek: basic, standard, high."
            )
        return self

    @model_validator(mode="after")
    def validate_cookie_samesite_field(self) -> "BaseConfig":
        """cookie_samesite: csak lax, strict vagy none fogadható el."""
        samesite = (self.cookie_samesite or "").strip().lower()
        if samesite not in {"lax", "strict", "none"}:
            raise ValueError(
                f"cookie_samesite érvénytelen érték: {samesite!r}. "
                "Megengedett értékek: lax, strict, none."
            )
        if samesite == "none" and self.cookie_secure is False:
            raise ValueError(
                "cookie_samesite='none' csak cookie_secure=True esetén érvényes "
                "(a böngésző különben elutasítja a cookie-t)."
            )
        return self

    @model_validator(mode="after")
    def validate_ttl_fields(self) -> "BaseConfig":
        """Token TTL értékek alapszintű szanity check-je."""
        if self.access_ttl_min <= 0:
            raise ValueError(f"access_ttl_min értéke {self.access_ttl_min}, de pozitívnak kell lennie.")
        if self.refresh_ttl_days <= 0:
            raise ValueError(f"refresh_ttl_days értéke {self.refresh_ttl_days}, de pozitívnak kell lennie.")
        if self.refresh_ttl_session_hours <= 0:
            raise ValueError(
                f"refresh_ttl_session_hours értéke {self.refresh_ttl_session_hours}, de pozitívnak kell lennie."
            )
        refresh_in_min = self.refresh_ttl_days * 24 * 60
        if self.access_ttl_min >= refresh_in_min:
            raise ValueError(
                f"access_ttl_min ({self.access_ttl_min} perc) >= refresh_ttl_days "
                f"({self.refresh_ttl_days} nap = {refresh_in_min} perc). "
                "Az access token élettartama rövidebb kell legyen a refresh tokenénél."
            )
        return self

    @model_validator(mode="after")
    def validate_rate_limit_field(self) -> "BaseConfig":
        """Rate limit alapszintű szanity check-je."""
        if self.rate_limit_login_per_minute <= 0:
            raise ValueError(
                f"rate_limit_login_per_minute értéke {self.rate_limit_login_per_minute}, "
                "de pozitívnak kell lennie."
            )
        return self

    @model_validator(mode="after")
    def validate_2fa_fields(self) -> "BaseConfig":
        """2FA konfiguráció alapszintű konzisztencia ellenőrzés."""
        if self.two_fa_max_attempts <= 0:
            raise ValueError(f"two_fa_max_attempts pozitívnak kell lennie, kapott: {self.two_fa_max_attempts}.")
        if self.two_fa_attempt_window_minutes <= 0:
            raise ValueError(
                f"two_fa_attempt_window_minutes pozitívnak kell lennie, kapott: {self.two_fa_attempt_window_minutes}."
            )
        if self.two_fa_code_expiry_minutes <= 0:
            raise ValueError(
                f"two_fa_code_expiry_minutes pozitívnak kell lennie, kapott: {self.two_fa_code_expiry_minutes}."
            )
        if self.two_fa_code_expiry_minutes >= self.two_fa_attempt_window_minutes:
            raise ValueError(
                f"two_fa_code_expiry_minutes ({self.two_fa_code_expiry_minutes}) "
                f">= two_fa_attempt_window_minutes ({self.two_fa_attempt_window_minutes}). "
                "A 2FA kód lejárata rövidebb kell legyen a kísérlet ablaknál."
            )
        return self

    @model_validator(mode="after")
    def validate_production_security(self) -> "BaseConfig":
        """Production-specifikus kritikus biztonsági ellenőrzések."""
        env = os.getenv("APP_ENV", "dev").lower()
        origins = [o.strip() for o in (self.cors_origins or "").split(",") if o.strip()]

        if env != "prod":
            return self

        # --- JWT secret ---
        env_secret = (os.getenv("JWT_SECRET") or "").strip()
        if not env_secret:
            raise ValueError(
                "Production környezetben a JWT_SECRET környezeti változó megadása kötelező. "
                "Generálj egyet: openssl rand -hex 64"
            )
        if len(env_secret) < 64:
            raise ValueError(
                f"Production JWT_SECRET legalább 64 karakter hosszú kell legyen "
                f"(jelenlegi: {len(env_secret)} karakter). "
                "Generálj egyet: openssl rand -hex 64"
            )
        if len(set(env_secret)) < 16:
            raise ValueError(
                "JWT_SECRET entrópiája elégtelen production-ben (túl sok ismétlődő karakter). "
                "Generálj egyet: openssl rand -hex 64"
            )

        # --- Frontend URL ---
        if not self.frontend_base_url:
            raise ValueError("frontend_base_url kötelező production környezetben.")

        # --- SMTP ---
        if not self.smtp_password:
            raise ValueError("smtp_password kötelező production környezetben.")
        if not (self.smtp_host or "").strip():
            raise ValueError("smtp_host kötelező production környezetben.")
        if not (self.smtp_user or "").strip():
            raise ValueError("smtp_user kötelező production környezetben.")
        if not (self.smtp_from_email or "").strip():
            raise ValueError("smtp_from_email kötelező production környezetben.")
        if not (self.smtp_from_name or "").strip():
            raise ValueError("smtp_from_name kötelező production környezetben.")

        # --- Database ---
        if not self.database_url or self.database_url == _DEFAULT_DATABASE_URL:
            raise ValueError("database_url kötelező és nem lehet default productionben.")

        # --- Cookie ---
        if not self.cookie_secure:
            raise ValueError("cookie_secure nem lehet False production környezetben.")

        # --- CORS ---
        if "*" in origins:
            raise ValueError("CORS wildcard origin ('*') nem engedélyezett production környezetben.")
        if any(origin.startswith("http://") for origin in origins):
            raise ValueError("Production CORS origin-ekhez kötelező a HTTPS.")

        # --- Trusted hosts ---
        if not (self.trusted_hosts or "").strip():
            raise ValueError("trusted_hosts kötelező production környezetben.")
        hosts = [h.strip() for h in (self.trusted_hosts or "").split(",") if h.strip()]
        if "*" in hosts:
            raise ValueError("Wildcard '*' trusted_hosts production-ben nem engedélyezett.")

        # --- Password policy ---
        if (self.password_security_level or "").strip().lower() == "basic":
            raise ValueError(
                "password_security_level='basic' production-ben nem engedélyezett. "
                "Legalább 'standard' szintet kell használni."
            )

        # --- Rate limit production korlát ---
        if self.rate_limit_login_per_minute > 30:
            raise ValueError(
                f"rate_limit_login_per_minute={self.rate_limit_login_per_minute} "
                "production-ben túl magas (ajánlott maximum: 30/perc)."
            )

        # --- JWT issuer / audience (domain szerződés) ---
        issuer = (self.jwt_issuer or "").strip()
        if len(issuer) < 3:
            raise ValueError(
                f"jwt_issuer túl rövid ({issuer!r}). Legalább 3 karakteres azonosítót adj meg."
            )
        audience = (self.jwt_audience or "").strip()
        if not audience:
            raise ValueError(
                "jwt_audience production-ben kötelező (egyértelmű API vagy erőforrás azonosító, pl. https://api.example.com)."
            )
        if audience == issuer:
            raise ValueError(
                "jwt_audience és jwt_issuer nem lehet azonos. Használj különböző iss és aud értékeket."
            )

        # --- Redis: rate limit tároló + token allowlist több példánynál ---
        if not (self.redis_url or "").strip():
            raise ValueError(
                "redis_url kötelező production környezetben (rate limit megosztott tároló és token allowlist)."
            )

        # --- CSRF nem kapcsolható ki ---
        disable_csrf = (os.getenv("DISABLE_CSRF") or "").strip().lower()
        if disable_csrf in ("1", "true", "yes", "on"):
            raise ValueError(
                "DISABLE_CSRF be van kapcsolva production-ben — távolítsd el vagy állítsd üresre."
            )

        # --- Access TTL production korlát ---
        if self.access_ttl_min > 60:
            raise ValueError(
                f"access_ttl_min={self.access_ttl_min} perc production-ben túl hosszú "
                "(ajánlott maximum: 60 perc)."
            )

        return self

    @property
    def DEBUG_MENTION(self) -> bool:
        return bool(self.debug_mention)

    @property
    def DEBUG_CLAIM(self) -> bool:
        return bool(self.debug_claim)

    @property
    def DEBUG_SPACE_TIME(self) -> bool:
        return bool(self.debug_space_time)

    @property
    def CLAIM_EXTRACTOR_VERSION(self) -> str:
        return str(self.claim_extractor_version or "legacy").strip().lower() or "legacy"
