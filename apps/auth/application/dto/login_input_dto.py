# apps/auth/application/dto/login_input_dto.py
# Login bemenetből egy DTO osztályt készít
# 2026.02.28 - Sárközi Mihály

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LoginInput:
    """Login use case bemenet: 1. lépés (email+jelszó) vagy 2. lépés (pending_token+two_factor_code) + ip, ua, auto_login. Tenant = search_path (middleware)."""
    email: Optional[str]
    password: Optional[str]
    pending_token: Optional[str]
    two_factor_code: Optional[str]
    ip: Optional[str]
    ua: Optional[str]
    auto_login: bool = False
