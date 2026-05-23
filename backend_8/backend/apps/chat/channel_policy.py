# backend/apps/chat/channel_policy.py
# Feladat: Channel credential normalizálási, origin és secret helper függvényeket tartalmaz. Lista deduplikálást, widget origin validációt, origin normalizálást és pepperelt secret hash képzést választ le a repositoryról. Program-specifikus channel credential policy réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hmac
import hashlib
import ipaddress
import time
from urllib.parse import urlparse

from core.kernel.config.config_loader import settings
from core.kernel.config.environment import is_deployed_env
from core.kernel.security.rate_limit import get_rate_limit_redis

_replay_fallback_seen: dict[str, float] = {}


def normalize_list(values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        value = str(item or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def normalize_widget_origin(value: str) -> str:
    text_value = str(value or "").strip().lower()
    if not text_value:
        raise ValueError("Az allowed_origins nem tartalmazhat üres elemet.")
    if "*" in text_value:
        raise ValueError("Wildcard origin nem engedélyezett widget credentialnél.")
    if "://" not in text_value:
        text_value = f"https://{text_value}"
    parsed = urlparse(text_value)
    scheme = str(parsed.scheme or "").strip().lower()
    host = str(parsed.hostname or "").strip().lower()
    port = parsed.port
    if scheme not in {"http", "https"}:
        raise ValueError("Widget origin csak http vagy https lehet.")
    if not host:
        raise ValueError("Widget origin host kötelező.")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Widget origin csak protocol+host formátum lehet (útvonal nélkül).")
    if parsed.username or parsed.password:
        raise ValueError("Widget origin nem tartalmazhat userinfo részt.")
    if ":" in host and not host.startswith("["):
        raise ValueError("Widget origin host formátuma érvénytelen.")
    if port is not None:
        return f"{scheme}://{host}:{int(port)}"
    return f"{scheme}://{host}"


def normalize_widget_origins(values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        normalized = normalize_widget_origin(str(item or ""))
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def hash_channel_secret(secret: str) -> str:
    pepper = str(getattr(settings, "jwt_secret", "") or "aiplaza").strip()
    payload = f"{pepper}:{secret}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def origin_value(origin: str | None) -> str:
    text_value = str(origin or "").strip()
    if not text_value:
        return ""
    try:
        parsed = urlparse(text_value)
        scheme = str(parsed.scheme or "").strip().lower()
        host = str(parsed.hostname or "").strip().lower()
        port = parsed.port
        if scheme not in {"http", "https"} or not host:
            return ""
        if port is not None:
            return f"{scheme}://{host}:{int(port)}"
        return f"{scheme}://{host}"
    except Exception:
        return ""


def normalize_ip_ranges(values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        value = str(item or "").strip()
        if not value:
            continue
        try:
            if "/" in value:
                normalized = str(ipaddress.ip_network(value, strict=False))
            else:
                normalized = str(ipaddress.ip_address(value))
        except ValueError as exc:
            raise ValueError(f"Érvénytelen IP allowlist elem: {value}") from exc
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def remote_ip_allowed(remote_ip: str | None, allowed_ranges: list[str]) -> bool:
    if not allowed_ranges:
        return False
    raw_ip = str(remote_ip or "").strip()
    if not raw_ip:
        return False
    try:
        client_ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        return raw_ip in allowed_ranges
    for item in allowed_ranges:
        try:
            if "/" in item:
                if client_ip in ipaddress.ip_network(item, strict=False):
                    return True
            elif client_ip == ipaddress.ip_address(item):
                return True
        except ValueError:
            if raw_ip == item:
                return True
    return False


def verify_channel_signature(
    *,
    secret: str,
    method: str,
    path: str,
    body: bytes,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
    body_hash: str | None = None,
    credential_id: int,
) -> tuple[bool, str]:
    normalized_timestamp = str(timestamp or "").strip()
    normalized_nonce = str(nonce or "").strip()
    normalized_signature = str(signature or "").strip()
    normalized_body_hash = str(body_hash or "").strip().lower()
    if not normalized_timestamp or not normalized_nonce or not normalized_signature:
        return False, "missing_signature_headers: Missing channel request signature headers."
    if len(normalized_nonce) < 12 or len(normalized_nonce) > 128:
        return False, "invalid_nonce: Invalid channel request nonce."
    try:
        request_ts = int(normalized_timestamp)
    except ValueError:
        return False, "invalid_timestamp: Invalid channel request timestamp."
    now = int(time.time())
    max_skew_sec = max(30, int(getattr(settings, "channel_signature_max_skew_sec", 300) or 300))
    if abs(now - request_ts) > max_skew_sec:
        return False, "expired_timestamp: Expired channel request signature."
    actual_body_hash = hashlib.sha256(body or b"").hexdigest()
    if normalized_body_hash and not hmac.compare_digest(actual_body_hash, normalized_body_hash):
        return False, "invalid_body_hash: Invalid channel request body hash."
    expected = _channel_signature(
        secret=secret,
        method=method,
        path=path,
        body=body,
        timestamp=normalized_timestamp,
        nonce=normalized_nonce,
    )
    incoming = normalized_signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, incoming):
        return False, "invalid_signature: Invalid channel request signature."
    nonce_ttl_sec = max_skew_sec + max(30, int(max_skew_sec * 0.2))
    replay_seen, replay_error = _replay_seen_or_record(credential_id=credential_id, nonce=normalized_nonce, ttl_sec=nonce_ttl_sec)
    if replay_error:
        return False, f"{replay_error}: Signed request replay protection unavailable."
    if replay_seen:
        return False, "reused_nonce: Replay channel request rejected."
    return True, ""


def _channel_signature(*, secret: str, method: str, path: str, body: bytes, timestamp: str, nonce: str) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    payload = "\n".join(
        [
            str(method or "POST").upper(),
            str(path or "/"),
            str(timestamp),
            str(nonce),
            body_hash,
        ]
    ).encode("utf-8")
    return hmac.new(str(secret or "").encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _replay_seen_or_record(*, credential_id: int, nonce: str, ttl_sec: int) -> tuple[bool, str]:
    key = f"channel:sig:{int(credential_id)}:{nonce}"
    redis_client = get_rate_limit_redis()
    if redis_client is not None:
        try:
            return not bool(redis_client.set(key, "1", nx=True, ex=max(1, int(ttl_sec)))), ""
        except Exception:
            if is_deployed_env():
                return False, "redis_unavailable"
    elif is_deployed_env():
        return False, "redis_unavailable"
    now = time.time()
    cutoff = now - max(1, int(ttl_sec))
    for item_key, expires_at in list(_replay_fallback_seen.items()):
        if expires_at <= cutoff:
            _replay_fallback_seen.pop(item_key, None)
    if key in _replay_fallback_seen and _replay_fallback_seen[key] > now:
        return True, ""
    _replay_fallback_seen[key] = now + max(1, int(ttl_sec))
    return False, ""


__all__ = [
    "hash_channel_secret",
    "normalize_list",
    "normalize_ip_ranges",
    "normalize_widget_origin",
    "normalize_widget_origins",
    "origin_value",
    "remote_ip_allowed",
    "verify_channel_signature",
]
