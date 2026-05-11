import asyncio
# Ez a fájl az adott terület szolgáltatás- és üzleti logikáját tartalmazza.
import inspect
import logging
import re
import threading
import unicodedata
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, Optional

try:
    from openai import AsyncOpenAI
    from openai import APIError, APIConnectionError, APITimeoutError, RateLimitError
except Exception:  # pragma: no cover - optional dependency guard
    AsyncOpenAI = Any  # type: ignore
    APIError = Exception  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    RateLimitError = Exception  # type: ignore

from core.kernel.config import app_settings
from core.kernel.config.environment import get_app_env
from core.platform.contract.observability import increment_metric, log_structured_event, observe_metric
from core.kernel.security.rate_limit import get_rate_limit_redis
from apps.chat.service.pii_depersonalization import PiiDepersonalizationService
from shared.text.language_lexicon import SUPPORTED_LEXICON_LANGUAGES, get_lexicon_terms, get_month_number
from shared.utils import sanitize_log_data

logger = logging.getLogger(__name__)
_AUDIT_ACTION_KNOWLEDGE_PII_DEPERSONALIZED = "knowledge_pii_depersonalized"


def _fold_lexicon_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


class PiiDepersonalizationUnavailableError(RuntimeError):
    """Raised when KB-level PII depersonalization cannot be guaranteed."""


class ChatPolicyViolationError(RuntimeError):
    """Raised when a chat request violates policy rules."""


@dataclass(frozen=True)
class _PermissionSubject:
    id: int | None
    role: str | None
    is_active: bool = True


