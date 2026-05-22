# backend/core/kernel/config/settings_limit_validators.py
# Feladat: A rate limit, quota, chat, websocket, outbox és demo signup limit mezők alapszintű pozitivitási validációját végzi. Ezek a mezők sok alrendszert érintenek, ezért külön helperben maradnak, hogy a settings modell olvasható legyen. A base.py közvetetten hívja, és csak konfigurációs konzisztenciát ellenőriz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from core.kernel.config.settings_constants import ALLOWED_DEMO_CAPTCHA_PROVIDERS

_POSITIVE_LIMIT_FIELDS = (
    "rate_limit_login_per_minute",
    "rate_limit_login_step1_per_email_per_hour",
    "rate_limit_login_burst_per_10s",
    "rate_limit_login_failure_ban_threshold",
    "rate_limit_login_failure_ban_window_sec",
    "rate_limit_login_failure_ban_hours",
    "platform_admin_max_failed_login_attempts",
    "platform_admin_mfa_attempt_window_minutes",
    "platform_admin_mfa_lock_minutes",
    "platform_admin_mfa_totp_max_attempts_per_user",
    "platform_admin_mfa_totp_max_attempts_per_ip",
    "platform_admin_mfa_recovery_max_attempts_per_user",
    "platform_admin_mfa_recovery_max_attempts_per_ip",
    "ws_chat_max_messages_per_10s",
    "ws_chat_max_message_chars",
    "ws_chat_idle_timeout_sec",
    "ws_chat_max_connections_per_tenant",
    "ws_chat_max_connections_per_user",
    "llm_budget_request_limit_per_minute",
    "llm_budget_prompt_chars_per_minute",
    "llm_budget_concurrency_limit",
    "llm_budget_tenant_daily_tokens",
    "llm_budget_tenant_monthly_tokens",
    "llm_budget_demo_daily_tokens",
    "llm_budget_demo_monthly_tokens",
    "llm_budget_starter_monthly_tokens",
    "llm_budget_global_daily_spend_usd",
    "llm_budget_input_cost_per_1k_tokens_usd",
    "llm_budget_output_cost_per_1k_tokens_usd",
    "llm_budget_estimated_completion_tokens",
    "chat_max_answer_chars",
    "chat_max_input_chars",
    "chat_max_history_items",
    "chat_max_history_chars",
    "chat_max_retrieval_items",
    "chat_max_retrieval_chars",
    "chat_default_max_sources",
    "chat_starter_max_sources",
    "chat_demo_max_sources",
    "chat_demo_max_question_chars",
    "chat_demo_max_history_items",
    "chat_demo_max_history_chars",
    "chat_demo_max_retrieval_items",
    "chat_demo_max_retrieval_chars",
    "channel_default_max_daily_limit",
    "channel_default_max_per_minute_limit",
    "channel_demo_max_daily_limit",
    "channel_demo_max_per_minute_limit",
    "channel_session_max_per_minute",
    "channel_session_max_burst_10s",
    "channel_session_min_interval_ms",
    "channel_session_cookie_max_age_sec",
    "channel_signature_max_skew_sec",
    "platform_event_outbox_backlog_soft_limit",
    "platform_event_handler_timeout_sec",
    "demo_signup_max_per_day",
    "demo_signup_max_per_ip_per_day",
    "demo_signup_max_per_ip_email_per_day",
    "demo_signup_max_per_session_per_day",
    "demo_signup_max_per_email",
    "demo_trial_days",
)


def validate_rate_limits(settings: Any) -> None:
    for field_name in _POSITIVE_LIMIT_FIELDS:
        if getattr(settings, field_name) <= 0:
            raise ValueError(f"{field_name} pozitívnak kell lennie.")
    if settings.channel_session_wait_max_ms < 0:
        raise ValueError("channel_session_wait_max_ms nem lehet negatív.")

    provider = (settings.demo_signup_captcha_provider or "").strip().lower()
    if provider not in ALLOWED_DEMO_CAPTCHA_PROVIDERS:
        raise ValueError("demo_signup_captcha_provider értéke: none, turnstile vagy recaptcha lehet.")
    if settings.demo_signup_require_captcha and provider == "none":
        raise ValueError("demo_signup_require_captcha=True esetén demo_signup_captcha_provider nem lehet 'none'.")


__all__ = ["validate_rate_limits"]
