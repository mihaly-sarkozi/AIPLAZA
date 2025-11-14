from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class User:
    id: int
    email: str
    password_hash: str
    is_active: bool
    role: str
    created_at: datetime