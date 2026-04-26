"""Kernel biztonsági csomag — edge / infrastruktúra szintű védelem.

A `core.kernel.security` és a `core.kernel.middleware.security` modulok
technikai védelmeket tartalmaznak: JWT titok erőssége, cookie Secure/SameSite,
CSRF middleware, TrustedHost, rate limit tároló bekötés, refresh/access TTL
szanity check az induláskor.

Az **auth domain policy** (issuer/audience üzleti szerződés, jelszó/2FA/invite
szabályok, jogosultsági döntések, tokenhez kötött üzleti szabályok) a
`core.platform.auth` alatt él (pl. `security_policy.py`, `auth_dependencies.py`).
Ne helyezz el domain- vagy permission-logikát a kernel security rétegben.
"""

from __future__ import annotations

__all__: list[str] = []
