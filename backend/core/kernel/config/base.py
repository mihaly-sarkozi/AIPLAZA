# Beállítások: alapértékek ITT, felülírás a .env-ből (loader tölti).
# Mindkettő kell: base.py = mezők + fallback, .env = tényleges érték ha megadod.
# 2026.02.14 - Sárközi Mihály

import os
import re
import secrets
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DATABASE_URL = "postgresql+psycopg2://localhost:5432/aiplaza"
_DEFAULT_SMTP_HOST = ""
_DEFAULT_SMTP_PORT = 587
_DEFAULT_SMTP_USER = ""
_DEFAULT_SMTP_FROM_EMAIL = ""
_DEFAULT_SMTP_FROM_NAME = ""
_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # API (api_host = bind cím, pl. 0.0.0.0; port pl. 8001)
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    # CORS: frontend origin(s), vesszővel elválasztva. acme.local esetén pl. :5173 (Vite)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origin_regex: str = r"https?://[^.]+\.app\.test(:\d+)?"
    csrf_refresh_allowed_origins: str = ""
    
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
    # Metrics endpoint védelem: prod-ban csak allowlistelt IP + token.
    metrics_access_token: str = ""
    metrics_allowed_ips: str = "127.0.0.1,::1"
    metrics_require_token_in_prod: bool = True
    metrics_require_ip_allowlist_in_prod: bool = True
    # Observability export / tracing
    observability_service_name: str = "aiplaza-backend"
    observability_metrics_histogram_buckets_ms: str = "5,10,25,50,75,100,150,250,500,750,1000,2000,5000,10000"
    observability_trace_enabled: bool = False
    observability_trace_sample_ratio: float = 0.1
    observability_otlp_endpoint: str = ""
    sentry_enabled: bool = False
    sentry_dsn: str = ""
    sentry_environment: str = ""
    sentry_traces_sample_rate: float = 0.05

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
    platform_event_outbox_backlog_soft_limit: int = 5000
    platform_event_handler_timeout_sec: int = 15
    # Lejárt lock után más worker újra claimelheti a sort (összeomlott feldolgozó).
    platform_event_outbox_stale_lock_sec: int = 300
    # Üres = hostname:pid; több workerben állíts egyedi értéket (pl. Kubernetes pod name).
    platform_event_outbox_worker_instance_id: str = ""

    # Invite / set-password token TTL (óra); 1–4 óra ajánlott (rövid életű link).
    invite_ttl_hours: int = 4

    # Főtenant / platform admin bootstrap. Ha mindkettő meg van adva, induláskor
    # létrejön az első platform admin felhasználó a public sémában.
    platform_admin_bootstrap_email: str = ""
    platform_admin_bootstrap_password: str = ""
    platform_admin_mfa_required: bool = True
    platform_admin_login_alert_email: str = ""
    platform_admin_ip_allowlist_enabled: bool = False
    platform_admin_allowed_ips: str = "127.0.0.1,::1"

    # 2FA policy: max próbálkozás / ablak, lock (központi réteg).
    two_fa_max_attempts: int = 5
    two_fa_attempt_window_minutes: int = 15
    two_fa_code_expiry_minutes: int = 10

    # Rate limit: login IP alapú (5/perc élesben; tesztekben magasabb limit lehet env-ből)
    rate_limit_login_per_minute: int = 10
    rate_limit_login_step1_per_email_per_hour: int = 25
    rate_limit_login_burst_per_10s: int = 5
    rate_limit_login_failure_ban_threshold: int = 16
    rate_limit_login_failure_ban_window_sec: int = 900
    rate_limit_login_failure_ban_hours: int = 2
    platform_admin_max_failed_login_attempts: int = 8
    platform_admin_mfa_attempt_window_minutes: int = 15
    platform_admin_mfa_lock_minutes: int = 30
    platform_admin_mfa_totp_max_attempts_per_user: int = 5
    platform_admin_mfa_totp_max_attempts_per_ip: int = 10
    platform_admin_mfa_recovery_max_attempts_per_user: int = 3
    platform_admin_mfa_recovery_max_attempts_per_ip: int = 6

    # Websocket flood protection
    ws_chat_max_messages_per_10s: int = 20
    ws_chat_max_message_chars: int = 8000
    ws_chat_idle_timeout_sec: int = 45
    enable_chat_websocket: bool = False
    ws_chat_max_connections_per_tenant: int = 20
    ws_chat_max_connections_per_user: int = 3

    # LLM abuse guard: tenant + channel scoped budget
    llm_budget_request_limit_per_minute: int = 120
    llm_budget_prompt_chars_per_minute: int = 120000
    llm_budget_concurrency_limit: int = 8
    llm_budget_tenant_daily_tokens: int = 120000
    llm_budget_tenant_monthly_tokens: int = 2000000
    llm_budget_demo_daily_tokens: int = 30000
    llm_budget_demo_monthly_tokens: int = 150000
    llm_budget_starter_monthly_tokens: int = 900000
    llm_budget_global_daily_spend_usd: float = 15.0
    llm_budget_input_cost_per_1k_tokens_usd: float = 0.003
    llm_budget_output_cost_per_1k_tokens_usd: float = 0.006
    llm_budget_estimated_completion_tokens: int = 220
    llm_budget_fail_closed_without_redis: bool = True
    token_allowlist_fail_closed_without_redis: bool = True
    channel_quota_fail_closed_without_redis: bool = True
    chat_max_answer_chars: int = 2400
    chat_max_input_chars: int = 2400
    chat_max_history_items: int = 30
    chat_max_history_chars: int = 12000
    chat_max_retrieval_items: int = 20
    chat_max_retrieval_chars: int = 6000
    chat_default_max_sources: int = 8
    chat_starter_max_sources: int = 5
    chat_demo_max_sources: int = 3
    chat_demo_max_question_chars: int = 1024
    chat_demo_max_history_items: int = 8
    chat_demo_max_history_chars: int = 2400
    chat_demo_max_retrieval_items: int = 6
    chat_demo_max_retrieval_chars: int = 1800
    chat_demo_allow_debug: bool = False
    chat_debug_responses_enabled: bool = True
    channel_default_max_daily_limit: int = 5000
    channel_default_max_per_minute_limit: int = 120
    channel_demo_max_daily_limit: int = 100
    channel_demo_max_per_minute_limit: int = 10
    channel_session_max_per_minute: int = 30
    channel_session_max_burst_10s: int = 5
    channel_session_min_interval_ms: int = 1500
    channel_session_wait_max_ms: int = 900
    channel_session_cookie_max_age_sec: int = 86400

    # Demo signup abuse guard
    demo_signups_enabled: bool = True
    demo_signup_max_per_day: int = 30
    demo_signup_max_per_ip_per_day: int = 3
    demo_signup_max_per_ip_email_per_day: int = 2
    demo_signup_max_per_session_per_day: int = 2
    demo_signup_max_per_email: int = 1
    demo_trial_days: int = 7
    demo_signup_captcha_provider: str = "none"  # none | turnstile | recaptcha
    demo_signup_captcha_secret: str = ""
    demo_signup_require_captcha: bool = False
    demo_signup_require_email_verification: bool = True
    demo_signup_expose_login_token_in_response: bool = False
    demo_signup_block_disposable_emails: bool = True
    demo_signup_external_disposable_domains_path: str = ""
    demo_signup_require_mx: bool = True
    demo_signup_fail_closed_without_redis: bool = True
    training_mfa_required: bool = True

    # Embedding provider konfiguráció (knowledge indexelés / retrieval).
    embedding_provider: str = "local"  # local | openai
    embedding_model: str = "BAAI/bge-m3"
    embedding_vector_size: int = 1024
    embedding_batch_size: int = 16
    embedding_worker_concurrency: int = 2
    legacy_knowledge_ingest_enabled: bool = False
    knowledge_url_ingest_enabled: bool = False
    upload_magic_sniff_enabled: bool = True
    upload_parser_timeout_sec: int = 20
    upload_pdf_max_pages: int = 200
    upload_docx_max_zip_entries: int = 5000
    upload_docx_max_decompressed_bytes: int = 30 * 1024 * 1024
    upload_docx_max_compression_ratio: float = 120.0
    upload_malware_scan_provider: str = "none"  # none | clamav
    upload_malware_scan_required_in_prod: bool = True
    upload_malware_scan_timeout_sec: int = 5
    upload_clamav_unix_socket_path: str = "/var/run/clamav/clamd.ctl"

    # Mention pipeline debug: True esetén minden sentence után részletes mention debug print fut.
    debug_mention: bool = False
    # Claim pipeline debug: True esetén a claim extractor részletes debug printet és type debugot ír.
    debug_claim: bool = False
    # Space-time pipeline debug: True esetén a frame extractor részletes debug printet ír.
    debug_space_time: bool = False
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

    # Számlakiállító adatai. Élesben .env-ből töltsd (invoice_issuer_*).
    invoice_issuer_name: str = "BrainBankCenter"
    invoice_issuer_tax_id: str = ""
    invoice_issuer_address_line: str = ""
    invoice_issuer_postal_code: str = ""
    invoice_issuer_city: str = ""
    invoice_issuer_region: str = ""
    invoice_issuer_country: str = ""
    invoice_issuer_phone: str = ""
    invoice_issuer_website: str = ""
    invoice_issuer_email: str = ""

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
    def validate_upload_security_settings(self) -> "BaseConfig":
        if int(self.upload_parser_timeout_sec) <= 0:
            raise ValueError("upload_parser_timeout_sec pozitívnak kell lennie.")
        if int(self.upload_pdf_max_pages) <= 0:
            raise ValueError("upload_pdf_max_pages pozitívnak kell lennie.")
        if int(self.upload_docx_max_zip_entries) <= 0:
            raise ValueError("upload_docx_max_zip_entries pozitívnak kell lennie.")
        if int(self.upload_docx_max_decompressed_bytes) <= 0:
            raise ValueError("upload_docx_max_decompressed_bytes pozitívnak kell lennie.")
        if float(self.upload_docx_max_compression_ratio) <= 1.0:
            raise ValueError("upload_docx_max_compression_ratio értéke legyen > 1.0.")
        provider = str(self.upload_malware_scan_provider or "none").strip().lower()
        if provider not in {"none", "clamav"}:
            raise ValueError("upload_malware_scan_provider értéke: none vagy clamav.")
        if int(self.upload_malware_scan_timeout_sec) <= 0:
            raise ValueError("upload_malware_scan_timeout_sec pozitívnak kell lennie.")
        socket_path = str(self.upload_clamav_unix_socket_path or "").strip()
        if provider == "clamav" and not socket_path:
            raise ValueError("clamav providerhez upload_clamav_unix_socket_path kötelező.")
        if provider == "clamav" and socket_path:
            # Path check csak formai, tényleges elérhetőség runtime.
            _ = Path(socket_path)
        return self

    @model_validator(mode="after")
    def validate_observability_settings(self) -> "BaseConfig":
        if not (0.0 <= float(self.observability_trace_sample_ratio) <= 1.0):
            raise ValueError("observability_trace_sample_ratio értéke 0.0 és 1.0 között legyen.")
        if not (0.0 <= float(self.sentry_traces_sample_rate) <= 1.0):
            raise ValueError("sentry_traces_sample_rate értéke 0.0 és 1.0 között legyen.")
        buckets_raw = str(self.observability_metrics_histogram_buckets_ms or "").strip()
        if not buckets_raw:
            raise ValueError("observability_metrics_histogram_buckets_ms nem lehet üres.")
        try:
            parsed = [float(item.strip()) for item in buckets_raw.split(",") if item.strip()]
        except Exception as exc:
            raise ValueError("observability_metrics_histogram_buckets_ms csak számokat tartalmazhat.") from exc
        if not parsed or any(value <= 0 for value in parsed):
            raise ValueError("observability histogram bucket értékek legyenek pozitív számok.")
        if parsed != sorted(parsed):
            raise ValueError("observability histogram bucket lista legyen növekvő sorrendben.")
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
        if self.rate_limit_login_step1_per_email_per_hour <= 0:
            raise ValueError("rate_limit_login_step1_per_email_per_hour pozitívnak kell lennie.")
        if self.rate_limit_login_burst_per_10s <= 0:
            raise ValueError("rate_limit_login_burst_per_10s pozitívnak kell lennie.")
        if self.rate_limit_login_failure_ban_threshold <= 0:
            raise ValueError("rate_limit_login_failure_ban_threshold pozitívnak kell lennie.")
        if self.rate_limit_login_failure_ban_window_sec <= 0:
            raise ValueError("rate_limit_login_failure_ban_window_sec pozitívnak kell lennie.")
        if self.rate_limit_login_failure_ban_hours <= 0:
            raise ValueError("rate_limit_login_failure_ban_hours pozitívnak kell lennie.")
        if self.platform_admin_max_failed_login_attempts <= 0:
            raise ValueError("platform_admin_max_failed_login_attempts pozitívnak kell lennie.")
        if self.platform_admin_mfa_attempt_window_minutes <= 0:
            raise ValueError("platform_admin_mfa_attempt_window_minutes pozitívnak kell lennie.")
        if self.platform_admin_mfa_lock_minutes <= 0:
            raise ValueError("platform_admin_mfa_lock_minutes pozitívnak kell lennie.")
        if self.platform_admin_mfa_totp_max_attempts_per_user <= 0:
            raise ValueError("platform_admin_mfa_totp_max_attempts_per_user pozitívnak kell lennie.")
        if self.platform_admin_mfa_totp_max_attempts_per_ip <= 0:
            raise ValueError("platform_admin_mfa_totp_max_attempts_per_ip pozitívnak kell lennie.")
        if self.platform_admin_mfa_recovery_max_attempts_per_user <= 0:
            raise ValueError("platform_admin_mfa_recovery_max_attempts_per_user pozitívnak kell lennie.")
        if self.platform_admin_mfa_recovery_max_attempts_per_ip <= 0:
            raise ValueError("platform_admin_mfa_recovery_max_attempts_per_ip pozitívnak kell lennie.")
        if self.ws_chat_max_messages_per_10s <= 0:
            raise ValueError("ws_chat_max_messages_per_10s pozitívnak kell lennie.")
        if self.ws_chat_max_message_chars <= 0:
            raise ValueError("ws_chat_max_message_chars pozitívnak kell lennie.")
        if self.ws_chat_idle_timeout_sec <= 0:
            raise ValueError("ws_chat_idle_timeout_sec pozitívnak kell lennie.")
        if self.ws_chat_max_connections_per_tenant <= 0:
            raise ValueError("ws_chat_max_connections_per_tenant pozitívnak kell lennie.")
        if self.ws_chat_max_connections_per_user <= 0:
            raise ValueError("ws_chat_max_connections_per_user pozitívnak kell lennie.")
        if self.llm_budget_request_limit_per_minute <= 0:
            raise ValueError("llm_budget_request_limit_per_minute pozitívnak kell lennie.")
        if self.llm_budget_prompt_chars_per_minute <= 0:
            raise ValueError("llm_budget_prompt_chars_per_minute pozitívnak kell lennie.")
        if self.llm_budget_concurrency_limit <= 0:
            raise ValueError("llm_budget_concurrency_limit pozitívnak kell lennie.")
        if self.llm_budget_tenant_daily_tokens <= 0:
            raise ValueError("llm_budget_tenant_daily_tokens pozitívnak kell lennie.")
        if self.llm_budget_tenant_monthly_tokens <= 0:
            raise ValueError("llm_budget_tenant_monthly_tokens pozitívnak kell lennie.")
        if self.llm_budget_demo_daily_tokens <= 0:
            raise ValueError("llm_budget_demo_daily_tokens pozitívnak kell lennie.")
        if self.llm_budget_demo_monthly_tokens <= 0:
            raise ValueError("llm_budget_demo_monthly_tokens pozitívnak kell lennie.")
        if self.llm_budget_starter_monthly_tokens <= 0:
            raise ValueError("llm_budget_starter_monthly_tokens pozitívnak kell lennie.")
        if self.llm_budget_global_daily_spend_usd <= 0:
            raise ValueError("llm_budget_global_daily_spend_usd pozitívnak kell lennie.")
        if self.llm_budget_input_cost_per_1k_tokens_usd <= 0:
            raise ValueError("llm_budget_input_cost_per_1k_tokens_usd pozitívnak kell lennie.")
        if self.llm_budget_output_cost_per_1k_tokens_usd <= 0:
            raise ValueError("llm_budget_output_cost_per_1k_tokens_usd pozitívnak kell lennie.")
        if self.llm_budget_estimated_completion_tokens <= 0:
            raise ValueError("llm_budget_estimated_completion_tokens pozitívnak kell lennie.")
        if self.chat_max_answer_chars <= 0:
            raise ValueError("chat_max_answer_chars pozitívnak kell lennie.")
        if self.chat_max_input_chars <= 0:
            raise ValueError("chat_max_input_chars pozitívnak kell lennie.")
        if self.chat_max_history_items <= 0:
            raise ValueError("chat_max_history_items pozitívnak kell lennie.")
        if self.chat_max_history_chars <= 0:
            raise ValueError("chat_max_history_chars pozitívnak kell lennie.")
        if self.chat_max_retrieval_items <= 0:
            raise ValueError("chat_max_retrieval_items pozitívnak kell lennie.")
        if self.chat_max_retrieval_chars <= 0:
            raise ValueError("chat_max_retrieval_chars pozitívnak kell lennie.")
        if self.chat_default_max_sources <= 0:
            raise ValueError("chat_default_max_sources pozitívnak kell lennie.")
        if self.chat_starter_max_sources <= 0:
            raise ValueError("chat_starter_max_sources pozitívnak kell lennie.")
        if self.chat_demo_max_sources <= 0:
            raise ValueError("chat_demo_max_sources pozitívnak kell lennie.")
        if self.chat_demo_max_question_chars <= 0:
            raise ValueError("chat_demo_max_question_chars pozitívnak kell lennie.")
        if self.chat_demo_max_history_items <= 0:
            raise ValueError("chat_demo_max_history_items pozitívnak kell lennie.")
        if self.chat_demo_max_history_chars <= 0:
            raise ValueError("chat_demo_max_history_chars pozitívnak kell lennie.")
        if self.chat_demo_max_retrieval_items <= 0:
            raise ValueError("chat_demo_max_retrieval_items pozitívnak kell lennie.")
        if self.chat_demo_max_retrieval_chars <= 0:
            raise ValueError("chat_demo_max_retrieval_chars pozitívnak kell lennie.")
        if self.channel_default_max_daily_limit <= 0:
            raise ValueError("channel_default_max_daily_limit pozitívnak kell lennie.")
        if self.channel_default_max_per_minute_limit <= 0:
            raise ValueError("channel_default_max_per_minute_limit pozitívnak kell lennie.")
        if self.channel_demo_max_daily_limit <= 0:
            raise ValueError("channel_demo_max_daily_limit pozitívnak kell lennie.")
        if self.channel_demo_max_per_minute_limit <= 0:
            raise ValueError("channel_demo_max_per_minute_limit pozitívnak kell lennie.")
        if self.channel_session_max_per_minute <= 0:
            raise ValueError("channel_session_max_per_minute pozitívnak kell lennie.")
        if self.channel_session_max_burst_10s <= 0:
            raise ValueError("channel_session_max_burst_10s pozitívnak kell lennie.")
        if self.channel_session_min_interval_ms <= 0:
            raise ValueError("channel_session_min_interval_ms pozitívnak kell lennie.")
        if self.channel_session_wait_max_ms < 0:
            raise ValueError("channel_session_wait_max_ms nem lehet negatív.")
        if self.channel_session_cookie_max_age_sec <= 0:
            raise ValueError("channel_session_cookie_max_age_sec pozitívnak kell lennie.")
        if self.platform_event_outbox_backlog_soft_limit <= 0:
            raise ValueError("platform_event_outbox_backlog_soft_limit pozitívnak kell lennie.")
        if self.platform_event_handler_timeout_sec <= 0:
            raise ValueError("platform_event_handler_timeout_sec pozitívnak kell lennie.")
        if self.demo_signup_max_per_day <= 0:
            raise ValueError("demo_signup_max_per_day pozitívnak kell lennie.")
        if self.demo_signup_max_per_ip_per_day <= 0:
            raise ValueError("demo_signup_max_per_ip_per_day pozitívnak kell lennie.")
        if self.demo_signup_max_per_ip_email_per_day <= 0:
            raise ValueError("demo_signup_max_per_ip_email_per_day pozitívnak kell lennie.")
        if self.demo_signup_max_per_session_per_day <= 0:
            raise ValueError("demo_signup_max_per_session_per_day pozitívnak kell lennie.")
        if self.demo_signup_max_per_email <= 0:
            raise ValueError("demo_signup_max_per_email pozitívnak kell lennie.")
        if self.demo_trial_days <= 0:
            raise ValueError("demo_trial_days pozitívnak kell lennie.")
        provider = (self.demo_signup_captcha_provider or "").strip().lower()
        if provider not in {"none", "turnstile", "recaptcha"}:
            raise ValueError("demo_signup_captcha_provider értéke: none, turnstile vagy recaptcha lehet.")
        if self.demo_signup_require_captcha and provider == "none":
            raise ValueError("demo_signup_require_captcha=True esetén demo_signup_captcha_provider nem lehet 'none'.")
        return self

    @model_validator(mode="after")
    def validate_embedding_fields(self) -> "BaseConfig":
        provider = (self.embedding_provider or "").strip().lower()
        if provider not in {"local", "openai"}:
            raise ValueError("embedding_provider érvénytelen. Megengedett értékek: local, openai.")
        if self.embedding_vector_size <= 0:
            raise ValueError("embedding_vector_size pozitívnak kell lennie.")
        if self.embedding_batch_size <= 0:
            raise ValueError("embedding_batch_size pozitívnak kell lennie.")
        if self.embedding_worker_concurrency <= 0:
            raise ValueError("embedding_worker_concurrency pozitívnak kell lennie.")
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

        # --- Tenant base domain / CORS regex policy ---
        base_domain = (self.tenant_base_domain or "").strip().lower()
        if not base_domain:
            raise ValueError("tenant_base_domain kötelező production környezetben.")
        if base_domain in {"local", "localhost"}:
            raise ValueError("tenant_base_domain='local/localhost' production-ben nem engedélyezett.")
        if any(token in base_domain for token in ("*", "/", "\\", ":", " ")):
            raise ValueError("tenant_base_domain production-ben csak tiszta hostname lehet.")
        labels = [part for part in base_domain.split(".") if part]
        if len(labels) < 2:
            raise ValueError(
                "tenant_base_domain production-ben teljes domain kell legyen (pl. app.example.com)."
            )
        if any(not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
            raise ValueError("tenant_base_domain nem RFC-kompatibilis hostname formátum.")

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

        # --- CSRF / debug bypass env-ek productionben ne legyenek beállítva ---
        disable_csrf_raw = (os.getenv("DISABLE_CSRF") or "").strip()
        if disable_csrf_raw:
            raise ValueError(
                "DISABLE_CSRF production-ben nem lehet beállítva. "
                "Távolítsd el az env-ből (ne 0-ra állítsd, hanem töröld)."
            )
        billing_debug_routes_raw = (os.getenv("BILLING_DEBUG_ROUTES_ENABLED") or "").strip()
        if billing_debug_routes_raw:
            raise ValueError(
                "BILLING_DEBUG_ROUTES_ENABLED production-ben nem lehet beállítva. "
                "A debug route-ok maradjanak rejtve."
            )
        billing_disabled_raw = (os.getenv("BILLING_DISABLED") or "").strip()
        if billing_disabled_raw:
            raise ValueError(
                "BILLING_DISABLED production-ben nem lehet beállítva. "
                "Ez megkerülheti a kérdéskeret-védelmet."
            )
        billing_provider_raw = (os.getenv("BILLING_PROVIDER") or "manual").strip().lower()
        if billing_provider_raw in {"simulated", "stripe_test"}:
            raise ValueError(
                f"BILLING_PROVIDER={billing_provider_raw!r} production-ben nem engedélyezett. "
                "Amíg nincs éles payment provider, manual módot használj."
            )
        billing_mode_raw = (os.getenv("BILLING_MODE") or "manual").strip().lower()
        if billing_mode_raw != "manual":
            raise ValueError(
                f"BILLING_MODE={billing_mode_raw!r} production-ben nem engedélyezett. "
                "Állítsd BILLING_MODE=manual értékre."
            )
        pii_legacy_plaintext_raw = (os.getenv("PII_ALLOW_LEGACY_PLAINTEXT_READ") or "").strip().lower()
        if pii_legacy_plaintext_raw in {"1", "true", "yes", "on"}:
            raise ValueError(
                "PII_ALLOW_LEGACY_PLAINTEXT_READ production-ben nem engedélyezett. "
                "Futtasd le a PII migrációt, majd állítsd false értékre."
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
