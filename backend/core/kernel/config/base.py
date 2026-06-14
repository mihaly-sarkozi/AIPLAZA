# backend/core/kernel/config/base.py
# Feladat: Az alkalmazás központi settings modelljét definiálja. Itt találhatóak az AppSettings/BaseConfig mezői, típusai és a Pydantic model szintű validátorok bekötései; a hosszabb validációs logika külön settings_*_validators.py fájlokban van. A config_loader tölti be, és a teljes backend ezt a settings szerződést használja, ezért ez core/framework szintű konfigurációs modell.
# Sárközi Mihály - 2026.05.21

import secrets
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.kernel.config.settings_constants import (
    DEFAULT_SMTP_FROM_EMAIL,
    DEFAULT_SMTP_FROM_NAME,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_USER,
)
from core.kernel.config.settings_validators import (
    validate_2fa,
    validate_cookie_samesite,
    validate_embedding,
    validate_observability,
    validate_password_policy_level,
    validate_rate_limits,
    validate_ttl,
    validate_upload_security,
)


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # App metadata: FastAPI dokumentáció és publikus verzió.
    app_name: str
    app_description: str
    app_version: str
    openapi_enabled: bool = True
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    # API (api_host = bind cím, pl. 0.0.0.0; port pl. 8001)
    api_host: str
    api_port: int

    # CORS: frontend origin(s), vesszővel elválasztva. acme.local esetén pl. :5173 (Vite)
    cors_origins: str
    cors_origin_regex: str = r"https?://[^.]+\.app\.test(:\d+)?"
    csrf_refresh_allowed_origins: str = ""
    
    # Jelszó beállító link (emailben): path + opcionális frontend port (ha a kérés a backend portjára jön, pl. proxy).
    # Pl. path=/set-password, port=5173 → link: http://demo.local:5173/set-password?token=...
    frontend_set_password_path: str = "/set-password"
    frontend_set_password_port: int | None = 5173  # A link ezt a portot használja (frontend). Élesben írd felül .env-ben (pl. 443) vagy töröld.
    frontend_base_url: str = ""  # Opcionális fix frontend base URL (pl. https://app.example.com)

    # Multi-tenant: base domain a Host-ból (acme.local → base=local → slug=acme)
    multi_tenant_enabled: bool = True
    tenant_base_domain: str
    install_host: str
    single_tenant_slug: str
    trusted_hosts: str

    # DB: élesben .env-ben (database_url – jelszó ne legyen kódban). PostgreSQL.
    database_url: str
    # pool_pre_ping: kapcsolat ellenőrzés használat előtt (élesben True). Dev-ben False = kevesebb round-trip, gyorsabb.
    database_pool_pre_ping: bool
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_sec: int = 30
    database_pool_recycle_sec: int = 1800

    # Redis: token allowlist (bejelentkezett tokenek jti). Üres = in-memory fallback (dev).
    redis_url: str = ""
    # Metrics endpoint védelem: prod-ban csak allowlistelt IP + token.
    metrics_access_token: str = ""
    metrics_allowed_ips: str
    metrics_require_token_in_prod: bool = True
    metrics_require_ip_allowlist_in_prod: bool = True
    # Observability export / tracing
    observability_service_name: str = "brainbankcenter-backend"
    observability_metrics_histogram_buckets_ms: str = "5,10,25,50,75,100,150,250,500,750,1000,2000,5000,10000"
    observability_trace_enabled: bool = False
    observability_trace_sample_ratio: float = 0.1
    observability_otlp_endpoint: str = ""
    sentry_enabled: bool = False
    sentry_dsn: str = ""
    sentry_environment: str = ""
    sentry_traces_sample_rate: float = 0.05
    log_level: str
    security_csp_extra_connect_src: str = ""
    security_csp_extra_img_src: str = ""
    security_csp_extra_frame_src: str = ""

    # Auth/JWT: élesben .env-ben JWT_SECRET kötelező (pl. openssl rand -hex 64)
    jwt_secret: str = secrets.token_hex(64)
    # jwt_issuer: "iss" claim (TokenService); prod-ban policy ellenőrzi (security_policy).
    jwt_issuer: str
    # jwt_audience: "aud" claim; dev-ben opcionális, prod-ban kötelező (startup + Pydantic).
    jwt_audience: str = ""
    # Cookie: Secure = csak HTTPS (élesben True); SameSite = lax | strict (subdomain izoláció + CSRF)
    # Domain NINCS beállítva → host-only: demo.local cookie nem megy acme.local-ra (tenant → tenant nem szivárog).
    cookie_secure: bool
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
    platform_event_outbox_lease_sec: int = 300
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
    platform_admin_allowed_ips: str

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
    openai_api_key: str = ""
    chat_provider: str
    chat_model: str
    ollama_url: str
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_api_key: str = "ollama"
    qdrant_url: str
    qdrant_api_key: str
    qdrant_timeout_sec: int = 120
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
    chat_use_kb_search: bool = True
    chat_allow_legacy_retrieval: bool = False
    kb_search_top_k: int = 10
    kb_search_language_filter_mode: str = "soft"
    chat_context_timeout_sec: int = 20
    channel_default_max_daily_limit: int = 5000
    channel_default_max_per_minute_limit: int = 120
    channel_demo_max_daily_limit: int = 100
    channel_demo_max_per_minute_limit: int = 10
    channel_session_max_per_minute: int = 30
    channel_session_max_burst_10s: int = 5
    channel_session_min_interval_ms: int = 1500
    channel_session_wait_max_ms: int = 900
    channel_session_cookie_max_age_sec: int = 86400
    channel_signature_max_skew_sec: int = 300

    # Demo signup abuse guard
    demo_signups_enabled: bool = True
    demo_signup_max_per_day: int = 30
    demo_signup_max_per_ip_per_day: int = 5
    demo_signup_max_per_ip_email_per_day: int = 5
    demo_signup_max_per_session_per_day: int = 5
    demo_signup_max_per_email: int = 5
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
    embedding_provider: str = "local"  # local | openai | dummy (dummy csak dev + allow_dummy)
    embedding_model: str = "BAAI/bge-m3"
    embedding_vector_size: int = 1024
    embedding_batch_size: int = 16
    embedding_device: str = "cpu"
    embedding_normalize: bool = True
    embedding_allow_dummy: bool = False
    embedding_model_cache_dir: str = ""
    embedding_worker_concurrency: int = 2
    knowledge_ingest_backgroundtasks_fallback_enabled: bool = False
    knowledge_url_ingest_enabled: bool = False
    knowledge_url_ingest_requires_isolated_worker: bool = True
    knowledge_url_ingest_worker_isolated: bool = False
    upload_magic_sniff_enabled: bool = True
    upload_spool_max_memory_bytes: int = 1024 * 1024
    upload_parser_timeout_sec: int = 20
    upload_parser_memory_limit_mb: int = 256
    upload_pdf_max_pages: int = 200
    upload_docx_max_zip_entries: int = 5000
    upload_docx_max_decompressed_bytes: int = 30 * 1024 * 1024
    upload_docx_max_compression_ratio: float = 120.0
    upload_malware_scan_provider: str = "none"  # none | clamav
    upload_malware_scan_required_in_prod: bool = True
    upload_malware_scan_timeout_sec: int = 5
    upload_clamav_unix_socket_path: str = "/var/run/clamav/clamd.ctl"
    kb_upload_max_mb: int = 40
    kb_store_raw_content: bool = False
    pii_encryption_key: str = ""
    pii_retention_days: int = 90
    pii_allow_legacy_plaintext_read: bool = False
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
    qdrant_fusion_semantic_weight: float = 0.72
    qdrant_fusion_lexical_weight: float = 0.28
    qdrant_lexical_overlap_weight: float = 0.72
    qdrant_lexical_substring_weight: float = 0.28
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
    kb_debug_trace_persist: bool = True
    kb_debug_trace_path: str = "logs/retrieval_traces.jsonl"

    # Object storage (knowledge fájlok és mellékletek).
    object_storage_enabled: bool = True
    object_storage_provider: str = "s3_compatible"
    object_storage_endpoint: str
    object_storage_region: str = "us-east-1"
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_bucket: str
    object_storage_secure: bool = False
    object_storage_force_path_style: bool = True

    # Mention pipeline debug: True esetén minden sentence után részletes mention debug print fut.
    debug_mention: bool = False
    # Claim pipeline debug: True esetén a claim extractor részletes debug printet és type debugot ír.
    debug_claim: bool = False
    # Space-time pipeline debug: True esetén a frame extractor részletes debug printet ír.
    debug_space_time: bool = False
    # Claim extractor verzió: csak "v1" támogatott; legacy pipeline nem visszakapcsolható runtime flaggel.
    claim_extractor_version: str = "v1"

    # Auth light path: path prefixek, ahol NINCS DB user fetch (token+allowlist+role elég).
    # Vesszővel elválasztott; üres = minden route full auth. Az app-specifikus light path-ok az app manifestből jönnek.
    auth_light_paths: str = ""

    # Email (SMTP): jelszót .env-ben (smtp_password)
    smtp_host: str = DEFAULT_SMTP_HOST
    smtp_port: int = DEFAULT_SMTP_PORT
    smtp_user: str = DEFAULT_SMTP_USER
    smtp_password: str = ""
    smtp_from_email: str = DEFAULT_SMTP_FROM_EMAIL
    smtp_from_name: str = DEFAULT_SMTP_FROM_NAME

    # Számlakiállító adatai. Élesben .env-ből töltsd (invoice_issuer_*).
    invoice_issuer_name: str
    invoice_issuer_tax_id: str
    invoice_issuer_address_line: str
    invoice_issuer_postal_code: str
    invoice_issuer_city: str
    invoice_issuer_region: str
    invoice_issuer_country: str
    invoice_issuer_phone: str
    invoice_issuer_website: str
    invoice_issuer_email: str

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
        validate_password_policy_level(self)
        return self

    @model_validator(mode="after")
    def validate_cookie_samesite_field(self) -> "BaseConfig":
        """cookie_samesite: csak lax, strict vagy none fogadható el."""
        validate_cookie_samesite(self)
        return self

    @model_validator(mode="after")
    def validate_upload_security_settings(self) -> "BaseConfig":
        validate_upload_security(self)
        return self

    @model_validator(mode="after")
    def validate_observability_settings(self) -> "BaseConfig":
        validate_observability(self)
        return self

    @model_validator(mode="after")
    def validate_ttl_fields(self) -> "BaseConfig":
        """Token TTL értékek alapszintű szanity check-je."""
        validate_ttl(self)
        return self

    @model_validator(mode="after")
    def validate_rate_limit_field(self) -> "BaseConfig":
        """Rate limit alapszintű szanity check-je."""
        validate_rate_limits(self)
        return self

    @model_validator(mode="after")
    def validate_embedding_fields(self) -> "BaseConfig":
        validate_embedding(self)
        return self

    @model_validator(mode="after")
    def validate_2fa_fields(self) -> "BaseConfig":
        """2FA konfiguráció alapszintű konzisztencia ellenőrzés."""
        validate_2fa(self)
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
        version = str(self.claim_extractor_version or "v1").strip().lower()
        return version if version == "v1" else "v1"


# Beszédesebb alias: a projekt egyetlen központi settings modellje.
AppSettings = BaseConfig
