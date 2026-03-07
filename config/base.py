# Beállítások: alapértékek ITT, felülírás a .env-ből (loader tölti).
# Mindkettő kell: base.py = mezők + fallback, .env = tényleges érték ha megadod.
# 2026.02.14 - Sárközi Mihály

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # API (api_host = bind cím, pl. 0.0.0.0; port pl. 8001)
    api_host: str = "demo.local"
    api_port: int = 8001

    # CORS: frontend origin(s), vesszővel elválasztva. acme.local esetén pl. :5173 (Vite)
    cors_origins: str = "http://demo.local:5173,http://127.0.0.1:8001,http://localhost:5173"
    # Jelszó beállító link (emailben): path + opcionális frontend port (ha a kérés a backend portjára jön, pl. proxy).
    # Pl. path=/set-password, port=5173 → link: http://demo.local:5173/set-password?token=...
    frontend_set_password_path: str = "/set-password"
    frontend_set_password_port: int | None = 5173  # A link ezt a portot használja (frontend). Élesben írd felül .env-ben (pl. 443) vagy töröld.

    # Multi-tenant: base domain a Host-ból (acme.local → base=local → slug=acme)
    tenant_base_domain: str = "local"

    # DB: élesben .env-ben (database_url – jelszó ne legyen kódban). PostgreSQL.
    database_url: str = "postgresql+psycopg2://sarkozimihaly:erosjelszo123@localhost:5432/aiplaza"
    # pool_pre_ping: kapcsolat ellenőrzés használat előtt (élesben True). Dev-ben False = kevesebb round-trip, gyorsabb.
    database_pool_pre_ping: bool = True

    # LLM
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # Redis: token allowlist (bejelentkezett tokenek jti). Üres = in-memory fallback (dev).
    redis_url: str = ""

    # Auth/JWT: élesben .env-ben JWT_SECRET kötelező (pl. openssl rand -hex 64)
    jwt_secret: str = "5g6e7c14987t89bb845d1b69a5385a7afa8ef05efc08436a2554e0af4ebd75d89"
    # Cookie: Secure = csak HTTPS (élesben True); SameSite = lax | strict (subdomain izoláció + CSRF)
    # Domain NINCS beállítva → host-only: demo.local cookie nem megy acme.local-ra (tenant → tenant nem szivárog).
    cookie_secure: bool = True
    cookie_samesite: str = "lax"  # lax | strict
    access_ttl_min: int = 15
    refresh_ttl_days: int = 30  # auto_login esetén a refresh cookie max_age (nap)
    refresh_ttl_session_hours: int = 24  # nincs auto_login: refresh cookie max_age (óra); session cookie helyett, ne dobjon ki ~5 perc inaktivitás után

    # Security/audit: True = queue + háttér worker (kisebb request latency), False = szinkron log/audit (pl. tesztek)
    audit_events_async: bool = True

    # Rate limit: login IP alapú (5/perc élesben; tesztekben magasabb limit lehet env-ből)
    rate_limit_login_per_minute: int = 5

    # Email (SMTP): jelszót .env-ben (smtp_password)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "sarkozi.mihaly@gmail.com"
    smtp_password: str = "ahwh mahv eljj asha"
    smtp_from_email: str = "sarkozi.mihaly@gmail.com"
    smtp_from_name: str = "AIMAIL"