class ChatService:
    _budget_lock = threading.Lock()
    _budget_state: dict[tuple[str, str], dict[str, int]] = {}
    _INSUFFICIENT_CONTEXT_ANSWER = "Nincs elegendő információ a válaszhoz a kiválasztott tudástár alapján."
    _PII_POLICY_REFUSAL_TEXT = (
        "Az adott név adatvédelmi okból tokenizálva van; a teljes választ a felület automatikusan visszacseréli."
    )
    _MAX_CONVERSATION_HISTORY_MESSAGES = 20
    _MAX_CONVERSATION_HISTORY_CHARS = 2200
    _MAX_CONTEXT_BLOCKS = 1
    _MAX_PRIMARY_ASSERTIONS = 4
    _MAX_SUPPORTING_ASSERTIONS = 3
    _MAX_EVIDENCE_LINES = 3
    _MAX_CONTEXT_CHUNKS = 2
    _MAX_CONTEXT_TEXT_CHARS = 1400
    _MAX_CONTEXT_BLOCK_SNIPPET_CHARS = 520
    _MAX_RETRIEVAL_HISTORY_ITEMS = 4
    _MAX_RETRIEVAL_HISTORY_CHARS = 1000
    _MULTI_KB_PACKET_SCORE_THRESHOLD = 0.45
    _MULTI_KB_BLOCK_SCORE_THRESHOLD = 0.35
    _MULTI_KB_BLOCK_RELATIVE_FLOOR_RATIO = 0.8
    _ENTITY_TOKEN_STOPWORDS = {
        _fold_lexicon_token(token)
        for language_code in SUPPORTED_LEXICON_LANGUAGES
        for token in get_lexicon_terms(language_code, "entity_stopwords")
    }
    _ENTITY_HINT_STOPWORDS = {
        _fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "entity_hint_stopwords")
    }
    _ENTITY_DESCRIPTOR_TERMS = {
        _fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "descriptor_terms")
    }
    _ENTITY_SUFFIXES = get_lexicon_terms("hu", "entity_suffixes", include_fallback=False)
    _QUESTION_NAME_SUFFIXES = get_lexicon_terms("hu", "name_suffixes", include_fallback=False)
    _YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")
    _DATE_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
    _YEAR_MONTH_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})-(0[1-9]|1[0-2])\b")
    _CAP_SEQ_RE = re.compile(r"\b(?:[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)*\b")
    _WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]{3,}")
    _MONTHS = {
        month_name: get_month_number("hu", month_name)
        for month_name in get_lexicon_terms("hu", "time_months", include_fallback=False)
        if get_month_number("hu", month_name) is not None
    }
    _ENTITY_STOPWORDS = {
        token.capitalize()
        for token in get_lexicon_terms("hu", "question_words", include_fallback=False)
    } | {"Mutasd", "Mondd", "Keresd", "Van", "Volt", "Lesz", "A", "Az", "És", "Vagy"}
    _PLACE_SUFFIXES = get_lexicon_terms("hu", "place_suffixes", include_fallback=False)
    _QUESTION_STOPWORDS = {
        _fold_lexicon_token(token)
        for token in get_lexicon_terms("hu", "question_stopwords")
    }
    _PII_ENCODE_UNAVAILABLE_DETAIL = (
        "PII deperszonalizációs szolgáltatás átmenetileg nem érhető el, próbáld újra később."
    )
    _ENUMERATION_POLICY_DETAIL = (
        "A kérés túl általános listázást céloz. Pontosítsd a kérdést konkrét entitással, időszakkal vagy témával."
    )

    @staticmethod
    def _openai_client(**kwargs: Any):
        try:
            from openai import AsyncOpenAI as _AsyncOpenAI
        except Exception as exc:  # pragma: no cover - dependency/environment guard
            raise RuntimeError("Az openai csomag nincs telepitve a chat klienshez.") from exc
        return _AsyncOpenAI(**kwargs)

    def _chat_completion_kwargs(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.chat_model_name,
            "messages": messages,
        }
        create_callable = getattr(getattr(getattr(self.client, "chat", None), "completions", None), "create", None)
        accepts_kwargs = False
        accepted_names: set[str] = set()
        if callable(create_callable):
            try:
                signature = inspect.signature(create_callable)
                accepted_names = set(signature.parameters.keys())
                accepts_kwargs = any(
                    parameter.kind == inspect.Parameter.VAR_KEYWORD
                    for parameter in signature.parameters.values()
                )
            except (TypeError, ValueError):
                accepts_kwargs = True
        else:
            accepts_kwargs = True
        if accepts_kwargs or "max_tokens" in accepted_names:
            payload["max_tokens"] = self._chat_max_tokens
        if self._chat_temperature >= 0 and (accepts_kwargs or "temperature" in accepted_names):
            payload["temperature"] = self._chat_temperature
        return payload

    @staticmethod
    def _coerce_response_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        parts.append(text)
                    continue
                if isinstance(item, dict):
                    for key in ("text", "content", "reasoning"):
                        raw = item.get(key)
                        if isinstance(raw, str) and raw.strip():
                            parts.append(raw.strip())
                            break
            return "\n".join(part for part in parts if part).strip()
        if isinstance(value, dict):
            for key in ("text", "content", "reasoning", "summary"):
                raw = value.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
            return ""
        return str(value).strip()

    def _extract_response_text(self, response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        if message is None:
            return ""
        # Ollama OpenAI-kompatibilis válaszoknál előfordulhat, hogy a content üres,
        # de a reasoning/output_text mező tartalmazza a tényleges kimenetet.
        if isinstance(message, dict):
            for key in ("content", "reasoning", "output_text"):
                text = self._coerce_response_text(message.get(key))
                if text:
                    return text
            return ""
        for key in ("content", "reasoning", "output_text"):
            text = self._coerce_response_text(getattr(message, key, None))
            if text:
                return text
        return ""

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        chat_model: Optional[AsyncOpenAI] = None,
        chat_model_name: str | None = None,
        kb_service: Any = None,
        retrieval_service: Any = None,
        query_parser: Any = None,
        context_builder: Any = None,
        channel_access_service: Any = None,
        pii_depersonalization_service: PiiDepersonalizationService | None = None,
        audit_service: Any = None,
    ):
        if chat_model is None:
            provider = str(getattr(app_settings, "chat_provider", "openai") or "openai").strip().lower()
            if provider == "ollama":
                base_url = str(getattr(app_settings, "ollama_url", "http://localhost:11434") or "http://localhost:11434").rstrip("/")
                api_key = str(getattr(app_settings, "ollama_api_key", "ollama") or "ollama")
                self.client = self._openai_client(base_url=f"{base_url}/v1", api_key=api_key)
            else:
                if not app_settings.openai_api_key:
                    raise ValueError("❌ OPENAI_API_KEY nincs beállítva (config / .env).")
                self.client = self._openai_client(api_key=app_settings.openai_api_key)
        else:
            self.client = chat_model
        provider = str(getattr(app_settings, "chat_provider", "openai") or "openai").strip().lower()
        default_model = (
            str(getattr(app_settings, "ollama_model", "qwen2.5:7b-instruct") or "qwen2.5:7b-instruct")
            if provider == "ollama"
            else str(getattr(app_settings, "chat_model", "gpt-4o-mini") or "gpt-4o-mini")
        )
        self.chat_model_name = str(chat_model_name or default_model)
        self._chat_completion_timeout_sec = max(
            5,
            int(getattr(app_settings, "chat_completion_timeout_sec", 45) or 45),
        )
        self._chat_context_timeout_sec = max(
            5,
            int(getattr(app_settings, "chat_context_timeout_sec", 20) or 20),
        )
        self._chat_max_tokens = max(
            64,
            int(getattr(app_settings, "chat_max_tokens", 220) or 220),
        )
        self._chat_temperature = float(getattr(app_settings, "chat_temperature", 0.2) or 0.2)
        self.kb_service = kb_service
        self.retrieval_service = retrieval_service
        self.query_parser = query_parser
        self.context_builder = context_builder
        self.channel_access_service = channel_access_service
        self.pii_depersonalization_service = pii_depersonalization_service
        self.audit_service = audit_service
        self._recent_query_focus_by_user: dict[int, dict] = {}
        self._llm_budget_request_limit_per_minute = max(
            1,
            int(getattr(app_settings, "llm_budget_request_limit_per_minute", 120) or 120),
        )
        self._llm_budget_prompt_chars_per_minute = max(
            1,
            int(getattr(app_settings, "llm_budget_prompt_chars_per_minute", 120000) or 120000),
        )
        self._llm_budget_concurrency_limit = max(
            1,
            int(getattr(app_settings, "llm_budget_concurrency_limit", 8) or 8),
        )
        self._llm_budget_tenant_daily_tokens = max(
            1,
            int(getattr(app_settings, "llm_budget_tenant_daily_tokens", 120_000) or 120_000),
        )
        self._llm_budget_tenant_monthly_tokens = max(
            1,
            int(getattr(app_settings, "llm_budget_tenant_monthly_tokens", 2_000_000) or 2_000_000),
        )
        self._llm_budget_global_daily_spend_usd = max(
            0.01,
            float(getattr(app_settings, "llm_budget_global_daily_spend_usd", 15.0) or 15.0),
        )
        self._llm_budget_input_cost_per_1k_tokens_usd = max(
            0.00001,
            float(getattr(app_settings, "llm_budget_input_cost_per_1k_tokens_usd", 0.003) or 0.003),
        )
        self._llm_budget_output_cost_per_1k_tokens_usd = max(
            0.00001,
            float(getattr(app_settings, "llm_budget_output_cost_per_1k_tokens_usd", 0.006) or 0.006),
        )
        self._llm_budget_estimated_completion_tokens = max(
            1,
            int(getattr(app_settings, "llm_budget_estimated_completion_tokens", 220) or 220),
        )
        self._chat_max_answer_chars = max(
            120,
            int(getattr(app_settings, "chat_max_answer_chars", 2400) or 2400),
        )

    @staticmethod
    def estimate_prompt_chars(
        *,
        question: str,
        conversation_history: list[dict[str, str]] | None,
        retrieval_history: list[str] | None,
    ) -> int:
        total = len(str(question or ""))
        total += sum(len(str(item.get("content") or item.get("text") or "")) for item in (conversation_history or []) if isinstance(item, dict))
        total += sum(len(str(item or "")) for item in (retrieval_history or []))
        return max(1, total)

    @staticmethod
    def _rollback_llm_redis_budget(
        redis_client,
        *,
        req_key: str,
        chars_key: str,
        inflight_key: str,
        day_tokens_key: str,
        month_tokens_key: str,
        global_spend_key: str,
        prompt_units: int,
        estimated_tokens: int,
        estimated_cost_micro: int,
    ) -> None:
        try:
            pipe = redis_client.pipeline()
            pipe.decr(req_key, 1)
            pipe.decrby(chars_key, prompt_units)
            pipe.decr(inflight_key, 1)
            pipe.decrby(day_tokens_key, estimated_tokens)
            pipe.decrby(month_tokens_key, estimated_tokens)
            pipe.decrby(global_spend_key, estimated_cost_micro)
            pipe.execute()
        except Exception:
            logger.warning("LLM budget rollback failed.")

    def acquire_llm_budget(
        self,
        *,
        tenant_id: int | None,
        scope: str,
        prompt_chars: int,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        tenant_key = str(int(tenant_id or 0))
        scope_key = str(scope or "default").strip().lower() or "default"
        is_demo_scope = ":demo" in scope_key or scope_key.endswith("demo")
        is_starter_scope = ":starter" in scope_key or scope_key.endswith("starter")
        effective_daily_tokens = self._llm_budget_tenant_daily_tokens
        effective_monthly_tokens = self._llm_budget_tenant_monthly_tokens
        if is_demo_scope:
            effective_daily_tokens = min(
                effective_daily_tokens,
                max(1, int(getattr(app_settings, "llm_budget_demo_daily_tokens", 30_000) or 30_000)),
            )
            effective_monthly_tokens = min(
                effective_monthly_tokens,
                max(1, int(getattr(app_settings, "llm_budget_demo_monthly_tokens", 150_000) or 150_000)),
            )
        elif is_starter_scope:
            effective_monthly_tokens = min(
                effective_monthly_tokens,
                max(1, int(getattr(app_settings, "llm_budget_starter_monthly_tokens", 900_000) or 900_000)),
            )
        now_utc = datetime.now(UTC)
        minute_bucket = int(now_utc.timestamp() // 60)
        day_bucket = now_utc.strftime("%Y%m%d")
        month_bucket = now_utc.strftime("%Y%m")
        prompt_units = max(1, int(prompt_chars or 1))
        prompt_tokens = max(1, int(round(prompt_units / 4.0)))
        completion_tokens = min(self._chat_max_tokens, self._llm_budget_estimated_completion_tokens)
        estimated_tokens = max(1, prompt_tokens + completion_tokens)
        estimated_cost_usd = (
            (prompt_tokens / 1000.0) * self._llm_budget_input_cost_per_1k_tokens_usd
            + (completion_tokens / 1000.0) * self._llm_budget_output_cost_per_1k_tokens_usd
        )
        redis_client = get_rate_limit_redis()
        fail_closed = bool(getattr(app_settings, "llm_budget_fail_closed_without_redis", True))
        try:
            env = get_app_env()
        except Exception:
            env = "dev"
        if redis_client is None and fail_closed and env == "prod":
            return False, "LLM budget szolgáltatás átmenetileg nem elérhető.", None
        if redis_client is not None:
            req_key = f"rl:llm:req:{tenant_key}:{scope_key}:{minute_bucket}"
            chars_key = f"rl:llm:chars:{tenant_key}:{scope_key}:{minute_bucket}"
            inflight_key = f"rl:llm:inflight:{tenant_key}:{scope_key}"
            day_tokens_key = f"rl:llm:tokens:day:{tenant_key}:{day_bucket}"
            month_tokens_key = f"rl:llm:tokens:month:{tenant_key}:{month_bucket}"
            global_spend_key = f"rl:llm:spend:day:{day_bucket}"
            estimated_cost_micro = int(round(estimated_cost_usd * 1_000_000))
            try:
                pipe = redis_client.pipeline()
                pipe.incr(req_key, 1)
                pipe.expire(req_key, 120)
                pipe.incrby(chars_key, prompt_units)
                pipe.expire(chars_key, 120)
                pipe.incr(inflight_key, 1)
                pipe.expire(inflight_key, 180)
                pipe.incrby(day_tokens_key, estimated_tokens)
                pipe.expire(day_tokens_key, 3 * 24 * 3600)
                pipe.incrby(month_tokens_key, estimated_tokens)
                pipe.expire(month_tokens_key, 40 * 24 * 3600)
                pipe.incrby(global_spend_key, estimated_cost_micro)
                pipe.expire(global_spend_key, 3 * 24 * 3600)
                (
                    req_count,
                    _,
                    chars_count,
                    _,
                    inflight_count,
                    _,
                    day_tokens,
                    _,
                    month_tokens,
                    _,
                    global_spend_micro,
                    _,
                ) = pipe.execute()
                if int(req_count or 0) > self._llm_budget_request_limit_per_minute:
                    self._rollback_llm_redis_budget(
                        redis_client,
                        req_key=req_key,
                        chars_key=chars_key,
                        inflight_key=inflight_key,
                        day_tokens_key=day_tokens_key,
                        month_tokens_key=month_tokens_key,
                        global_spend_key=global_spend_key,
                        prompt_units=prompt_units,
                        estimated_tokens=estimated_tokens,
                        estimated_cost_micro=estimated_cost_micro,
                    )
                    return False, "LLM kéréslimit elérve ebben a percben.", None
                if int(chars_count or 0) > self._llm_budget_prompt_chars_per_minute:
                    self._rollback_llm_redis_budget(
                        redis_client,
                        req_key=req_key,
                        chars_key=chars_key,
                        inflight_key=inflight_key,
                        day_tokens_key=day_tokens_key,
                        month_tokens_key=month_tokens_key,
                        global_spend_key=global_spend_key,
                        prompt_units=prompt_units,
                        estimated_tokens=estimated_tokens,
                        estimated_cost_micro=estimated_cost_micro,
                    )
                    return False, "LLM prompt limit elérve ebben a percben.", None
                if int(inflight_count or 0) > self._llm_budget_concurrency_limit:
                    self._rollback_llm_redis_budget(
                        redis_client,
                        req_key=req_key,
                        chars_key=chars_key,
                        inflight_key=inflight_key,
                        day_tokens_key=day_tokens_key,
                        month_tokens_key=month_tokens_key,
                        global_spend_key=global_spend_key,
                        prompt_units=prompt_units,
                        estimated_tokens=estimated_tokens,
                        estimated_cost_micro=estimated_cost_micro,
                    )
                    return False, "Túl sok párhuzamos LLM kérés folyamatban.", None
                if int(day_tokens or 0) > effective_daily_tokens:
                    self._rollback_llm_redis_budget(
                        redis_client,
                        req_key=req_key,
                        chars_key=chars_key,
                        inflight_key=inflight_key,
                        day_tokens_key=day_tokens_key,
                        month_tokens_key=month_tokens_key,
                        global_spend_key=global_spend_key,
                        prompt_units=prompt_units,
                        estimated_tokens=estimated_tokens,
                        estimated_cost_micro=estimated_cost_micro,
                    )
                    return False, "Napi AI token keret elérve a tenantnál.", None
                if int(month_tokens or 0) > effective_monthly_tokens:
                    self._rollback_llm_redis_budget(
                        redis_client,
                        req_key=req_key,
                        chars_key=chars_key,
                        inflight_key=inflight_key,
                        day_tokens_key=day_tokens_key,
                        month_tokens_key=month_tokens_key,
                        global_spend_key=global_spend_key,
                        prompt_units=prompt_units,
                        estimated_tokens=estimated_tokens,
                        estimated_cost_micro=estimated_cost_micro,
                    )
                    return False, "Havi AI token keret elérve a tenantnál.", None
                if (int(global_spend_micro or 0) / 1_000_000.0) > self._llm_budget_global_daily_spend_usd:
                    self._rollback_llm_redis_budget(
                        redis_client,
                        req_key=req_key,
                        chars_key=chars_key,
                        inflight_key=inflight_key,
                        day_tokens_key=day_tokens_key,
                        month_tokens_key=month_tokens_key,
                        global_spend_key=global_spend_key,
                        prompt_units=prompt_units,
                        estimated_tokens=estimated_tokens,
                        estimated_cost_micro=estimated_cost_micro,
                    )
                    return False, "A mai globális AI költségkeret betelt.", None
                return True, "", {"backend": "redis", "inflight_key": inflight_key}
            except Exception:
                if fail_closed and env == "prod":
                    logger.error("LLM budget Redis check failed in production fail-closed mode.")
                    return False, "LLM budget szolgáltatás átmenetileg nem elérhető.", None
                logger.warning("LLM budget Redis check failed, fallback to in-memory.")
        key = (tenant_key, scope_key)
        with self._budget_lock:
            state = self._budget_state.get(key) or {
                "minute": minute_bucket,
                "day": day_bucket,
                "month": month_bucket,
                "requests": 0,
                "chars": 0,
                "inflight": 0,
                "day_tokens": 0,
                "month_tokens": 0,
            }
            if int(state.get("minute") or minute_bucket) != minute_bucket:
                state["minute"] = minute_bucket
                state["requests"] = 0
                state["chars"] = 0
            if str(state.get("day") or day_bucket) != day_bucket:
                state["day"] = day_bucket
                state["day_tokens"] = 0
            if str(state.get("month") or month_bucket) != month_bucket:
                state["month"] = month_bucket
                state["month_tokens"] = 0
            if int(state["requests"]) + 1 > self._llm_budget_request_limit_per_minute:
                return False, "LLM kéréslimit elérve ebben a percben.", None
            if int(state["chars"]) + prompt_units > self._llm_budget_prompt_chars_per_minute:
                return False, "LLM prompt limit elérve ebben a percben.", None
            if int(state["inflight"]) >= self._llm_budget_concurrency_limit:
                return False, "Túl sok párhuzamos LLM kérés folyamatban.", None
            if int(state.get("day_tokens") or 0) + estimated_tokens > effective_daily_tokens:
                return False, "Napi AI token keret elérve a tenantnál.", None
            if int(state.get("month_tokens") or 0) + estimated_tokens > effective_monthly_tokens:
                return False, "Havi AI token keret elérve a tenantnál.", None
            state["requests"] = int(state["requests"]) + 1
            state["chars"] = int(state["chars"]) + prompt_units
            state["inflight"] = int(state["inflight"]) + 1
            state["day_tokens"] = int(state.get("day_tokens") or 0) + estimated_tokens
            state["month_tokens"] = int(state.get("month_tokens") or 0) + estimated_tokens
            self._budget_state[key] = state
        return True, "", {"backend": "memory", "key": key}

    def release_llm_budget(self, reservation: dict[str, Any] | None) -> None:
        if not reservation:
            return
        backend = str(reservation.get("backend") or "")
        if backend == "redis":
            redis_client = get_rate_limit_redis()
            if redis_client is None:
                return
            inflight_key = str(reservation.get("inflight_key") or "").strip()
            if not inflight_key:
                return
            try:
                redis_client.decr(inflight_key, 1)
            except Exception:
                logger.debug("LLM budget inflight release failed (redis).")
            return
        key = reservation.get("key")
        if not isinstance(key, tuple) or len(key) != 2:
            return
        with self._budget_lock:
            state = self._budget_state.get(key)
            if not state:
                return
            state["inflight"] = max(0, int(state.get("inflight") or 0) - 1)

    # Ez a metódus a(z) capture_retrieval_feedback logikáját valósítja meg.
    def capture_retrieval_feedback(
        self,
        trace_id: str,
        helpful: bool | None = None,
        context_useful: bool | None = None,
        wrong_entity_resolution: bool = False,
        wrong_time_slice: bool = False,
        note: str | None = None,
    ) -> dict:
        if self.retrieval_service is None or not hasattr(self.retrieval_service, "capture_feedback"):
            return {"status": "skipped", "reason": "feedback_service_not_available"}
        return self.retrieval_service.capture_feedback(
            trace_id=trace_id,
            helpful=helpful,
            context_useful=context_useful,
            wrong_entity_resolution=wrong_entity_resolution,
            wrong_time_slice=wrong_time_slice,
            note=note,
        )

    def download_answer_source(
        self,
        *,
        query_run_id: str,
        source_id: str,
        user_id: int | None = None,
        user_role: str | None = None,
    ) -> dict | None:
        if self.kb_service is None or not hasattr(self.kb_service, "get_query_source_download"):
            return None
        download = self.kb_service.get_query_source_download(query_run_id, source_id)
        if download is None:
            return None
        corpus_uuid = str(download.get("corpus_uuid") or "").strip()
        if corpus_uuid and user_id is not None and hasattr(self.kb_service, "user_can_use"):
            subject = _PermissionSubject(id=user_id, role=user_role, is_active=True)
            if not self.kb_service.user_can_use(corpus_uuid, user_id, subject):
                raise PermissionError("Nincs jogosultság a megadott tudástár használatához.")
        return download

    def download_answer_context(
        self,
        *,
        query_run_id: str,
        user_id: int | None = None,
        user_role: str | None = None,
    ) -> dict | None:
        if self.kb_service is None or not hasattr(self.kb_service, "get_query_context_download"):
            return None
        download = self.kb_service.get_query_context_download(query_run_id)
        if download is None:
            return None
        corpus_uuid = str(download.get("corpus_uuid") or "").strip()
        if corpus_uuid and user_id is not None and hasattr(self.kb_service, "user_can_use"):
            subject = _PermissionSubject(id=user_id, role=user_role, is_active=True)
            if not self.kb_service.user_can_use(corpus_uuid, user_id, subject):
                raise PermissionError("Nincs jogosultság a megadott tudástár használatához.")
        return download

    # Ez a metódus a(z) utcnow_naive logikáját valósítja meg.
    @staticmethod
    def _utcnow_naive() -> datetime:
        from core.kernel.clock import utc_now_naive

        return utc_now_naive()

    # Ez a metódus a(z) dedupe_keep_order logikáját valósítja meg.
    @staticmethod
    def _dedupe_keep_order(values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = " ".join(str(value or "").strip().split())
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _fold_text(value: str | None) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        return "".join(char for char in normalized if not unicodedata.combining(char)).lower()

    # Ez a metódus a(z) sanitize_debug_text logikáját valósítja meg.
    @staticmethod
    def _sanitize_debug_text(value: Any) -> str:
        text = str(value or "")
        if not text:
            return ""
        text = re.sub(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", "[redacted_email]", text)
        text = re.sub(r"\b(?:\+?\d[\d\s().-]{6,}\d)\b", "[redacted_phone]", text)
        text = re.sub(r"\b\d{6,}\b", "[redacted_number]", text)
        return text[:400] + ("..." if len(text) > 400 else "")

    # Ez a metódus a(z) sanitize_debug_value logikáját valósítja meg.
    @classmethod
    def _sanitize_debug_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): cls._sanitize_debug_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._sanitize_debug_value(v) for v in value]
        if isinstance(value, tuple):
            return [cls._sanitize_debug_value(v) for v in value]
        if isinstance(value, str):
            return cls._sanitize_debug_text(value)
        return value

    @classmethod
    def _conversation_history_context(cls, conversation_history: list[dict[str, str]] | None) -> str:
        if not conversation_history:
            return ""
        rows: list[str] = []
        total = 0
        for item in reversed(conversation_history[-cls._MAX_CONVERSATION_HISTORY_MESSAGES :]):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            text = " ".join(str(item.get("content") or item.get("text") or "").strip().split())
            if not text:
                continue
            prefix = "Felhasználó" if role == "user" else "Asszisztens"
            line = f"{prefix}: {text[:1200]}"
            if total + len(line) > cls._MAX_CONVERSATION_HISTORY_CHARS:
                break
            rows.append(line)
            total += len(line)
        rows.reverse()
        return "\n".join(rows)

    @classmethod
    def _retrieval_history_context(cls, retrieval_history: list[str] | None) -> str:
        if not retrieval_history:
            return ""
        rows: list[str] = []
        total = 0
        for item in retrieval_history[: cls._MAX_RETRIEVAL_HISTORY_ITEMS]:
            text = " ".join(str(item or "").strip().split())
            if not text:
                continue
            line = f"- {text[:300]}"
            if total + len(line) > cls._MAX_RETRIEVAL_HISTORY_CHARS:
                break
            rows.append(line)
            total += len(line)
        return "\n".join(rows)

    # Ez a metódus normalizálja a(z) place surface logikáját.
    @classmethod
    def _normalize_place_surface(cls, value: str) -> str:
        raw = " ".join(str(value or "").strip().split())
        if not raw:
            return ""
        if cls._fold_text(raw) in cls._QUESTION_STOPWORDS:
            return raw
        lower = raw.lower()
        for suffix in sorted(cls._PLACE_SUFFIXES, key=len, reverse=True):
            if lower.endswith(suffix) and len(raw) > len(suffix) + 2:
                return raw[: len(raw) - len(suffix)]
        return raw

    @classmethod
    def _normalize_entity_surface(cls, value: str) -> str:
        raw = " ".join(str(value or "").strip().split())
        if not raw:
            return ""
        lower = raw.lower()
        for suffix in sorted(cls._ENTITY_SUFFIXES, key=len, reverse=True):
            if lower.endswith(suffix) and len(raw) > len(suffix) + 2:
                candidate = raw[: len(raw) - len(suffix)]
                if candidate and candidate[:1].isalpha():
                    return candidate
        return raw

    @classmethod
    def _encode_question_using_context_mappings(
        cls,
        *,
        question: str,
        context_mappings: list[dict[str, Any]] | None,
    ) -> str:
        text = str(question or "")
        if not text:
            return text
        mappings = [item for item in (context_mappings or []) if isinstance(item, dict)]
        if not mappings:
            return text
        encoded = text
        for item in mappings:
            token = str(item.get("token") or "").strip()
            preview = str(item.get("original_preview") or "").strip()
            if not token or not preview:
                continue
            folded_preview = cls._fold_text(preview)
            if not folded_preview or len(folded_preview) < 3:
                continue
            escaped = re.escape(preview)
            direct_pattern = re.compile(rf"(?iu)\b{escaped}\b")
            if direct_pattern.search(encoded):
                encoded = direct_pattern.sub(token, encoded)
                continue
            # Ragozott névalak fallback: pl. "péternek" -> [person_1]
            suffix_pattern = re.compile(
                rf"(?iu)\b{escaped}(?:{'|'.join(map(re.escape, cls._QUESTION_NAME_SUFFIXES))})\b"
            )
            encoded = suffix_pattern.sub(token, encoded)
        return encoded

    # Ez a metódus a(z) extract_entity_candidates logikáját valósítja meg.
    @classmethod
    def _extract_entity_candidates(cls, question: str) -> list[str]:
        out: list[str] = []
        text = str(question or "")
        explicit_pairs = re.findall(
            r"\b([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,})\s+([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,})\b",
            text,
        )
        for left, right in explicit_pairs:
            left_normalized = cls._normalize_entity_surface(left)
            right_normalized = cls._normalize_entity_surface(right)
            left_folded_raw = cls._fold_text(left)
            right_folded_raw = cls._fold_text(right)
            left_folded_normalized = cls._fold_text(left_normalized or left)
            right_folded_normalized = cls._fold_text(right_normalized or right)
            if (
                left_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or left_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
            ):
                continue
            pair = f"{left_normalized or left} {right_normalized or right}".strip()
            if len(pair) >= 5 and pair.lower() not in {"milyen programot", "utolso kerdes", "utolsó kérdés"}:
                out.append(pair)
        for match in cls._CAP_SEQ_RE.findall(question or ""):
            value = " ".join(str(match).split())
            if not value:
                continue
            tokens = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,}", value)
            while tokens:
                first_raw_folded = cls._fold_text(tokens[0])
                first_normalized_folded = cls._fold_text(cls._normalize_entity_surface(tokens[0]) or tokens[0])
                if first_raw_folded in cls._ENTITY_TOKEN_STOPWORDS or first_normalized_folded in cls._ENTITY_TOKEN_STOPWORDS:
                    tokens.pop(0)
                else:
                    break
            if not tokens:
                continue
            value = " ".join(tokens)
            if value in cls._ENTITY_STOPWORDS:
                continue
            out.append(value)
        # Kisbetűs, több tokenes márkanév/cégnév jellegű kérdések (pl. "sk trend")
        lowered = re.findall(r"\b[a-z0-9áéíóöőúüű]{2,}\b", text.lower())
        for idx in range(len(lowered) - 1):
            left_normalized = cls._normalize_entity_surface(lowered[idx])
            right_normalized = cls._normalize_entity_surface(lowered[idx + 1])
            left_folded_raw = cls._fold_text(lowered[idx])
            right_folded_raw = cls._fold_text(lowered[idx + 1])
            left_folded_normalized = cls._fold_text(left_normalized or lowered[idx])
            right_folded_normalized = cls._fold_text(right_normalized or lowered[idx + 1])
            if (
                left_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_raw in cls._ENTITY_TOKEN_STOPWORDS
                or left_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
                or right_folded_normalized in cls._ENTITY_TOKEN_STOPWORDS
            ):
                continue
            pair = f"{left_normalized or lowered[idx]} {right_normalized or lowered[idx + 1]}".strip()
            if pair in {"milyen programot", "programot keszitett", "programot készített"}:
                continue
            if len(pair) >= 5:
                out.append(pair)
        return cls._dedupe_keep_order(out)

    @classmethod
    def _strong_entity_candidates(cls, query_profile: dict[str, Any]) -> list[str]:
        out: list[str] = []
        lexical_hints = [str(item or "").strip() for item in (query_profile.get("lexical_focus_terms") or [])]
        for raw in query_profile.get("entity_candidates") or []:
            text = " ".join(str(raw or "").strip().split())
            if not text:
                continue
            raw_tokens = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]{2,}", text)
            if not raw_tokens:
                continue
            has_capitalized_token = any(token[:1].isupper() for token in raw_tokens)
            tokens: list[str] = []
            for token in raw_tokens:
                normalized = cls._normalize_entity_surface(token)
                folded = cls._fold_text(normalized or token)
                if not folded or folded in cls._ENTITY_TOKEN_STOPWORDS:
                    continue
                tokens.append(folded)
            if not tokens:
                continue
            if len(tokens) == 1 and not has_capitalized_token:
                single = tokens[0]
                if single in cls._ENTITY_HINT_STOPWORDS or single in cls._ENTITY_DESCRIPTOR_TERMS:
                    # Egyetlen, kisbetűs attribútumszó (pl. "szeme") ne legyen "strong entity".
                    continue
            if not has_capitalized_token and any(token in cls._ENTITY_DESCRIPTOR_TERMS for token in tokens):
                # "útlevél száma", "személyi azonosító" jellegű attribútumkifejezések ne kényszerítsenek entity-gate-et.
                continue
            normalized = " ".join(tokens)
            if normalized and normalized not in out:
                out.append(normalized)
        # Ha az entity parser gyenge (pl. kérdőszót fogott), lexical hintből próbálunk nevet visszaállítani.
        for hint in lexical_hints:
            token = re.sub(r"[^A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]", "", hint)
            if not token:
                continue
            folded_token = cls._fold_text(token)
            if not folded_token or folded_token in cls._ENTITY_TOKEN_STOPWORDS:
                continue
            normalized_hint = cls._fold_text(cls._normalize_entity_surface(token))
            if not normalized_hint or normalized_hint in cls._ENTITY_TOKEN_STOPWORDS:
                continue
            if normalized_hint in cls._ENTITY_HINT_STOPWORDS:
                continue
            # Csak olyan hintet emelünk át, amin látszik a raglevágás (pl. "péternek" -> "péter").
            if normalized_hint == folded_token:
                continue
            if normalized_hint not in out:
                out.append(normalized_hint)
        return out

    @classmethod
    def _text_matches_strong_entity(cls, text: str, strong_entities: list[str]) -> bool:
        if not strong_entities:
            return True
        haystack = cls._fold_text(text)
        if not haystack:
            return False
        hay_tokens = {
            token
            for token in re.findall(r"[a-z0-9áéíóöőúüű]{2,}", haystack)
            if token
        }
        if not hay_tokens:
            return False

        def one_edit_or_less(left: str, right: str) -> bool:
            if left == right:
                return True
            if not left or not right:
                return False
            len_left, len_right = len(left), len(right)
            if abs(len_left - len_right) > 1:
                return False
            if len_left == len_right:
                mismatch = sum(1 for idx in range(len_left) if left[idx] != right[idx])
                return mismatch <= 1
            if len_left > len_right:
                left, right = right, left
                len_left, len_right = len_right, len_left
            # right hosszabb pontosan 1 karakterrel
            i = 0
            j = 0
            used_skip = False
            while i < len_left and j < len_right:
                if left[i] == right[j]:
                    i += 1
                    j += 1
                    continue
                if used_skip:
                    return False
                used_skip = True
                j += 1
            return True

        for entity in strong_entities:
            entity_tokens = [
                token
                for token in re.findall(r"[a-z0-9áéíóöőúüű]{2,}", cls._fold_text(entity))
                if token and token not in cls._ENTITY_TOKEN_STOPWORDS
            ]
            if not entity_tokens:
                continue
            if len(entity_tokens) == 1 and (
                entity_tokens[0] in hay_tokens
                or any(one_edit_or_less(entity_tokens[0], hay_token) for hay_token in hay_tokens)
            ):
                return True
            if len(entity_tokens) > 1 and all(
                token in hay_tokens or any(one_edit_or_less(token, hay_token) for hay_token in hay_tokens)
                for token in entity_tokens
            ):
                return True
        return False

    # Ez a metódus a(z) extract_place_candidates logikáját valósítja meg.
    @classmethod
    def _extract_place_candidates(cls, question: str) -> list[str]:
        words = re.findall(r"\b[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+\b", question or "")
        out: list[str] = []
        for word in words:
            normalized = cls._normalize_place_surface(word)
            if normalized != word and normalized[:1].isupper():
                if cls._fold_text(word) in cls._QUESTION_STOPWORDS:
                    continue
                if cls._fold_text(normalized) in cls._QUESTION_STOPWORDS:
                    continue
                out.append(normalized)
        for match in cls._CAP_SEQ_RE.findall(question or ""):
            low = f" {(question or '').lower()} "
            value = " ".join(str(match).split())
            if not value:
                continue
            probe = value.lower()
            if any(
                token in low
                for token in (
                    f" {probe.lower()} ban ", f" {probe.lower()} ben ", f" {probe.lower()} on ",
                    f" {probe.lower()} en ", f" {probe.lower()} ön ", f" {probe.lower()} területén ",
                    f" {probe.lower()} városban ", f" {probe.lower()} megyében ",
                )
            ):
                out.append(value)
        return cls._dedupe_keep_order(out)

    # Ez a metódus a(z) extract_time_hints logikáját valósítja meg.
    @classmethod
    def _extract_time_hints(cls, question: str) -> tuple[list[str], dict[str, datetime | None]]:
        text = str(question or "")
        low = text.lower()
        now = cls._utcnow_naive()
        candidates: list[str] = []
        window = {"from": None, "to": None}
        for year, month, day in cls._DATE_RE.findall(text):
            candidates.append(f"{year}-{month}-{day}")
            dt = datetime(int(year), int(month), int(day), 0, 0, 0)
            window["from"] = dt
            window["to"] = dt.replace(hour=23, minute=59, second=59)
            return cls._dedupe_keep_order(candidates), window
        for year, month in cls._YEAR_MONTH_RE.findall(text):
            candidates.append(f"{year}-{month}")
            start = datetime(int(year), int(month), 1, 0, 0, 0)
            if int(month) == 12:
                end = datetime(int(year), 12, 31, 23, 59, 59)
            else:
                end = datetime(int(year), int(month) + 1, 1, 0, 0, 0) - timedelta(seconds=1)
            window["from"] = start
            window["to"] = end
            return cls._dedupe_keep_order(candidates), window
        years = cls._YEAR_RE.findall(text)
        if years:
            year = int(years[0])
            candidates.extend(years)
            window["from"] = datetime(year, 1, 1, 0, 0, 0)
            window["to"] = datetime(year, 12, 31, 23, 59, 59)
            return cls._dedupe_keep_order(candidates), window
        for month_name, month_num in cls._MONTHS.items():
            if month_name in low:
                candidates.append(month_name)
                year = now.year
                year_match = cls._YEAR_RE.search(text)
                if year_match:
                    year = int(year_match.group(1))
                start = datetime(year, month_num, 1, 0, 0, 0)
                if month_num == 12:
                    end = datetime(year, 12, 31, 23, 59, 59)
                else:
                    end = datetime(year, month_num + 1, 1, 0, 0, 0) - timedelta(seconds=1)
                window["from"] = start
                window["to"] = end
                return cls._dedupe_keep_order(candidates), window
        if "tavaly" in low:
            year = now.year - 1
            candidates.append("tavaly")
            window["from"] = datetime(year, 1, 1, 0, 0, 0)
            window["to"] = datetime(year, 12, 31, 23, 59, 59)
        elif "idén" in low:
            candidates.append("idén")
            window["from"] = datetime(now.year, 1, 1, 0, 0, 0)
            window["to"] = datetime(now.year, 12, 31, 23, 59, 59)
        elif "most" in low or "jelenleg" in low:
            candidates.append("most")
            window["from"] = datetime(now.year, now.month, 1, 0, 0, 0)
            if now.month == 12:
                window["to"] = datetime(now.year, 12, 31, 23, 59, 59)
            else:
                window["to"] = datetime(now.year, now.month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
        return cls._dedupe_keep_order(candidates), window

    # Ez a metódus a(z) derive_intent logikáját valósítja meg.
    @classmethod
    def _derive_intent(cls, question: str, parsed: dict) -> str:
        low = str(question or "").lower()
        if any(x in low for x in ("időrend", "timeline", "mikor", "meddig", "mettől", "előtte", "utána")):
            return "timeline"
        if any(x in low for x in ("kapcsolat", "viszony", "kapcsolódik", "kapcsolódnak", "köze van")):
            return "relation"
        if any(x in low for x in ("milyen", "mennyi", "mekkora", "státusz", "állapot", "attribútum")):
            return "attribute"
        if any(x in low for x in ("mit csinál", "mit csinált", "mi történt", "ki dolgozik", "ki vezet")):
            return "activity"
        entities = parsed.get("entity_candidates") or []
        predicates = parsed.get("predicate_candidates") or []
        if predicates and entities:
            return "activity"
        return str(parsed.get("intent") or "summary")

    @classmethod
    def _looks_broad_enumeration_request(cls, question: str) -> bool:
        q = str(question or "").strip().lower()
        if not q:
            return False
        signals = (
            "összes tudás",
            "minden tudás",
            "listázd az összes",
            "listázz mindent",
            "minden adat",
            "teljes tudásbázis",
            "all knowledge",
            "list everything",
            "dump all",
            "show all records",
            "export all",
        )
        return any(token in q for token in signals)

    # Ez a metódus felépíti a(z) hint terms logikáját.
    @classmethod
    def _build_hint_terms(cls, question: str, parsed: dict) -> list[str]:
        low = str(question or "").lower()
        tokens = [token for token in cls._WORD_RE.findall(low) if token not in cls._QUESTION_STOPWORDS]
        blocked = {
            str(x).lower()
            for key in ("entity_candidates", "place_candidates", "time_candidates")
            for x in (parsed.get(key) or [])
        }
        out = [
            token for token in tokens
            if token not in blocked and len(token) >= 4
        ]
        return cls._dedupe_keep_order(out[:8])

    # Ez a metódus a(z) enrich_parsed_query logikáját valósítja meg.
    @classmethod
    def _enrich_parsed_query(cls, question: str, parsed: dict) -> dict:
        parsed = dict(parsed or {})
        parsed.setdefault("raw_query", question)
        parsed["entity_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("entity_candidates") or []) + cls._extract_entity_candidates(question)
        )
        parsed["place_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("place_candidates") or []) + cls._extract_place_candidates(question)
        )
        time_candidates, time_window = cls._extract_time_hints(question)
        parsed["time_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("time_candidates") or []) + time_candidates
        )
        if parsed.get("query_valid_time_from") is None and time_window.get("from") is not None:
            parsed["query_valid_time_from"] = time_window["from"]
        if parsed.get("query_valid_time_to") is None and time_window.get("to") is not None:
            parsed["query_valid_time_to"] = time_window["to"]
        parsed["valid_time_window"] = parsed.get("valid_time_window") or {
            "from": parsed.get("query_valid_time_from").isoformat() if parsed.get("query_valid_time_from") else None,
            "to": parsed.get("query_valid_time_to").isoformat() if parsed.get("query_valid_time_to") else None,
        }
        parsed["time_window"] = parsed.get("time_window") or parsed["valid_time_window"]
        parsed["intent"] = cls._derive_intent(question, parsed)
        hint_terms = cls._build_hint_terms(question, parsed)
        parsed["lexical_focus_terms"] = cls._dedupe_keep_order(
            list(parsed.get("lexical_focus_terms") or [])
            + list(parsed.get("predicate_candidates") or [])
            + list(parsed.get("attribute_candidates") or [])
            + list(parsed.get("relation_candidates") or [])
            + hint_terms
        )
        parsed["entity_heavy"] = bool(parsed.get("entity_heavy")) or len(parsed["entity_candidates"]) >= 2
        parsed["predicate_heavy"] = bool(parsed.get("predicate_heavy")) or bool(parsed.get("predicate_candidates"))
        if not parsed.get("retrieval_mode") or parsed.get("retrieval_mode") == "assertion_first":
            intent = str(parsed.get("intent") or "summary")
            if intent == "timeline":
                parsed["retrieval_mode"] = "timeline_first"
            elif intent in {"relation", "attribute"} or parsed.get("entity_heavy"):
                parsed["retrieval_mode"] = "entity_first"
            else:
                parsed["retrieval_mode"] = "assertion_first"
        representation_parts = [
            str(parsed.get("raw_query") or question),
            " ".join(parsed.get("entity_candidates") or []),
            " ".join(parsed.get("place_candidates") or []),
            " ".join(parsed.get("time_candidates") or []),
            " ".join(parsed.get("predicate_candidates") or []),
            " ".join(parsed.get("relation_candidates") or []),
            " ".join(parsed.get("attribute_candidates") or []),
            " ".join(parsed.get("lexical_focus_terms") or []),
        ]
        normalized_representation = " ".join(part.strip() for part in representation_parts if str(part).strip())
        parsed["normalized_query_text"] = parsed.get("normalized_query_text") or normalized_representation
        parsed["lexical_query_text"] = parsed.get("lexical_query_text") or normalized_representation
        parsed["query_embedding_text"] = parsed.get("query_embedding_text") or normalized_representation
        parser_audit = dict(parsed.get("parser_audit") or {})
        parser_audit["chat_enrichment"] = {
            "entity_candidates": parsed.get("entity_candidates") or [],
            "time_candidates": parsed.get("time_candidates") or [],
            "place_candidates": parsed.get("place_candidates") or [],
            "intent": parsed.get("intent"),
            "retrieval_mode": parsed.get("retrieval_mode"),
            "lexical_focus_terms": parsed.get("lexical_focus_terms") or [],
            "normalized_query_text": parsed.get("normalized_query_text"),
        }
        parsed["parser_audit"] = parser_audit
        return parsed

    # Ez a metódus a(z) is_followup logikáját valósítja meg.
    def _is_followup(self, user_id: int | None, query_focus: dict) -> bool:
        if user_id is None:
            return False
        prev = self._recent_query_focus_by_user.get(int(user_id))
        now = self._utcnow_naive()
        self._recent_query_focus_by_user[int(user_id)] = {
            "at": now,
            "entity_candidates": query_focus.get("entity_candidates") or [],
            "valid_time_window": query_focus.get("valid_time_window") or query_focus.get("time_window") or {},
        }
        if not prev:
            return False
        prev_at = prev.get("at")
        if not isinstance(prev_at, datetime):
            return False
        if (now - prev_at).total_seconds() > 300:
            return False
        prev_entities = {str(x).lower() for x in (prev.get("entity_candidates") or [])}
        curr_entities = {str(x).lower() for x in (query_focus.get("entity_candidates") or [])}
        if prev_entities.intersection(curr_entities):
            return True
        prev_tw = prev.get("valid_time_window") or prev.get("time_window") or {}
        curr_tw = query_focus.get("valid_time_window") or query_focus.get("time_window") or {}
        return bool(prev_tw.get("from") and curr_tw.get("from") and prev_tw.get("from") == curr_tw.get("from"))

    async def _build_context_packet(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> dict:
        """Retrieval context packet előállítása chathez."""
        if self.kb_service is None:
            return {
                "query_focus": {},
                "top_assertions": [],
                "evidence_sentences": [],
                "source_chunks": [],
                "related_entities": [],
                "scoring_summary": {},
            }
        permission_subject = (
            _PermissionSubject(id=user_id, role=user_role, is_active=True)
            if user_id is not None
            else None
        )
        if kb_uuid and user_id is not None and not self.kb_service.user_can_use(kb_uuid, user_id, permission_subject):
            raise PermissionError("Nincs jogosultság a megadott tudástár használatához.")
        t_parse = perf_counter()
        parsed = self.query_parser.parse(question) if self.query_parser is not None else {"intent": "summary"}
        parsed = self._enrich_parsed_query(question, parsed)
        parsed["parse_time_ms"] = round((perf_counter() - t_parse) * 1000.0, 2)

        if not kb_uuid and user_id is not None:
            packet = await self._build_multi_kb_context_packet(
                question=question,
                user_id=user_id,
                user_role=user_role,
                permission_subject=permission_subject,
                parsed=parsed,
                debug=debug,
            )
            packet["query_focus"] = parsed
            packet["parser_audit"] = parsed.get("parser_audit") or {}
            packet.setdefault("scoring_summary", {})
            packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
            packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
            packet["is_followup"] = self._is_followup(user_id, parsed)
            return packet

        if user_id is not None:
            if self.retrieval_service is not None and hasattr(self.retrieval_service, "build_context_for_chat"):
                packet = await self.retrieval_service.build_context_for_chat(
                    question=question,
                    current_user_id=user_id,
                    current_user_role=user_role,
                    parsed_query=parsed,
                    kb_uuid=kb_uuid,
                    debug=debug,
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet
            if hasattr(self.kb_service, "build_context_for_chat"):
                packet = await self.kb_service.build_context_for_chat(
                    question=question,
                    current_user_id=user_id,
                    current_user_role=user_role,
                    parsed_query=parsed,
                    kb_uuid=kb_uuid,
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet
            if hasattr(self.kb_service, "build_chat_context"):
                packet = await self.kb_service.build_chat_context(
                    question=question,
                    current_user_id=user_id,
                    current_user_role=user_role,
                    parsed_query=parsed,
                    kb_uuid=kb_uuid,
                    debug=debug,
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet

        assertions = []
        if user_id is not None:
            search_assertions = getattr(self.kb_service, "search_assertions", None)
            if search_assertions is None:
                return {
                    "query_focus": parsed,
                    "parser_audit": parsed.get("parser_audit") or {},
                    "top_assertions": [],
                    "evidence_sentences": [],
                    "source_chunks": [],
                    "related_entities": [],
                    "scoring_summary": {"latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)}},
                    "is_followup": self._is_followup(user_id, parsed),
                }
            assertions = search_assertions(
                current_user_id=user_id,
                current_user_role=user_role,
                predicates=None,
                entity_ids=None,
                limit=18,
            )
        packet = (
            self.context_builder.build_context_packet(assertions, [], [], [])
            if self.context_builder is not None
            else {"top_assertions": assertions}
        )
        packet["query_focus"] = parsed
        packet["parser_audit"] = parsed.get("parser_audit") or {}
        packet.setdefault("scoring_summary", {})
        packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
        packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
        packet["is_followup"] = self._is_followup(user_id, parsed)
        return packet

    async def _build_single_kb_context_packet(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        parsed: dict,
        kb_uuid: str,
        debug: bool,
    ) -> dict:
        if self.retrieval_service is not None and hasattr(self.retrieval_service, "build_context_for_chat"):
            return await self.retrieval_service.build_context_for_chat(
                question=question,
                current_user_id=user_id,
                current_user_role=user_role,
                parsed_query=parsed,
                kb_uuid=kb_uuid,
                debug=debug,
            )
        if hasattr(self.kb_service, "build_context_for_chat"):
            return await self.kb_service.build_context_for_chat(
                question=question,
                current_user_id=user_id,
                current_user_role=user_role,
                parsed_query=parsed,
                kb_uuid=kb_uuid,
            )
        if hasattr(self.kb_service, "build_chat_context"):
            return await self.kb_service.build_chat_context(
                question=question,
                current_user_id=user_id,
                current_user_role=user_role,
                parsed_query=parsed,
                kb_uuid=kb_uuid,
                debug=debug,
            )
        return {}

    async def _build_multi_kb_context_packet(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        permission_subject: _PermissionSubject | None,
        parsed: dict,
        debug: bool,
    ) -> dict:
        list_all = getattr(self.kb_service, "list_all", None)
        if not callable(list_all):
            return {
                "query_focus": parsed,
                "top_assertions": [],
                "evidence_sentences": [],
                "source_chunks": [],
                "related_entities": [],
                "scoring_summary": {"latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)}},
            }
        corpora = list_all(current_user_id=user_id, current_user=permission_subject)
        candidates = [
            item
            for item in corpora
            if str(getattr(item, "uuid", "") or "").strip()
            and getattr(item, "deleted_at", None) is None
        ]
        diagnostics: dict[str, Any] = {
            "candidate_kb_count": len(candidates),
            "processed_kb_count": 0,
            "context_kb_count": 0,
            "permission_skipped_kb_count": 0,
            "failed_kb_count": 0,
            "empty_context_kb_count": 0,
            "ready_index_kb_count": 0,
            "candidate_kb_uuids": [],
            "context_kb_uuids": [],
            "empty_context_kb_uuids": [],
        }
        packets: list[dict] = []
        has_ready_index_candidate = False
        kb_names: dict[str, str] = {}
        for corpus in candidates:
            current_kb_uuid = str(getattr(corpus, "uuid", "") or "").strip()
            if not current_kb_uuid:
                continue
            diagnostics["candidate_kb_uuids"].append(current_kb_uuid)
            kb_names[current_kb_uuid] = str(getattr(corpus, "name", "") or current_kb_uuid)
            try:
                packet = await self._build_single_kb_context_packet(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    parsed=parsed,
                    kb_uuid=current_kb_uuid,
                    debug=debug,
                )
            except PermissionError:
                diagnostics["permission_skipped_kb_count"] += 1
                continue
            except Exception:
                diagnostics["failed_kb_count"] += 1
                logger.debug("chat.multi_kb_context_failed", extra={"kb_uuid": current_kb_uuid}, exc_info=True)
                continue
            if not isinstance(packet, dict):
                continue
            diagnostics["processed_kb_count"] += 1
            has_context_text = bool(self._llm_context_text_from_packet(packet).strip())
            is_ready_candidate = (not bool(packet.get("no_ready_index_build"))) or has_context_text
            if is_ready_candidate:
                has_ready_index_candidate = True
                diagnostics["ready_index_kb_count"] += 1
            packet["kb_uuid"] = current_kb_uuid
            packet["corpus_uuid"] = current_kb_uuid
            packet["kb_name"] = kb_names[current_kb_uuid]
            self._stamp_packet_kb(packet, current_kb_uuid, kb_names[current_kb_uuid])
            if has_context_text:
                diagnostics["context_kb_count"] += 1
                diagnostics["context_kb_uuids"].append(current_kb_uuid)
                packets.append(packet)
            else:
                diagnostics["empty_context_kb_count"] += 1
                diagnostics["empty_context_kb_uuids"].append(current_kb_uuid)
        return self._merge_context_packets(
            packets,
            kb_names=kb_names,
            parsed=parsed,
            no_ready_index_build=not has_ready_index_candidate,
            multi_kb_diagnostics=diagnostics,
        )

    @staticmethod
    def _packet_score(packet: dict) -> float:
        score = 0.0
        for key in ("synthesis_confidence", "retrieval_confidence", "confidence"):
            try:
                score = max(score, float(packet.get(key) or 0.0))
            except (TypeError, ValueError):
                pass
        try:
            score += min(1.0, float((packet.get("scoring_summary") or {}).get("result_count") or 0) / 10.0)
        except (TypeError, ValueError):
            pass
        return score

    @staticmethod
    def _packet_retrieval_confidence(packet: dict[str, Any]) -> float:
        for value in (
            packet.get("retrieval_confidence"),
            (packet.get("scoring_summary") or {}).get("retrieval_confidence"),
            packet.get("confidence"),
        ):
            try:
                parsed = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return 0.0

    @classmethod
    def _packet_has_strong_context_blocks(
        cls,
        packet: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> bool:
        blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        if not isinstance(blocks, list):
            return False
        for block in blocks:
            if not isinstance(block, dict):
                continue
            score = cls._candidate_block_score(block, strong_entities=strong_entities)
            if score >= cls._MULTI_KB_BLOCK_SCORE_THRESHOLD:
                return True
        return False

    @classmethod
    def _packet_has_entity_matching_fallback_rows(
        cls,
        packet: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> bool:
        if not strong_entities:
            return False
        for key in ("source_chunks", "evidence_sentences", "top_assertions"):
            for row in packet.get(key) or []:
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("subject") or row.get("entity_name") or ""),
                        str(row.get("text") or row.get("snippet") or row.get("claim_text") or ""),
                    ]
                ).strip()
                if text and cls._text_matches_strong_entity(text, strong_entities):
                    return True
        return False

    @classmethod
    def _candidate_block_score(
        cls,
        row: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> float:
        if strong_entities:
            block_text = " ".join(
                [
                    str(row.get("subject") or row.get("primary_subject") or ""),
                    str(row.get("snippet") or row.get("text") or ""),
                ]
            )
            if not cls._text_matches_strong_entity(block_text, strong_entities):
                return 0.0
        try:
            return float(row.get("match_score") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _dynamic_multi_kb_block_floor(
        cls,
        packets: list[dict[str, Any]],
        *,
        strong_entities: list[str],
    ) -> float:
        scores: list[float] = []
        for packet in packets:
            for key in ("context_blocks", "matched_semantic_blocks"):
                for row in packet.get(key) or []:
                    if not isinstance(row, dict):
                        continue
                    score = cls._candidate_block_score(row, strong_entities=strong_entities)
                    if score > 0:
                        scores.append(score)
        if not scores:
            return cls._MULTI_KB_BLOCK_SCORE_THRESHOLD
        top_score = max(scores)
        return max(
            cls._MULTI_KB_BLOCK_SCORE_THRESHOLD,
            top_score * cls._MULTI_KB_BLOCK_RELATIVE_FLOOR_RATIO,
        )

    @staticmethod
    def _stamp_packet_kb(packet: dict, kb_uuid: str, kb_name: str) -> None:
        for key in ("source_chunks", "evidence_sentences", "top_assertions", "matched_chunks", "matched_claims"):
            for row in packet.get(key) or []:
                if isinstance(row, dict):
                    row.setdefault("kb_uuid", kb_uuid)
                    row.setdefault("kb_name", kb_name)
        for key in ("context_blocks", "matched_semantic_blocks"):
            for row in packet.get(key) or []:
                if isinstance(row, dict):
                    row.setdefault("kb_uuid", kb_uuid)
                    row.setdefault("kb_name", kb_name)
        for row in packet.get("evidence_summary") or []:
            if isinstance(row, dict):
                row.setdefault("kb_uuid", kb_uuid)
                row.setdefault("kb_name", kb_name)

    def _merge_context_packets(
        self,
        packets: list[dict],
        *,
        kb_names: dict[str, str],
        parsed: dict,
        no_ready_index_build: bool = False,
        multi_kb_diagnostics: dict[str, Any] | None = None,
    ) -> dict:
        if not packets:
            return {
                "query_focus": parsed,
                "top_assertions": [],
                "evidence_sentences": [],
                "source_chunks": [],
                "related_entities": [],
                "matched_semantic_blocks": [],
                "matched_chunks": [],
                "matched_claims": [],
                "kb_scope": "all",
                "kb_names": kb_names,
                "answer_mode": "no_answer",
                "no_ready_index_build": bool(no_ready_index_build),
                "multi_kb_diagnostics": multi_kb_diagnostics or {},
                "scoring_summary": {
                    "result_count": 0,
                    "kb_count": len(kb_names),
                    "kb_qualified_count": 0,
                    "latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)},
                },
            }
        strong_entities = self._strong_entity_candidates(parsed)
        ordered = sorted(packets, key=self._packet_score, reverse=True)
        qualified: list[dict[str, Any]] = []
        fallback_to_non_entity_gate = False
        for packet in ordered:
            has_entity_signal = (
                self._packet_has_strong_context_blocks(packet, strong_entities=strong_entities)
                or self._packet_has_entity_matching_fallback_rows(packet, strong_entities=strong_entities)
            )
            if strong_entities:
                if has_entity_signal:
                    qualified.append(packet)
                continue
            if (
                self._packet_retrieval_confidence(packet) >= self._MULTI_KB_PACKET_SCORE_THRESHOLD
                and has_entity_signal
            ):
                qualified.append(packet)
        if strong_entities and not qualified:
            # Ne essen szét a flow, ha az entity-gate túl szigorú (pl. attribútum-jellegű follow-up kérdés).
            fallback_to_non_entity_gate = True
            qualified = [
                packet
                for packet in ordered
                if self._packet_retrieval_confidence(packet) >= self._MULTI_KB_PACKET_SCORE_THRESHOLD
                and self._packet_has_strong_context_blocks(packet, strong_entities=[])
            ]
        effective_strong_entities = [] if fallback_to_non_entity_gate else strong_entities
        dynamic_block_floor = self._dynamic_multi_kb_block_floor(
            qualified,
            strong_entities=effective_strong_entities,
        )
        if not qualified:
            return {
                "query_focus": parsed,
                "top_assertions": [],
                "evidence_sentences": [],
                "source_chunks": [],
                "related_entities": [],
                "matched_semantic_blocks": [],
                "matched_chunks": [],
                "matched_claims": [],
                "kb_scope": "all",
                "kb_names": kb_names,
                "answer_mode": "no_answer",
                "answer_text": "",
                "no_ready_index_build": bool(no_ready_index_build),
                "dynamic_block_score_threshold": dynamic_block_floor,
                "multi_kb_diagnostics": multi_kb_diagnostics or {},
                "scoring_summary": {
                    "result_count": 0,
                    "kb_count": len(kb_names),
                    "kb_qualified_count": 0,
                    "latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)},
                },
            }
        merged: dict[str, Any] = {
            "query_focus": parsed,
            "kb_scope": "all",
            "kb_uuid": "",
            "corpus_uuid": "",
            "kb_names": kb_names,
            "answer_mode": "summary",
            "answer_text": "",
            "query_run_id": None,
            "no_ready_index_build": bool(no_ready_index_build),
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": [],
            "related_entities": [],
            "context_blocks": [],
            "matched_semantic_blocks": [],
            "matched_chunks": [],
            "matched_claims": [],
            "evidence_summary": [],
            "cited_source_ids": [],
            "source_ids": [],
            "dynamic_block_score_threshold": dynamic_block_floor,
            "multi_kb_diagnostics": multi_kb_diagnostics or {},
            "scoring_summary": {"result_count": 0, "kb_count": len(kb_names), "kb_qualified_count": len(qualified), "latency_ms": {}},
        }
        if fallback_to_non_entity_gate:
            merged["filtered_out_reason"] = [
                "entity_gate_fallback: strict entity szűrés nem adott találatot, ezért packet-score alapú fallback futott"
            ]
        qualified_kb_uuids = {
            str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
            for packet in qualified
            if str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        }
        if len(qualified_kb_uuids) == 1:
            effective_kb_uuid = next(iter(qualified_kb_uuids))
            merged["kb_uuid"] = effective_kb_uuid
            merged["corpus_uuid"] = effective_kb_uuid
            # Ha a végső context egyetlen KB-ból áll, vigyük át a PII beállítást is.
            for packet in qualified:
                packet_kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
                if packet_kb_uuid != effective_kb_uuid:
                    continue
                if "pii_depersonalization_enabled" in packet:
                    merged["pii_depersonalization_enabled"] = bool(packet.get("pii_depersonalization_enabled"))
                if str(packet.get("personal_data_sensitivity") or "").strip():
                    merged["personal_data_sensitivity"] = str(packet.get("personal_data_sensitivity")).strip()
                break
        for packet in qualified:
            packet_selected_source_ids: set[str] = set()
            for key, limit in (
                ("context_blocks", 8),
                ("matched_semantic_blocks", 8),
                ("source_chunks", 8),
                ("evidence_sentences", 8),
                ("matched_chunks", 12),
                ("matched_claims", 12),
                ("evidence_summary", 12),
            ):
                current = merged.setdefault(key, [])
                for row in packet.get(key) or []:
                    if not isinstance(row, dict):
                        continue
                    if key in {"context_blocks", "matched_semantic_blocks"}:
                        block_score = self._candidate_block_score(row, strong_entities=effective_strong_entities)
                        if block_score < dynamic_block_floor:
                            continue
                        source_id = str(row.get("source_id") or row.get("source_point_id") or "").strip()
                        if source_id:
                            packet_selected_source_ids.add(source_id)
                    elif key in {"matched_chunks", "matched_claims"} and effective_strong_entities:
                        row_text = " ".join(
                            [
                                str(row.get("entity_name") or row.get("subject") or ""),
                                str(row.get("claim_text") or row.get("display_claim_text") or ""),
                            ]
                        )
                        if not self._text_matches_strong_entity(row_text, effective_strong_entities):
                            continue
                    elif key in {"source_chunks", "evidence_sentences", "evidence_summary"} and effective_strong_entities:
                        row_source_id = str(
                            row.get("source_id")
                            or row.get("source_point_id")
                            or row.get("point_id")
                            or row.get("id")
                            or ""
                        ).strip()
                        row_text = " ".join(
                            [
                                str(row.get("subject") or row.get("entity_name") or ""),
                                str(row.get("text") or row.get("snippet") or row.get("claim_text") or ""),
                            ]
                        ).strip()
                        source_match = bool(packet_selected_source_ids) and row_source_id in packet_selected_source_ids
                        text_match = bool(row_text) and self._text_matches_strong_entity(row_text, effective_strong_entities)
                        if not source_match and not text_match:
                            continue
                    if len(current) < limit:
                        current.append(row)
            for source_id in [*(packet.get("cited_source_ids") or []), *(packet.get("source_ids") or [])]:
                text = str(source_id or "").strip()
                if text and text not in merged["cited_source_ids"]:
                    merged["cited_source_ids"].append(text)
                    merged["source_ids"].append(text)
            summary = packet.get("scoring_summary") or {}
            merged["scoring_summary"]["result_count"] += int(summary.get("result_count") or 0)
        if int(merged["scoring_summary"].get("result_count") or 0) <= 0:
            semantic_rows = merged.get("context_blocks") or merged.get("matched_semantic_blocks") or []
            if semantic_rows:
                merged["scoring_summary"]["result_count"] = len(semantic_rows)
        return merged

    async def _safe_context_text(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> tuple[str, bool]:
        """Hibatűrő context építés.

        Visszatérés:
        - (context_text, False): context build sikerült
        - ("", True): context build hibára futott
        """
        try:
            packet = await asyncio.wait_for(
                self._build_context_packet(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    kb_uuid=kb_uuid,
                    debug=debug,
                ),
                timeout=self._chat_context_timeout_sec,
            )
            return self._llm_context_text_from_packet(packet), False
        except PermissionError:
            raise
        except asyncio.TimeoutError:
            logger.warning(
                "Knowledge context építés timeout (%ss).",
                self._chat_context_timeout_sec,
                exc_info=True,
            )
            return "", True
        except Exception as e:
            logger.warning("Knowledge context építés sikertelen: %s", e, exc_info=True)
            return "", True

    def _context_text_from_packet(self, packet: dict) -> str:
        """Tömör szöveges context építése packetből."""
        context_blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        block_lines = []
        for index, block in enumerate(context_blocks[: self._MAX_CONTEXT_BLOCKS], start=1):
            text = str(block.get("snippet") or block.get("text") or "").strip()
            if not text:
                continue
            if len(text) > self._MAX_CONTEXT_BLOCK_SNIPPET_CHARS:
                text = f"{text[: self._MAX_CONTEXT_BLOCK_SNIPPET_CHARS].rstrip()}..."
            subject = str(block.get("subject") or block.get("primary_subject") or "-").strip() or "-"
            space = str(block.get("space") or block.get("primary_space") or "-").strip() or "-"
            time = str(block.get("time") or block.get("primary_time") or "-").strip() or "-"
            block_id = str(block.get("block_id") or block.get("id") or "").strip()
            block_lines.append(
                f"- [B{index}] block_id={block_id}; alany={subject}; hely={space}; idő={time}\n{text}"
            )
        primary = packet.get("primary_assertions") or packet.get("seed_assertions") or packet.get("summary_assertions") or packet.get("top_assertions") or []
        supporting = packet.get("supporting_assertions") or packet.get("expanded_assertions") or []
        primary_lines = []
        for row in primary[: self._MAX_PRIMARY_ASSERTIONS]:
            text = row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or ""
            if text:
                primary_lines.append(f"- [A] {text}")
        # Ha nincs assertion, chunk/sentence fallback (pl. jogleírás, statisztika).
        sentence_lines = packet.get("evidence_sentences") or []
        chunk_lines = packet.get("source_chunks") or []
        if not primary_lines and (sentence_lines or chunk_lines):
            for row in chunk_lines[: self._MAX_CONTEXT_CHUNKS]:
                text = row.get("text") or row.get("payload", {}).get("text") or ""
                if text:
                    primary_lines.append(f"- [C] {text}")
            for row in sentence_lines[: self._MAX_EVIDENCE_LINES]:
                if len(primary_lines) >= self._MAX_PRIMARY_ASSERTIONS:
                    break
                text = row.get("text") or row.get("payload", {}).get("text") or ""
                if text and not any(t in "\n".join(primary_lines) for t in [text[:50]]):
                    primary_lines.append(f"- [S] {text}")
        if not primary_lines and not block_lines:
            return ""
        related_entities = packet.get("related_entities") or []
        related_places = packet.get("related_places") or []
        time_slices = packet.get("time_slice_groups") or []
        timeline_sequence = packet.get("timeline_sequence") or []
        conflicts = packet.get("conflict_bundles") or []
        refinements = packet.get("refinement_bundles") or []
        supporting_lines = []
        primary_ids = {
            str(row.get("id"))
            for row in primary[:6]
            if row.get("id") is not None
        }
        for row in supporting[: self._MAX_SUPPORTING_ASSERTIONS]:
            if str(row.get("id")) in primary_ids:
                continue
            text = row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or ""
            if text:
                supporting_lines.append(f"- [SA] {text}")
        evidence_lines = []
        for row in sentence_lines[: self._MAX_EVIDENCE_LINES]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                prefix = "[S]" if str(row.get("context_role") or "").startswith("primary") else "[SE]"
                evidence_lines.append(f"- {prefix} {text}")
        chunk_text_lines = []
        for row in chunk_lines[: self._MAX_CONTEXT_CHUNKS]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                prefix = "[C]" if str(row.get("context_role") or "") == "primary_chunk" else "[CF]"
                chunk_text_lines.append(f"- {prefix} {text}")
        query_focus = packet.get("query_focus") or {}
        entity_lines = [
            f"- [E] {x.get('canonical_name') or x.get('entity_id')}"
            for x in related_entities[:5]
        ]
        place_lines = [
            f"- [P] {x.get('place_key')} ({len(x.get('assertion_ids') or [])} állítás)"
            for x in related_places[:5]
            if x.get("place_key")
        ]
        slice_lines = [
            f"- [T] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]}..{str(x.get('valid_time_to') or x.get('time_to') or '')[:10]} ({len(x.get('assertion_ids') or [])} állítás)"
            for x in time_slices[:4]
        ]
        timeline_lines = [
            f"- [TL] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]} {x.get('text') or ''}"
            for x in timeline_sequence[:6]
        ]
        conflict_lines = [
            f"- [CF] {x.get('focus_key')} ({len(x.get('items') or [])} ellentmondó állítás)"
            for x in conflicts[:3]
        ]
        refinement_lines = [
            f"- [RF] {x.get('focus_key')} ({len(x.get('assertion_ids') or [])} finomított állítás)"
            for x in refinements[:3]
        ]
        intent = str(query_focus.get("intent", "summary"))
        base = (
            f"Intent: {intent}\n"
            f"Retrieval mode: {query_focus.get('retrieval_mode', 'assertion_first')}\n"
            + ("Knowledge blocks:\n" + "\n".join(block_lines) + "\n" if block_lines else "")
            + ("Primary assertions:\n" + "\n".join(primary_lines) if primary_lines else "")
            + ("\nSupporting assertions:\n" + "\n".join(supporting_lines) if supporting_lines else "")
            + ("\nEvidence sentences:\n" + "\n".join(evidence_lines) if evidence_lines else "")
            + ("\nContext chunks:\n" + "\n".join(chunk_text_lines) if chunk_text_lines else "")
            + ("\nRelated entities:\n" + "\n".join(entity_lines) if entity_lines else "")
            + ("\nPlaces:\n" + "\n".join(place_lines) if place_lines else "")
            + ("\nTime slices:\n" + "\n".join(slice_lines) if slice_lines else "")
            + ("\nConflicts:\n" + "\n".join(conflict_lines) if conflict_lines else "")
            + ("\nRefinements:\n" + "\n".join(refinement_lines) if refinement_lines else "")
        )
        if intent == "timeline":
            return (base + ("\nChronology:\n" + "\n".join(timeline_lines) if timeline_lines else ""))[: self._MAX_CONTEXT_TEXT_CHARS]
        if intent == "comparison":
            cmp = packet.get("comparison_summary") or {}
            return (
                base
                + "\nComparison focus:\n"
                + f"- left={cmp.get('left_target')} ({cmp.get('left_count', 0)})\n"
                + f"- right={cmp.get('right_target')} ({cmp.get('right_count', 0)})"
            )[: self._MAX_CONTEXT_TEXT_CHARS]
        if intent == "relation":
            return (base + "\nRelation guidance: koncentrálj a kapcsolati állításokra és bizonyítékra.")[: self._MAX_CONTEXT_TEXT_CHARS]
        if intent == "attribute":
            return (base + "\nAttribute guidance: emeld ki az attribútum és státusz jellegű állításokat.")[: self._MAX_CONTEXT_TEXT_CHARS]
        return base[: self._MAX_CONTEXT_TEXT_CHARS]

    def _llm_context_text_from_packet(self, packet: dict) -> str:
        """LLM-nek küldhető minimál context: kizárólag chunk snippetek.

        Nem tartalmazza a knowledge block meta mezőket (alany/hely/idő), assertion listákat
        és egyéb magas szintű összefoglalókat, így kisebb az esélye a nyers PII átszivárgásának.
        """
        chunk_lines = packet.get("source_chunks") or []
        chunk_text_lines: list[str] = []
        seen_chunk_texts: set[str] = set()
        for row in chunk_lines[: self._MAX_CONTEXT_CHUNKS]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            text = str(text or "").strip()
            if not text:
                continue
            if len(text) > self._MAX_CONTEXT_BLOCK_SNIPPET_CHARS:
                text = f"{text[: self._MAX_CONTEXT_BLOCK_SNIPPET_CHARS].rstrip()}..."
            dedupe_key = " ".join(text.lower().split())
            if dedupe_key in seen_chunk_texts:
                continue
            seen_chunk_texts.add(dedupe_key)
            chunk_text_lines.append(f"- {text}")
        if not chunk_text_lines:
            return ""
        return ("Context chunks:\n" + "\n".join(chunk_text_lines))[: self._MAX_CONTEXT_TEXT_CHARS]

    def _build_sources_from_packet(self, packet: dict) -> list[dict]:
        """Forráslista összeállítása a context packetből."""
        rows = []
        context_blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        blocks_by_source: dict[str, dict] = {}
        for block in context_blocks:
            if not isinstance(block, dict):
                continue
            source_id = str(block.get("source_id") or "").strip()
            if not source_id or source_id in blocks_by_source:
                continue
            blocks_by_source[source_id] = block
        context_source_ids = {
            str(block.get("source_id") or "").strip()
            for block in context_blocks
            if isinstance(block, dict) and str(block.get("source_id") or "").strip()
        }
        for key in ["source_chunks", "evidence_sentences", "top_assertions"]:
            rows.extend(packet.get(key) or [])
        fallback_kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        fallback_source_ids: list[str] = []
        for value in [*(packet.get("cited_source_ids") or []), *(packet.get("source_ids") or [])]:
            text = str(value or "").strip()
            if text and text not in fallback_source_ids:
                fallback_source_ids.append(text)
        for item in packet.get("evidence_summary") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("source_id") or "").strip()
            if text and text not in fallback_source_ids:
                fallback_source_ids.append(text)
        for block in packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []:
            if not isinstance(block, dict):
                continue
            text = str(block.get("source_id") or "").strip()
            if text and text not in fallback_source_ids:
                fallback_source_ids.append(text)
        seen: set[tuple[str, str, str]] = set()
        out: list[dict] = []
        for row in rows:
            kb_uuid = str(row.get("kb_uuid") or "").strip()
            kb_name = str(row.get("kb_name") or (packet.get("kb_names") or {}).get(kb_uuid) or "").strip()
            point_id = str(
                row.get("source_point_id")
                or row.get("source_id")
                or row.get("id")
                or row.get("point_id")
                or ""
            ).strip()
            source_id = str(row.get("source_id") or "").strip()
            has_source_metadata = bool(
                row.get("display_type")
                or row.get("file_ref")
                or row.get("created_by_label")
                or row.get("created_by") is not None
            )
            if not source_id and has_source_metadata:
                source_id = point_id
            if not source_id and row.get("build_id") and not has_source_metadata:
                continue
            if not source_id:
                source_id = point_id
            if not kb_uuid or not point_id or not source_id:
                continue
            # UI szinten egy forrás egyszer jelenjen meg: azonos cím+snippet duplikátumokat összevonjuk
            # akkor is, ha eltérő technikai source_id alá kerültek.
            title_raw = str(row.get("source_document_title") or "").strip()
            title_key = " ".join(title_raw.lower().split())
            snippet_value = str(
                row.get("text")
                or row.get("snippet")
                or row.get("payload", {}).get("text")
                or ""
            ).strip()
            snippet_key = " ".join(snippet_value.lower().split())
            source_type_key = str(row.get("source_type") or "").strip().lower()
            display_type_key = str(row.get("display_type") or "").strip().lower()
            is_chat_text_training = (
                source_type_key == "text"
                and (
                    "chatből tanított szöveg" in title_key
                    or "gepel" in display_type_key
                    or "gépel" in display_type_key
                )
            )
            # Chatből tanított többször ismétlődő, azonos snippeteket egy forrásnak tekintjük.
            display_key = snippet_key if is_chat_text_training and snippet_key else f"{title_key}|{snippet_key}".strip("|")
            if not display_key:
                display_key = source_id
            item_key = (kb_uuid, display_key, str(row.get("display_type") or "").strip().lower())
            if item_key in seen:
                continue
            seen.add(item_key)
            out.append(
                {
                    "kb_uuid": kb_uuid,
                    "kb_name": self._sanitize_debug_text(kb_name),
                    "point_id": point_id,
                    "source_id": source_id,
                    "title": self._sanitize_debug_text(row.get("source_document_title") or ""),
                    "snippet": self._sanitize_debug_text(
                        (
                            blocks_by_source.get(source_id, {}).get("snippet")
                            or blocks_by_source.get(source_id, {}).get("text")
                            or row.get("text")
                            or row.get("snippet")
                            or ""
                        )
                    ),
                    "source_type": self._sanitize_debug_text(row.get("source_type") or ""),
                    "file_ref": self._sanitize_debug_text(row.get("file_ref") or "") or None,
                    "display_type": self._sanitize_debug_text(row.get("display_type") or ""),
                    "created_by": row.get("created_by"),
                    "created_by_label": self._sanitize_debug_text(row.get("created_by_label") or ""),
                    # ISO dátumot ne redaktáljuk, különben a frontend nem tudja parse-olni.
                    "created_at": str(row.get("created_at") or "").strip() or None,
                }
            )
            if len(out) >= 8:
                break
        if not out and fallback_kb_uuid:
            for source_id in fallback_source_ids[:8]:
                out.append(
                    {
                        "kb_uuid": fallback_kb_uuid,
                        "kb_name": self._sanitize_debug_text((packet.get("kb_names") or {}).get(fallback_kb_uuid) or ""),
                        "point_id": source_id,
                        "source_id": source_id,
                        "title": f"Forrás {source_id[:8]}",
                        "snippet": "",
                        "source_type": "",
                        "file_ref": None,
                        "display_type": "",
                        "created_by": None,
                        "created_by_label": "",
                        "created_at": None,
                    }
                )
        return out

    @staticmethod
    def _is_knowledge_answer(packet: dict) -> bool:
        answer_text = str(packet.get("answer_text") or "").strip()
        answer_mode = str(packet.get("answer_mode") or "no_answer").strip()
        return bool(answer_text and answer_mode and answer_mode != "no_answer")

    @staticmethod
    def _chat_evidence(packet: dict) -> list[dict]:
        evidence = packet.get("evidence_summary")
        if isinstance(evidence, list):
            return [dict(item) for item in evidence if isinstance(item, dict)]
        query_debug = packet.get("query_debug") if isinstance(packet.get("query_debug"), dict) else {}
        evidence = query_debug.get("evidence")
        if isinstance(evidence, list):
            return [dict(item) for item in evidence if isinstance(item, dict)]
        return []

    @staticmethod
    def _chat_confidence(packet: dict) -> float:
        value = packet.get("synthesis_confidence")
        if value is None and isinstance(packet.get("query_debug"), dict):
            value = packet["query_debug"].get("synthesis_confidence")
        try:
            return round(max(0.0, min(1.0, float(value or 0.0))), 4)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _looks_hungarian_question(question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ("á", "é", "í", "ó", "ö", "ő", "ú", "ü", "ű", " mi ", " mit ", "milyen", "hogyan", "hol", "mennyi", "kérlek"))

    @staticmethod
    def _looks_english_template_answer(answer: str) -> bool:
        lowered = f" {answer.lower()} "
        return any(
            marker in lowered
            for marker in (
                " the ",
                " currently ",
                " historically ",
                " i found ",
                " direct answer ",
                " related information ",
            )
        )

    @classmethod
    def _should_return_direct_knowledge_answer(cls, packet: dict, *, question: str = "") -> bool:
        if not cls._is_knowledge_answer(packet):
            return False
        answer_text = str(packet.get("answer_text") or "")
        if cls._looks_hungarian_question(question) and cls._looks_english_template_answer(answer_text):
            return False
        answer_mode = str(packet.get("answer_mode") or "no_answer").strip()
        if answer_mode == "summary":
            return False
        return cls._chat_confidence(packet) >= 0.75

    def _knowledge_payload(
        self,
        *,
        packet: dict,
        debug: bool,
        question: str = "",
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
    ) -> dict:
        sources = self._build_sources_from_packet(packet)
        context_preview = self._context_text_from_packet(packet)
        answer_text = str(packet.get("answer_text") or "").strip()
        encoded_answer_text = answer_text
        restored_pii_spans: list[dict[str, Any]] = []
        pii_enabled, pii_sensitivity, _ = self._kb_pii_settings(packet=packet or {}, kb_uuid=None)
        pii_corpus_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        if answer_text and pii_enabled and pii_corpus_uuid and self.pii_depersonalization_service is not None:
            try:
                encoded_answer_text = self.pii_depersonalization_service.encode_text(
                    corpus_uuid=pii_corpus_uuid,
                    text=answer_text,
                    enabled=True,
                    sensitivity=pii_sensitivity,
                ).text
            except Exception:
                encoded_answer_text = answer_text
        if (
            answer_text
            and pii_enabled
            and self.pii_depersonalization_service is not None
            and hasattr(self.pii_depersonalization_service, "detect_plain_spans")
        ):
            try:
                restored_pii_spans = list(
                    self.pii_depersonalization_service.detect_plain_spans(
                        text=answer_text,
                        enabled=True,
                        sensitivity=pii_sensitivity,
                    )
                    or []
                )
            except Exception:
                logger.debug("chat.knowledge_pii_span_detection_failed", exc_info=True)
        messages = self._build_messages(
            question=question,
            context_text=context_preview,
            conversation_history=conversation_history,
            retrieval_history=retrieval_history,
        )
        query_profile = packet.get("query_profile") or (packet.get("query_debug") or {}).get("query_profile") or packet.get("query_focus") or {}
        matched_chunks = packet.get("matched_chunks") or []
        matched_claims = packet.get("matched_claims") or []
        context_blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        return {
            "answer": answer_text,
            "query_run_id": str(packet.get("query_run_id") or "").strip() or None,
            "answer_mode": str(packet.get("answer_mode") or "no_answer"),
            "answer_source": "knowledge",
            "confidence": self._chat_confidence(packet),
            "evidence": self._chat_evidence(packet),
            "cited_claim_ids": packet.get("cited_claim_ids") or [],
            "cited_sentence_ids": packet.get("cited_sentence_ids") or [],
            "cited_source_ids": packet.get("cited_source_ids") or packet.get("source_ids") or [],
            "query_profile": query_profile,
            "matched_chunks": matched_chunks,
            "claims": matched_claims,
            "context_blocks": context_blocks,
            "sources": sources,
            "encoded_prompt_context": "",
            "restored_pii_spans": restored_pii_spans,
            "prompt_context": self._build_prompt_context_payload(
                question=question,
                messages=messages,
                conversation_history=conversation_history,
                retrieval_history=retrieval_history,
                packet=packet or {},
                context_text=context_preview,
                encoded_answer_text=encoded_answer_text,
            ),
            "debug": (
                self._build_debug_payload(packet=packet or {}, context_text=context_preview, sources=sources)
                if debug
                else None
            ),
        }

    # Ez a metódus felépíti a(z) debug payload logikáját.
    def _build_debug_payload(self, packet: dict, context_text: str, sources: list[dict]) -> dict:
        top_assertions = (
            packet.get("primary_assertions")
            or packet.get("seed_assertions")
            or packet.get("summary_assertions")
            or packet.get("top_assertions")
            or []
        )
        evidence_sentences = packet.get("evidence_sentences") or []
        source_chunks = packet.get("source_chunks") or []
        related_entities = packet.get("related_entities") or []
        top_assertion_ids = [
            str(row.get("id"))
            for row in top_assertions
            if row.get("id") is not None
        ]
        source_point_ids = self._dedupe_keep_order(
            [
                str(item.get("point_id") or "").strip()
                for item in (sources or [])
                if str(item.get("point_id") or "").strip()
            ]
        )
        return {
            "query_focus": self._sanitize_debug_value(packet.get("query_focus") or {}),
            "query_profile": self._sanitize_debug_value(packet.get("query_profile") or (packet.get("query_debug") or {}).get("query_profile") or {}),
            "matched_chunks": self._sanitize_debug_value(packet.get("matched_chunks") or []),
            "claims": self._sanitize_debug_value(packet.get("matched_claims") or []),
            "context_blocks": self._sanitize_debug_value(packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []),
            "answer_verification": self._sanitize_debug_value(
                packet.get("answer_verification") or (packet.get("query_debug") or {}).get("answer_verification") or {}
            ),
            "scoring_summary": self._sanitize_debug_value(packet.get("scoring_summary") or {}),
            "top_assertion_count": len(top_assertions),
            "evidence_sentence_count": len(evidence_sentences),
            "source_chunk_count": len(source_chunks),
            "related_entity_count": len(related_entities),
            "context_preview": self._sanitize_debug_text((context_text or "")[:500]),
            "top_assertion_ids": top_assertion_ids[:12],
            "source_point_ids": source_point_ids[:12],
        }

    def _kb_pii_settings(self, *, packet: dict[str, Any], kb_uuid: str | None) -> tuple[bool, str, str]:
        effective_kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or kb_uuid or "").strip()
        enabled = bool(packet.get("pii_depersonalization_enabled", True))
        sensitivity = str(packet.get("personal_data_sensitivity") or "medium").strip() or "medium"
        return enabled, sensitivity, effective_kb_uuid

    @staticmethod
    def _pii_prompt_policy() -> str:
        return (
            "PII deperszonalizáció aktív. A contextben és kérdésben [type_index] formátumú tokenek szerepelnek. "
            "A tokenek valós személyes adatok helyettesítői, stabil azonosítóként kell kezelni őket.\n"
            "Gyakori token-típusok (a pontos címke a normalizált pipeline nevet követi):\n"
            "- [szemely_*] = természetes személy neve\n"
            "- [cim_*] = postacím\n"
            "- [azonosito_*], [szemelyi_azonosito_*], [ugyfel_azonosito_*], [utlevel_azonosito_*] = azonosító típusok\n"
            "- [name_*] / [person_*] = természetes személy neve\n"
            "- [email_*] = e-mail cím\n"
            "- [phone_*] = telefonszám\n"
            "- [iban_*] = bankszámla / IBAN\n"
            "- [customer_id_*] = ügyfélazonosító\n"
            "- [date_*] = dátum\n"
            "- [address_*] = postacím\n"
            "- [engine_number_*] / [motorszam_*] = motorszám\n"
            "- [chassis_number_*] / [alvazszam_*] / [vin_*] = alvázszám / VIN\n"
            "- [nie_*] = spanyol NIE azonosító\n"
            "- [vat_*] / [adoszam_*] / [iva_*] = VAT / adószám / IVA azonosító\n"
            "- [passport_*], [personal_id_*], [tax_id_*] = okmány/személyes azonosító\n"
            "Nemzetközi variánsok: hu/en/es címkék is előfordulhatnak ugyanarra az entitásra.\n"
            "Szabályok:\n"
            "1) Soha ne találj ki, egészíts ki vagy fejts vissza személyes adatot tokenből.\n"
            "2) Soha ne módosítsd a token formátumát, és ugyanarra az entitásra mindig ugyanazt a tokent használd.\n"
            "3) Soha ne próbáld meg kitalálni vagy magyarázni, hogy egy token mögött ki a valós személy.\n"
            "4) Ha a felhasználó token mögötti valós nevet kér, udvariasan jelezd, hogy ezt nem adhatod ki, "
            "és maradj a forrásban szereplő, tokenizált tényeknél.\n"
            "5) Bármilyen ismeretlen [*_N] token esetén is kezeld PII-helyettesítőként."
        )

    def _normalize_pii_policy_refusal(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return value
        if self._PII_POLICY_REFUSAL_TEXT.lower() in value.lower():
            return self._insufficient_context_answer()
        return value

    def _audit_pii_encode(
        self,
        *,
        user_id: int | None,
        corpus_uuid: str | None,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self.audit_service is None or not hasattr(self.audit_service, "log"):
            return
        try:
            self.audit_service.log(
                _AUDIT_ACTION_KNOWLEDGE_PII_DEPERSONALIZED,
                user_id=user_id if isinstance(user_id, int) else None,
                target_type="corpus",
                target_id=str(corpus_uuid or "").strip() or None,
                outcome=str(outcome or "unknown"),
                details=sanitize_log_data(details),
            )
        except Exception:
            logger.warning("PII encode audit log sikertelen.", exc_info=True)

    @staticmethod
    def _emit_pii_encode_metrics(
        *,
        sensitivity: str,
        outcome: str,
        duration_ms: float,
        token_count: int,
    ) -> None:
        tags = {
            "sensitivity": str(sensitivity or "medium"),
            "outcome": str(outcome or "unknown"),
        }
        increment_metric("knowledge.pii.depersonalize.runs", 1.0, tags=tags)
        observe_metric("knowledge.pii.depersonalize.duration_ms", float(max(0.0, duration_ms)), unit="ms", tags=tags)
        observe_metric("knowledge.pii.depersonalize.tokens_per_request", float(max(0, token_count)), unit="count", tags=tags)

    def _raise_pii_encode_unavailable(
        self,
        *,
        kb_uuid: str | None,
        corpus_uuid: str | None,
        user_id: int | None,
        source: str,
        sensitivity: str = "medium",
        duration_ms: float = 0.0,
    ) -> None:
        increment_metric("knowledge.pii.encode.failed", 1.0)
        self._emit_pii_encode_metrics(
            sensitivity=sensitivity,
            outcome="failure",
            duration_ms=duration_ms,
            token_count=0,
        )
        self._audit_pii_encode(
            user_id=user_id,
            corpus_uuid=corpus_uuid,
            outcome="failure",
            details={
                "source": source,
                "reason": "encode_exception",
                "kb_uuid": str(kb_uuid or "").strip() or None,
                "corpus_uuid": str(corpus_uuid or "").strip() or None,
                "sensitivity": str(sensitivity or "medium"),
            },
        )
        log_structured_event(
            "apps.chat.service.chat_service",
            "KNOWLEDGE_PII_ENCODE_FAILED",
            level=logging.ERROR,
            reason="encode_exception",
            source=source,
            kb_uuid=str(kb_uuid or "").strip() or None,
            corpus_uuid=str(corpus_uuid or "").strip() or None,
            user_id=int(user_id) if isinstance(user_id, int) else None,
        )
        raise PiiDepersonalizationUnavailableError(self._PII_ENCODE_UNAVAILABLE_DETAIL)

    # Ez a metódus felépíti a(z) messages logikáját.
    @classmethod
    def _build_messages(
        cls,
        question: str,
        context_text: str = "",
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
        pii_prompt_policy: str | None = None,
    ) -> list[dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "Te egy segítőkész asszisztens vagy az AIPLAZA rendszerben. "
                    "Úgy válaszolj, mintha a tudás a saját, belső tudásod lenne: természetesen, emberi hangon, "
                    "közvetlenül, felesleges technikai körítés nélkül. "
                    "Ne hivatkozz arra, hogy kontextust, dokumentumot vagy forrást kaptál. "
                    "A választ mindig teljes, természetes mondattal kezdd; ne induljon töredékes vagy címkeszerű "
                    "fordulattal (pl. 'X szerepel:' vagy 'A dokumentumban:'). "
                    "Válaszolj röviden, legfeljebb 3-4 mondatban."
                ),
            }
        ]
        if pii_prompt_policy:
            messages.append({"role": "system", "content": str(pii_prompt_policy or "").strip()})
        history_context = cls._conversation_history_context(conversation_history)
        if history_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Beszélgetési előzmény (kérdés-válasz párok), röviden. "
                        "Ezt kizárólag a kérdés értelmezéséhez használd, ebből önmagában tilos új tényt állítani.\n\n"
                        f"{history_context}"
                    ),
                }
            )
        retrieval_context = cls._retrieval_history_context(retrieval_history)
        if retrieval_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Korábbi kérdésekből megtartott, releváns tudástári találati részletek. "
                        "Ez segéd kontextus, nem elsődleges bizonyíték: tényt csak az aktuális tudástár-contexttel alátámasztva állíts.\n\n"
                        f"{retrieval_context}"
                    ),
                }
            )
        if context_text:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "A következő tudástár-context alapján válaszolj tömören, "
                        "és csak akkor állíts tényt, ha a context alátámasztja. "
                        "A válasz nyelve mindig egyezzen meg a felhasználó kérdésének nyelvével; "
                        "magyar kérdésre magyarul válaszolj akkor is, ha a context belső címkéi angolul vannak. "
                        "A belső címkéket, például Current facts, Historical vagy Vectoros találatok, ne idézd vissza. "
                        "Ne használj meta-megfogalmazást, például: 'a context alapján', 'a megadott kontextus szerint'. "
                        "Adj közvetlen, természetes választ, mintha a tényeket biztosan tudnád.\n\n"
                        f"{context_text}"
                    ),
                }
            )
        messages.append({"role": "user", "content": question})
        return messages

    @classmethod
    def _build_prompt_context_payload(
        cls,
        *,
        question: str,
        messages: list[dict[str, str]] | None,
        conversation_history: list[dict[str, str]] | None,
        retrieval_history: list[str] | None,
        packet: dict[str, Any],
        context_text: str,
        encoded_question: str | None = None,
        encoded_context_text: str | None = None,
        pii_prompt_policy: str | None = None,
        pii_applied: bool | None = None,
        pii_reason: str | None = None,
        encoded_answer_text: str | None = None,
        raw_question_before_pii: str | None = None,
        raw_context_before_pii: str | None = None,
        raw_conversation_history_before_pii: list[dict[str, str]] | None = None,
        raw_retrieval_history_before_pii: list[str] | None = None,
    ) -> dict[str, Any]:
        qa_context = cls._conversation_history_context(conversation_history)
        retrieval_context = cls._retrieval_history_context(retrieval_history)
        info_prompt = ""
        if messages:
            for msg in messages:
                if str(msg.get("role") or "").strip() == "system":
                    info_prompt = str(msg.get("content") or "").strip()
                    if info_prompt:
                        break
        hits: list[dict[str, Any]] = []
        for block in (packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [])[:4]:
            if not isinstance(block, dict):
                continue
            hits.append(
                {
                    "block_id": str(block.get("block_id") or block.get("id") or "").strip(),
                    "source_id": str(block.get("source_id") or "").strip(),
                    "subject": str(block.get("subject") or block.get("primary_subject") or "").strip(),
                    "snippet": str(block.get("snippet") or block.get("text") or "").strip(),
                }
            )
        evidence_rows = [
            item
            for item in (packet.get("evidence_summary") or [])
            if isinstance(item, dict)
        ]
        answer_information_sources: list[dict[str, Any]] = []
        seen_answer_source_ids: set[str] = set()
        for row in evidence_rows:
            source_id = str(row.get("source_id") or "").strip()
            if not source_id or source_id in seen_answer_source_ids:
                continue
            seen_answer_source_ids.add(source_id)
            answer_information_sources.append(
                {
                    "source_id": source_id,
                    "claim_id": str(row.get("claim_id") or "").strip(),
                    "sentence_id": str(row.get("sentence_id") or "").strip(),
                    "claim_text": str(row.get("claim_text") or "").strip(),
                    "sentence_text": str(row.get("sentence_text") or "").strip(),
                }
            )
        raw_context_sent_to_llm = "\n\n".join(
            f"[{str(msg.get('role') or '').strip()}]\n{str(msg.get('content') or '').strip()}"
            for msg in (messages or [])
            if isinstance(msg, dict) and str(msg.get("content") or "").strip()
        ).strip()
        matched_chunks_for_debug = [
            chunk
            for chunk in (packet.get("matched_chunks") or [])
            if isinstance(chunk, dict)
        ]
        packet_retrieval_confidence = 0.0
        try:
            packet_retrieval_confidence = float(packet.get("retrieval_confidence") or 0.0)
        except (TypeError, ValueError):
            packet_retrieval_confidence = 0.0
        if packet_retrieval_confidence <= 0 and matched_chunks_for_debug:
            scores: list[float] = []
            for chunk in matched_chunks_for_debug:
                try:
                    score = float(chunk.get("retrieval_confidence") or 0.0)
                except (TypeError, ValueError):
                    score = 0.0
                if score > 0:
                    scores.append(score)
            if scores:
                packet_retrieval_confidence = round(sum(scores) / len(scores), 4)
        index_debug = {
            "retrieval_confidence": packet_retrieval_confidence,
            "timing_ms": packet.get("_chat_timing_ms") or {},
            "query_profile": packet.get("query_profile") or packet.get("query_focus") or {},
            "scoring_summary": packet.get("scoring_summary") or {},
            "filtered_out_reason": packet.get("filtered_out_reason") or [],
            "thresholds": {
                "packet_score_threshold": cls._MULTI_KB_PACKET_SCORE_THRESHOLD,
                "block_score_threshold": cls._MULTI_KB_BLOCK_SCORE_THRESHOLD,
                "block_relative_floor_ratio": cls._MULTI_KB_BLOCK_RELATIVE_FLOOR_RATIO,
                "dynamic_block_score_threshold": float(packet.get("dynamic_block_score_threshold") or 0.0),
            },
            "selected_blocks": [
                {
                    "kb_uuid": str(block.get("kb_uuid") or packet.get("kb_uuid") or "").strip(),
                    "block_id": str(block.get("block_id") or block.get("id") or "").strip(),
                    "source_id": str(block.get("source_id") or "").strip(),
                    "match_score": float(block.get("match_score") or 0.0),
                    "match_reason": block.get("match_reason") or {},
                }
                for block in (packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [])[:8]
                if isinstance(block, dict)
            ],
            "matched_chunks": [
                {
                    "profile_id": str(chunk.get("profile_id") or "").strip(),
                    "entity_name": str(chunk.get("entity_name") or "").strip(),
                    "retrieval_confidence": float(chunk.get("retrieval_confidence") or 0.0),
                    "matched_claim_ids": list(chunk.get("matched_claim_ids") or []),
                }
                for chunk in matched_chunks_for_debug[:8]
            ],
            "multi_kb_diagnostics": packet.get("multi_kb_diagnostics") or {},
        }
        return {
            "informational_prompt": info_prompt,
            "qa_context": qa_context,
            "retrieval_context": retrieval_context,
            "latest_question": str(question or "").strip(),
            "raw_context_sent_to_llm": raw_context_sent_to_llm,
            "context_components": {
                "alap_context": str(context_text or "").strip(),
                "elozmenyek": qa_context,
                "kerdes": str(question or "").strip(),
                "valaszinformacio": {
                    "answer_mode": str(packet.get("answer_mode") or "no_answer"),
                    "evidence_summary": evidence_rows,
                    "cited_source_ids": list(packet.get("cited_source_ids") or packet.get("source_ids") or []),
                },
            },
            "raw_inputs_before_pii": {
                "question": str(raw_question_before_pii if raw_question_before_pii is not None else question or "").strip(),
                "context_text": str(raw_context_before_pii if raw_context_before_pii is not None else context_text or "").strip(),
                "conversation_history": list(raw_conversation_history_before_pii or []),
                "retrieval_history": list(raw_retrieval_history_before_pii or []),
            },
            "answer_information_sources": answer_information_sources,
            "latest_hits": hits,
            "llm_context_text": str(context_text or "").strip(),
            "encoded_latest_question": str(encoded_question or question or "").strip(),
            "encoded_llm_context_text": str(encoded_context_text or context_text or "").strip(),
            "encoded_answer_text": str(encoded_answer_text or "").strip(),
            "pii_prompt_policy": str(pii_prompt_policy or "").strip(),
            "pii_applied": pii_applied,
            "pii_reason": str(pii_reason or "").strip(),
            "index_debug": index_debug,
            "messages_sent_to_llm": [
                {"role": str(msg.get("role") or ""), "content": str(msg.get("content") or "")}
                for msg in (messages or [])
            ],
        }

    # Ez a metódus a(z) insufficient_context_answer logikáját valósítja meg.
    @classmethod
    def _insufficient_context_answer(cls) -> str:
        return cls._INSUFFICIENT_CONTEXT_ANSWER

    async def chat(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
    ) -> str:
        """Chat üzenet küldése OpenAI API-nak (egyszeri válasz)."""
        try:
            context_text, context_failed = await self._safe_context_text(
                question=question,
                user_id=user_id,
                user_role=user_role,
                kb_uuid=kb_uuid,
                debug=debug,
            )
            if context_failed or not context_text.strip():
                return ""
            messages = self._build_messages(
                question=question,
                context_text="" if context_failed else context_text,
                conversation_history=conversation_history,
                retrieval_history=retrieval_history,
            )
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**self._chat_completion_kwargs(messages)),
                timeout=self._chat_completion_timeout_sec,
            )
            answer = self._extract_response_text(response)
            if not answer:
                logger.warning("Üres válasz érkezett az OpenAI API-tól")
                return "⚠️ Nem sikerült választ kapni a modellből."
            answer = self._normalize_pii_policy_refusal(answer)
            if debug and context_text and not context_failed:
                return f"{answer}\n\n[debug-context]\n{self._sanitize_debug_text(context_text)}"
            return str(answer or "")[: self._chat_max_answer_chars]
        except RateLimitError as e:
            logger.error(f"OpenAI rate limit hiba: {e}", exc_info=True)
            return "⚠️ Túl sok kérés. Kérlek, próbáld újra később."
        except APITimeoutError as e:
            logger.error(f"OpenAI timeout hiba: {e}", exc_info=True)
            return "⚠️ A válasz túl sokáig tartott. Kérlek, próbáld újra."
        except APIConnectionError as e:
            logger.error(f"OpenAI kapcsolati hiba: {e}", exc_info=True)
            return "⚠️ Kapcsolati probléma történt. Kérlek, próbáld újra."
        except APIError as e:
            logger.error(f"OpenAI API hiba: {e}", exc_info=True)
            return "⚠️ Nem sikerült választ kapni a modellből."
        except asyncio.TimeoutError:
            logger.error("LLM timeout: a modellhívás túllépte az időkorlátot.", exc_info=True)
            return "⚠️ A modell válasza túl sokáig tartott. Próbáld újra rövidebb kérdéssel."
        except Exception as e:
            logger.error(f"Váratlan hiba a chat szolgáltatásban: {e}", exc_info=True)
            return "⚠️ Nem sikerült választ kapni a modellből."

    async def chat_with_sources(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
    ) -> dict:
        """Chat válasz forráslistával együtt."""
        t_total = perf_counter()
        context_build_ms = 0.0
        llm_ms = 0.0
        packet: dict = {}
        context_failed = False
        if str(user_role or "").strip().lower() == "channel" and self._looks_broad_enumeration_request(question):
            increment_metric("channel.chat.rejected.enumeration", 1.0)
            raise ChatPolicyViolationError(self._ENUMERATION_POLICY_DETAIL)
        try:
            t_context = perf_counter()
            packet = await asyncio.wait_for(
                self._build_context_packet(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    kb_uuid=kb_uuid,
                    debug=debug,
                ),
                timeout=self._chat_context_timeout_sec,
            )
            context_build_ms = round((perf_counter() - t_context) * 1000.0, 2)
            synthesized_answer = str(packet.get("answer_text") or "").strip()
            if synthesized_answer and self._should_return_direct_knowledge_answer(packet, question=question):
                packet["_chat_timing_ms"] = {
                    "context_build": context_build_ms,
                    "llm": 0.0,
                    "total": round((perf_counter() - t_total) * 1000.0, 2),
                }
                return self._knowledge_payload(
                    packet=packet,
                    debug=debug,
                    question=question,
                    conversation_history=conversation_history,
                    retrieval_history=retrieval_history,
                )
            context_text = self._llm_context_text_from_packet(packet)
        except PermissionError:
            raise
        except asyncio.TimeoutError:
            context_build_ms = round((perf_counter() - t_total) * 1000.0, 2)
            logger.warning(
                "chat_with_sources context timeout (%ss).",
                self._chat_context_timeout_sec,
                exc_info=True,
            )
            context_text = ""
            packet = {}
            context_failed = True
        except Exception as e:
            context_build_ms = round((perf_counter() - t_total) * 1000.0, 2)
            logger.warning("chat_with_sources context hiba: %s", e, exc_info=True)
            context_text = ""
            packet = {}
            context_failed = True

        prompt_context: dict[str, Any] = {}
        messages: list[dict[str, str]] = []
        restored_pii_spans: list[dict[str, Any]] = []
        encoded_prompt_context = ""
        encoded_question = question
        pii_prompt_policy = ""
        pii_enabled = False
        pii_corpus_uuid = ""
        pii_sensitivity = "medium"
        pii_applied: bool | None = None
        pii_reason = ""
        pii_encode_duration_ms = 0.0
        allowed_rehydrate_tokens: set[str] = set()
        encoded_answer_text = ""
        encoded_conversation_history = conversation_history
        encoded_retrieval_history = retrieval_history
        raw_question_before_pii = str(question or "")
        raw_context_before_pii = str(context_text or "")
        raw_conversation_history_before_pii = list(conversation_history or [])
        raw_retrieval_history_before_pii = list(retrieval_history or [])
        if isinstance(packet, dict):
            pii_enabled, pii_sensitivity, pii_corpus_uuid = self._kb_pii_settings(packet=packet, kb_uuid=kb_uuid)
        if pii_enabled and self.pii_depersonalization_service is not None and pii_corpus_uuid:
            pii_prompt_policy = self._pii_prompt_policy()
            pii_t0 = perf_counter()
            try:
                encoded_question_obj = self.pii_depersonalization_service.encode_text(
                    corpus_uuid=pii_corpus_uuid,
                    text=question,
                    enabled=True,
                    sensitivity=pii_sensitivity,
                )
                encoded_context_obj = self.pii_depersonalization_service.encode_text(
                    corpus_uuid=pii_corpus_uuid,
                    text=context_text,
                    enabled=True,
                    sensitivity=pii_sensitivity,
                )
                encoded_prompt_context = encoded_context_obj.text
                encoded_question = encoded_question_obj.text
                if (
                    str(encoded_question or "").strip() == str(question or "").strip()
                    and (encoded_context_obj.mappings or [])
                ):
                    encoded_question = self._encode_question_using_context_mappings(
                        question=question,
                        context_mappings=encoded_context_obj.mappings,
                    )
                encoded_conversation_history = []
                history_mappings: list[dict[str, Any]] = []
                for item in (conversation_history or []):
                    if not isinstance(item, dict):
                        continue
                    role = str(item.get("role") or "").strip()
                    content = str(item.get("content") or "").strip()
                    if not role or not content:
                        continue
                    encoded_item = self.pii_depersonalization_service.encode_text(
                        corpus_uuid=pii_corpus_uuid,
                        text=content,
                        enabled=True,
                        sensitivity=pii_sensitivity,
                    )
                    history_mappings.extend(encoded_item.mappings or [])
                    encoded_conversation_history.append(
                        {"role": role, "content": encoded_item.text}
                    )
                encoded_retrieval_history = []
                for raw_item in (retrieval_history or []):
                    raw_text = str(raw_item or "").strip()
                    if not raw_text:
                        continue
                    encoded_item = self.pii_depersonalization_service.encode_text(
                        corpus_uuid=pii_corpus_uuid,
                        text=raw_text,
                        enabled=True,
                        sensitivity=pii_sensitivity,
                    )
                    history_mappings.extend(encoded_item.mappings or [])
                    encoded_retrieval_history.append(encoded_item.text)
                pii_applied = True
                pii_reason = "PII deperszonalizáció sikeres."
                pii_encode_duration_ms = round((perf_counter() - pii_t0) * 1000.0, 2)
                mappings = [
                    *(encoded_question_obj.mappings or []),
                    *(encoded_context_obj.mappings or []),
                    *history_mappings,
                ]
                allowed_rehydrate_tokens = {
                    str(item.get("token") or "").strip()
                    for item in mappings
                    if isinstance(item, dict) and str(item.get("token") or "").strip()
                }
                token_count = len(mappings)
                entity_types = sorted(
                    {
                        str(item.get("entity_type") or "").strip()
                        for item in mappings
                        if isinstance(item, dict) and str(item.get("entity_type") or "").strip()
                    }
                )
                self._emit_pii_encode_metrics(
                    sensitivity=pii_sensitivity,
                    outcome="success",
                    duration_ms=pii_encode_duration_ms,
                    token_count=token_count,
                )
                self._audit_pii_encode(
                    user_id=user_id,
                    corpus_uuid=pii_corpus_uuid,
                    outcome="success",
                    details={
                        "source": "chat_with_sources",
                        "pii_items_created": token_count,
                        "entity_types": entity_types,
                        "context_length_chars": len(str(context_text or "")),
                        "encoded_length_chars": len(str(encoded_prompt_context or "")),
                        "sensitivity": pii_sensitivity,
                    },
                )
            except Exception:
                pii_encode_duration_ms = round((perf_counter() - pii_t0) * 1000.0, 2)
                logger.error("PII depersonalization encode failed; fail-closed response.", exc_info=True)
                self._raise_pii_encode_unavailable(
                    kb_uuid=kb_uuid,
                    corpus_uuid=pii_corpus_uuid,
                    user_id=user_id,
                    source="chat_with_sources",
                    sensitivity=pii_sensitivity,
                    duration_ms=pii_encode_duration_ms,
                )
        else:
            encoded_prompt_context = context_text
            if not pii_enabled:
                pii_applied = False
                pii_reason = "A kiválasztott tudástárban a PII deperszonalizáció ki van kapcsolva."
            elif not pii_corpus_uuid:
                pii_applied = False
                pii_reason = "Összes tudástár módban nincs egyedi KB-azonosító, ezért nem futott PII deperszonalizáció."
            elif self.pii_depersonalization_service is None:
                pii_applied = False
                pii_reason = "PII deperszonalizációs szolgáltatás nem elérhető."

        if context_failed or not context_text.strip():
            build_ids = packet.get("build_ids") if isinstance(packet, dict) else None
            has_ready_build_reference = isinstance(build_ids, list) and any(str(item or "").strip() for item in build_ids)
            should_show_missing_index_message = bool(packet.get("no_ready_index_build")) and not has_ready_build_reference
            if should_show_missing_index_message:
                increment_metric("chat_missing_ready_index_detected_total", 1)
                log_structured_event(
                    "apps.chat",
                    "chat.context.empty_missing_ready_index",
                    level=logging.WARNING,
                    user_id=user_id,
                    kb_uuid=str(packet.get("kb_uuid") or packet.get("corpus_uuid") or kb_uuid or "").strip() or None,
                    no_ready_index_build=True,
                    has_ready_build_reference=has_ready_build_reference,
                    query_preview=sanitize_log_data({"query_preview": str(question or "")[:160]}).get("query_preview"),
                )
            answer = "Nem találtam releváns választ a kiválasztott tudástárban."
            prompt_context = self._build_prompt_context_payload(
                question=question,
                messages=[],
                conversation_history=encoded_conversation_history,
                retrieval_history=encoded_retrieval_history,
                packet=packet or {},
                context_text=context_text,
                encoded_question=encoded_question,
                encoded_context_text=encoded_prompt_context,
                pii_prompt_policy=pii_prompt_policy,
                pii_applied=pii_applied,
                pii_reason=pii_reason,
                encoded_answer_text=encoded_answer_text,
                raw_question_before_pii=raw_question_before_pii,
                raw_context_before_pii=raw_context_before_pii,
                raw_conversation_history_before_pii=raw_conversation_history_before_pii,
                raw_retrieval_history_before_pii=raw_retrieval_history_before_pii,
            )
        else:
            messages = self._build_messages(
                question=encoded_question,
                context_text=encoded_prompt_context,
                conversation_history=encoded_conversation_history,
                retrieval_history=encoded_retrieval_history,
                pii_prompt_policy=pii_prompt_policy,
            )
            prompt_context = self._build_prompt_context_payload(
                question=question,
                messages=messages,
                conversation_history=encoded_conversation_history,
                retrieval_history=encoded_retrieval_history,
                packet=packet or {},
                context_text=context_text,
                encoded_question=encoded_question,
                encoded_context_text=encoded_prompt_context,
                pii_prompt_policy=pii_prompt_policy,
                pii_applied=pii_applied,
                pii_reason=pii_reason,
                encoded_answer_text=encoded_answer_text,
                raw_question_before_pii=raw_question_before_pii,
                raw_context_before_pii=raw_context_before_pii,
                raw_conversation_history_before_pii=raw_conversation_history_before_pii,
                raw_retrieval_history_before_pii=raw_retrieval_history_before_pii,
            )
            if debug:
                logger.info(
                    "chat.raw_inputs_before_pii",
                    extra={
                        "kb_uuid": str(packet.get("kb_uuid") or packet.get("corpus_uuid") or kb_uuid or "").strip() or None,
                        "question": raw_question_before_pii,
                        "context_text": raw_context_before_pii,
                        "conversation_history": raw_conversation_history_before_pii,
                        "retrieval_history": raw_retrieval_history_before_pii,
                    },
                )
            try:
                t_llm = perf_counter()
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(**self._chat_completion_kwargs(messages)),
                    timeout=self._chat_completion_timeout_sec,
                )
                llm_ms = round((perf_counter() - t_llm) * 1000.0, 2)
                answer = self._extract_response_text(response) or "⚠️ Nem sikerült választ kapni a modellből."
                encoded_answer_text = str(answer or "")
                if pii_enabled and self.pii_depersonalization_service is not None and pii_corpus_uuid:
                    restored = self.pii_depersonalization_service.rehydrate_text(
                        corpus_uuid=pii_corpus_uuid,
                        text=str(answer or ""),
                        enabled=True,
                        allowed_tokens=allowed_rehydrate_tokens,
                    )
                    answer = restored.text
                    restored_pii_spans = restored.restored_spans
                answer = self._normalize_pii_policy_refusal(answer)
                answer = str(answer or "")[: self._chat_max_answer_chars]
            except RateLimitError as e:
                llm_ms = round((perf_counter() - t_llm) * 1000.0, 2)
                logger.error(f"LLM rate limit hiba: {e}", exc_info=True)
                answer = "⚠️ Túl sok kérés. Kérlek, próbáld újra később."
            except APITimeoutError as e:
                llm_ms = round((perf_counter() - t_llm) * 1000.0, 2)
                logger.error(f"LLM timeout hiba: {e}", exc_info=True)
                answer = "⚠️ A válasz túl sokáig tartott. Kérlek, próbáld újra."
            except APIConnectionError as e:
                llm_ms = round((perf_counter() - t_llm) * 1000.0, 2)
                logger.error(f"LLM kapcsolati hiba: {e}", exc_info=True)
                answer = "⚠️ A lokális/remote LLM most nem elérhető. Ellenőrizd a provider URL-t és próbáld újra."
            except APIError as e:
                llm_ms = round((perf_counter() - t_llm) * 1000.0, 2)
                logger.error(f"LLM API hiba: {e}", exc_info=True)
                answer = "⚠️ Nem sikerült választ kapni a modellből."
            except asyncio.TimeoutError:
                llm_ms = round((perf_counter() - t_llm) * 1000.0, 2)
                logger.error("LLM timeout: a modellhívás túllépte az időkorlátot.", exc_info=True)
                answer = "⚠️ A modell válasza túl sokáig tartott. Próbáld újra rövidebb kérdéssel."
            except Exception as e:
                llm_ms = round((perf_counter() - t_llm) * 1000.0, 2)
                logger.error(f"Váratlan LLM hiba: {e}", exc_info=True)
                answer = "⚠️ Nem sikerült választ kapni a modellből."
        packet["_chat_timing_ms"] = {
            "context_build": context_build_ms,
            "llm": llm_ms,
            "total": round((perf_counter() - t_total) * 1000.0, 2),
        }
        if isinstance(prompt_context, dict):
            prompt_context["encoded_answer_text"] = str(encoded_answer_text or "").strip()
            index_debug = prompt_context.get("index_debug")
            if isinstance(index_debug, dict):
                index_debug["timing_ms"] = packet.get("_chat_timing_ms") or {}
        logger.info(
            "chat_with_sources timing ms",
            extra={
                "timing_ms": packet.get("_chat_timing_ms"),
                "kb_uuid": str(kb_uuid or "").strip() or "all",
                "has_context": bool(context_text and not context_failed),
            },
        )
        has_knowledge_context = bool(context_text and not context_failed)
        payload = {
            "answer": str(answer or "")[: self._chat_max_answer_chars],
            "query_run_id": str(packet.get("query_run_id") or "").strip() or None,
            "answer_mode": str(packet.get("answer_mode") or "no_answer"),
            "answer_source": "knowledge_llm" if has_knowledge_context and answer else "llm_fallback" if answer else "none",
            "confidence": self._chat_confidence(packet) if answer else 0.0,
            "evidence": self._chat_evidence(packet) if answer else [],
            "cited_claim_ids": packet.get("cited_claim_ids") or [],
            "cited_sentence_ids": packet.get("cited_sentence_ids") or [],
            "cited_source_ids": packet.get("cited_source_ids") or packet.get("source_ids") or [],
            "query_profile": packet.get("query_profile") or packet.get("query_focus") or {},
            "matched_chunks": packet.get("matched_chunks") or [],
            "claims": packet.get("matched_claims") or [],
            "context_blocks": packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [],
            "sources": self._build_sources_from_packet(packet) if context_text and not context_failed else [],
            "prompt_context": prompt_context,
            "encoded_prompt_context": encoded_prompt_context if pii_enabled else "",
            "restored_pii_spans": restored_pii_spans,
        }
        has_grounding_rows = bool(packet.get("source_chunks") or packet.get("evidence_summary") or packet.get("cited_source_ids"))
        if has_knowledge_context and payload["answer"] and not payload["sources"] and not has_grounding_rows:
            # Forrás nélküli tényválaszt ne engedjünk vissza (hallucináció-védelem).
            payload["answer"] = self._insufficient_context_answer()
            payload["answer_mode"] = "no_answer"
            payload["answer_source"] = "none"
            payload["confidence"] = 0.0
            payload["evidence"] = []
            payload["cited_claim_ids"] = []
            payload["cited_sentence_ids"] = []
            payload["cited_source_ids"] = []
        if context_text and not context_failed and packet.get("is_followup") and self.kb_service is not None:
            for row in packet.get("top_assertions") or []:
                aid = str(row.get("id") or "")
                kb_uuid_for_row = str(row.get("kb_uuid") or kb_uuid or "")
                if aid.startswith("assertion-") and aid.split("-", 1)[1].isdigit() and kb_uuid_for_row:
                    try:
                        self.kb_service.reinforce_assertion(
                            kb_uuid=kb_uuid_for_row,
                            assertion_id=int(aid.split("-", 1)[1]),
                            event_type="USER_FOLLOWUP",
                        )
                    except Exception:
                        pass
        if debug:
            payload["debug"] = self._build_debug_payload(
                packet=packet or {},
                context_text=context_text,
                sources=payload.get("sources") or [],
            )
        return payload

    async def chat_stream(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
    ) -> AsyncIterator[str]:
        """Streamelt chat válasz: tokenenként yield-eli a tartalmat."""
        try:
            packet = await asyncio.wait_for(
                self._build_context_packet(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    kb_uuid=kb_uuid,
                    debug=False,
                ),
                timeout=self._chat_context_timeout_sec,
            )
            context_text = self._llm_context_text_from_packet(packet)
            pii_enabled, pii_sensitivity, pii_corpus_uuid = self._kb_pii_settings(packet=packet, kb_uuid=kb_uuid)
            encoded_question = question
            encoded_context_text = context_text
            pii_prompt_policy = ""
            allowed_rehydrate_tokens: set[str] = set()
            if pii_enabled and self.pii_depersonalization_service is not None and pii_corpus_uuid:
                pii_prompt_policy = self._pii_prompt_policy()
                pii_t0 = perf_counter()
                try:
                    encoded_question_obj = self.pii_depersonalization_service.encode_text(
                        corpus_uuid=pii_corpus_uuid,
                        text=question,
                        enabled=True,
                        sensitivity=pii_sensitivity,
                    )
                    encoded_context_obj = self.pii_depersonalization_service.encode_text(
                        corpus_uuid=pii_corpus_uuid,
                        text=context_text,
                        enabled=True,
                        sensitivity=pii_sensitivity,
                    )
                    encoded_question = encoded_question_obj.text
                    encoded_context_text = encoded_context_obj.text
                    pii_encode_duration_ms = round((perf_counter() - pii_t0) * 1000.0, 2)
                    mappings = [
                        *(encoded_question_obj.mappings or []),
                        *(encoded_context_obj.mappings or []),
                    ]
                    allowed_rehydrate_tokens = {
                        str(item.get("token") or "").strip()
                        for item in mappings
                        if isinstance(item, dict) and str(item.get("token") or "").strip()
                    }
                    token_count = len(mappings)
                    entity_types = sorted(
                        {
                            str(item.get("entity_type") or "").strip()
                            for item in mappings
                            if isinstance(item, dict) and str(item.get("entity_type") or "").strip()
                        }
                    )
                    self._emit_pii_encode_metrics(
                        sensitivity=pii_sensitivity,
                        outcome="success",
                        duration_ms=pii_encode_duration_ms,
                        token_count=token_count,
                    )
                    self._audit_pii_encode(
                        user_id=user_id,
                        corpus_uuid=pii_corpus_uuid,
                        outcome="success",
                        details={
                            "source": "chat_stream",
                            "pii_items_created": token_count,
                            "entity_types": entity_types,
                            "context_length_chars": len(str(context_text or "")),
                            "encoded_length_chars": len(str(encoded_context_text or "")),
                            "sensitivity": pii_sensitivity,
                        },
                    )
                except Exception:
                    pii_encode_duration_ms = round((perf_counter() - pii_t0) * 1000.0, 2)
                    logger.error("PII depersonalization encode failed in stream; fail-closed response.", exc_info=True)
                    self._raise_pii_encode_unavailable(
                        kb_uuid=kb_uuid,
                        corpus_uuid=pii_corpus_uuid,
                        user_id=user_id,
                        source="chat_stream",
                        sensitivity=pii_sensitivity,
                        duration_ms=pii_encode_duration_ms,
                    )
            messages = self._build_messages(
                question=encoded_question,
                context_text=encoded_context_text,
                pii_prompt_policy=pii_prompt_policy,
            )
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**self._chat_completion_kwargs(messages)),
                timeout=self._chat_completion_timeout_sec,
            )
            answer = self._extract_response_text(response) or "⚠️ Nem sikerült választ kapni a modellből."
            if pii_enabled and self.pii_depersonalization_service is not None and pii_corpus_uuid:
                answer = self.pii_depersonalization_service.rehydrate_text(
                    corpus_uuid=pii_corpus_uuid,
                    text=str(answer or ""),
                    enabled=True,
                    allowed_tokens=allowed_rehydrate_tokens,
                ).text
            yield str(answer or "")[: self._chat_max_answer_chars]
        except RateLimitError as e:
            logger.error(f"OpenAI rate limit hiba: {e}", exc_info=True)
            yield "⚠️ Túl sok kérés. Kérlek, próbáld újra később."
        except APITimeoutError as e:
            logger.error(f"OpenAI timeout hiba: {e}", exc_info=True)
            yield "⚠️ A válasz túl sokáig tartott. Kérlek, próbáld újra."
        except APIConnectionError as e:
            logger.error(f"OpenAI kapcsolati hiba: {e}", exc_info=True)
            yield "⚠️ Kapcsolati probléma történt. Kérlek, próbáld újra."
        except APIError as e:
            logger.error(f"OpenAI API hiba: {e}", exc_info=True)
            yield "⚠️ Nem sikerült választ kapni a modellből."
        except asyncio.TimeoutError:
            logger.error("LLM timeout: a stream indítása túllépte az időkorlátot.", exc_info=True)
            yield "⚠️ A modell válasza túl sokáig tartott. Próbáld újra rövidebb kérdéssel."
        except PiiDepersonalizationUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Váratlan hiba a chat szolgáltatásban: {e}", exc_info=True)
            yield "⚠️ Nem sikerült választ kapni a modellből."
