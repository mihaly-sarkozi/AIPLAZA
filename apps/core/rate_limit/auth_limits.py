# apps/core/rate_limit/auth_limits.py
# Célzott limitek: login step1 per email (10/óra), login step2 per pending_token (5/perc).
# A limiter middleware csak IP-t lát; ezt a modult a route hívja a body alapján.
# 2026.03 - Sárközi Mihály

import threading
import time
from collections import defaultdict

# email -> list of timestamps (last hour)
_email_attempts: dict[str, list[float]] = defaultdict(list)
_email_lock = threading.Lock()

# pending_token -> list of timestamps (last minute)
_pending_attempts: dict[str, list[float]] = defaultdict(list)
_pending_lock = threading.Lock()

LOGIN_STEP1_MAX_PER_EMAIL = 10
LOGIN_STEP1_WINDOW_SEC = 3600  # 1 óra

LOGIN_STEP2_MAX_PER_TOKEN = 5
LOGIN_STEP2_WINDOW_SEC = 60  # 1 perc


def _prune(attempts: list[float], window_sec: float, now: float) -> list[float]:
    return [t for t in attempts if now - t < window_sec]


def check_login_step1_email(email: str) -> bool:
    """
    Login step1: max 10 kísérlet / óra / email.
    Vissza: True = engedélyezve, False = limit túllépve (429).
    """
    if not (email and email.strip()):
        return True
    key = email.strip().lower()
    now = time.monotonic()
    with _email_lock:
        _email_attempts[key] = _prune(_email_attempts[key], LOGIN_STEP1_WINDOW_SEC, now)
        if len(_email_attempts[key]) >= LOGIN_STEP1_MAX_PER_EMAIL:
            return False
        _email_attempts[key].append(now)
    return True


def check_login_step2_pending_token(pending_token: str) -> bool:
    """
    Login step2: max 5 kísérlet / perc / pending_token.
    Vissza: True = engedélyezve, False = limit túllépve (429).
    """
    if not (pending_token and pending_token.strip()):
        return True
    key = pending_token.strip()
    now = time.monotonic()
    with _pending_lock:
        _pending_attempts[key] = _prune(_pending_attempts[key], LOGIN_STEP2_WINDOW_SEC, now)
        if len(_pending_attempts[key]) >= LOGIN_STEP2_MAX_PER_TOKEN:
            return False
        _pending_attempts[key].append(now)
    return True
