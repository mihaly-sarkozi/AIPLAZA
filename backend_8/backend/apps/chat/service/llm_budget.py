# backend/apps/chat/service/llm_budget.py
# Feladat: Chat LLM budget és concurrency limit kezelést tartalmaz. Redis alapú prod limitet, in-memory fallbacket, napi/havi tokenkeretet, globális költségkeretet és inflight release logikát választ le a ChatService-ről. Program-specifikus AI költségvédelmi service.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from core.kernel.config.config_loader import get_app_env, settings
from core.kernel.config.environment import is_deployed_env
from core.kernel.security.rate_limit import get_rate_limit_redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmBudgetConfig:
    request_limit_per_minute: int
    prompt_chars_per_minute: int
    concurrency_limit: int
    tenant_daily_tokens: int
    tenant_monthly_tokens: int
    estimated_completion_tokens: int
    input_cost_per_1k_tokens_usd: float
    output_cost_per_1k_tokens_usd: float
    global_daily_spend_usd: float
    chat_max_tokens: int


class LlmBudgetManager:
    def __init__(
        self,
        *,
        config: LlmBudgetConfig,
        lock: threading.Lock | None = None,
        state: dict[tuple[str, str], dict[str, int]] | None = None,
        redis_getter: Callable[[], Any] = get_rate_limit_redis,
    ) -> None:
        self.config = config
        self._lock = lock or threading.Lock()
        self._state = state if state is not None else {}
        self._redis_getter = redis_getter

    @classmethod
    def from_settings(
        cls,
        *,
        chat_max_tokens: int,
        lock: threading.Lock | None = None,
        state: dict[tuple[str, str], dict[str, int]] | None = None,
        redis_getter: Callable[[], Any] = get_rate_limit_redis,
    ) -> LlmBudgetManager:
        return cls(
            config=LlmBudgetConfig(
                request_limit_per_minute=max(
                    1,
                    int(getattr(settings, "llm_budget_request_limit_per_minute", 120) or 120),
                ),
                prompt_chars_per_minute=max(
                    1,
                    int(getattr(settings, "llm_budget_prompt_chars_per_minute", 120000) or 120000),
                ),
                concurrency_limit=max(
                    1,
                    int(getattr(settings, "llm_budget_concurrency_limit", 8) or 8),
                ),
                tenant_daily_tokens=max(
                    1,
                    int(getattr(settings, "llm_budget_tenant_daily_tokens", 120_000) or 120_000),
                ),
                tenant_monthly_tokens=max(
                    1,
                    int(getattr(settings, "llm_budget_tenant_monthly_tokens", 2_000_000) or 2_000_000),
                ),
                estimated_completion_tokens=max(
                    1,
                    int(getattr(settings, "llm_budget_estimated_completion_tokens", 220) or 220),
                ),
                input_cost_per_1k_tokens_usd=max(
                    0.00001,
                    float(getattr(settings, "llm_budget_input_cost_per_1k_tokens_usd", 0.003) or 0.003),
                ),
                output_cost_per_1k_tokens_usd=max(
                    0.00001,
                    float(getattr(settings, "llm_budget_output_cost_per_1k_tokens_usd", 0.006) or 0.006),
                ),
                global_daily_spend_usd=max(
                    0.01,
                    float(getattr(settings, "llm_budget_global_daily_spend_usd", 15.0) or 15.0),
                ),
                chat_max_tokens=chat_max_tokens,
            ),
            lock=lock,
            state=state,
            redis_getter=redis_getter,
        )

    @staticmethod
    def rollback_redis_budget(
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

    def acquire(
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
        effective_daily_tokens = self.config.tenant_daily_tokens
        effective_monthly_tokens = self.config.tenant_monthly_tokens
        if is_demo_scope:
            effective_daily_tokens = min(
                effective_daily_tokens,
                max(1, int(getattr(settings, "llm_budget_demo_daily_tokens", 30_000) or 30_000)),
            )
            effective_monthly_tokens = min(
                effective_monthly_tokens,
                max(1, int(getattr(settings, "llm_budget_demo_monthly_tokens", 150_000) or 150_000)),
            )
        elif is_starter_scope:
            effective_monthly_tokens = min(
                effective_monthly_tokens,
                max(1, int(getattr(settings, "llm_budget_starter_monthly_tokens", 900_000) or 900_000)),
            )
        now_utc = datetime.now(UTC)
        minute_bucket = int(now_utc.timestamp() // 60)
        day_bucket = now_utc.strftime("%Y%m%d")
        month_bucket = now_utc.strftime("%Y%m")
        prompt_units = max(1, int(prompt_chars or 1))
        prompt_tokens = max(1, int(round(prompt_units / 4.0)))
        completion_tokens = min(self.config.chat_max_tokens, self.config.estimated_completion_tokens)
        estimated_tokens = max(1, prompt_tokens + completion_tokens)
        estimated_cost_usd = (
            (prompt_tokens / 1000.0) * self.config.input_cost_per_1k_tokens_usd
            + (completion_tokens / 1000.0) * self.config.output_cost_per_1k_tokens_usd
        )
        redis_client = self._redis_getter()
        fail_closed = bool(getattr(settings, "llm_budget_fail_closed_without_redis", True))
        try:
            env = get_app_env()
        except Exception:
            env = "dev"
        if redis_client is None and fail_closed and is_deployed_env(env):
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
                checks = (
                    (int(req_count or 0) > self.config.request_limit_per_minute, "LLM kéréslimit elérve ebben a percben."),
                    (int(chars_count or 0) > self.config.prompt_chars_per_minute, "LLM prompt limit elérve ebben a percben."),
                    (int(inflight_count or 0) > self.config.concurrency_limit, "Túl sok párhuzamos LLM kérés folyamatban."),
                    (int(day_tokens or 0) > effective_daily_tokens, "Napi AI token keret elérve a tenantnál."),
                    (int(month_tokens or 0) > effective_monthly_tokens, "Havi AI token keret elérve a tenantnál."),
                    ((int(global_spend_micro or 0) / 1_000_000.0) > self.config.global_daily_spend_usd, "A mai globális AI költségkeret betelt."),
                )
                for failed, message in checks:
                    if failed:
                        self.rollback_redis_budget(
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
                        return False, message, None
                return True, "", {"backend": "redis", "inflight_key": inflight_key}
            except Exception:
                if fail_closed and is_deployed_env(env):
                    logger.error("LLM budget Redis check failed in production fail-closed mode.")
                    return False, "LLM budget szolgáltatás átmenetileg nem elérhető.", None
                logger.warning("LLM budget Redis check failed, fallback to in-memory.")
        return self._acquire_memory(
            tenant_key=tenant_key,
            scope_key=scope_key,
            minute_bucket=minute_bucket,
            day_bucket=day_bucket,
            month_bucket=month_bucket,
            prompt_units=prompt_units,
            estimated_tokens=estimated_tokens,
            effective_daily_tokens=effective_daily_tokens,
            effective_monthly_tokens=effective_monthly_tokens,
        )

    def _acquire_memory(
        self,
        *,
        tenant_key: str,
        scope_key: str,
        minute_bucket: int,
        day_bucket: str,
        month_bucket: str,
        prompt_units: int,
        estimated_tokens: int,
        effective_daily_tokens: int,
        effective_monthly_tokens: int,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        key = (tenant_key, scope_key)
        with self._lock:
            state = self._state.get(key) or {
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
            if int(state["requests"]) + 1 > self.config.request_limit_per_minute:
                return False, "LLM kéréslimit elérve ebben a percben.", None
            if int(state["chars"]) + prompt_units > self.config.prompt_chars_per_minute:
                return False, "LLM prompt limit elérve ebben a percben.", None
            if int(state["inflight"]) >= self.config.concurrency_limit:
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
            self._state[key] = state
        return True, "", {"backend": "memory", "key": key}

    def release(self, reservation: dict[str, Any] | None) -> None:
        if not reservation:
            return
        backend = str(reservation.get("backend") or "")
        if backend == "redis":
            redis_client = self._redis_getter()
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
        with self._lock:
            state = self._state.get(key)
            if not state:
                return
            state["inflight"] = max(0, int(state.get("inflight") or 0) - 1)


__all__ = ["LlmBudgetConfig", "LlmBudgetManager"]
