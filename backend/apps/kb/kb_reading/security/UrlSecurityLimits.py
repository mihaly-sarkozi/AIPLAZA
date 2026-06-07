from __future__ import annotations

# backend/apps/kb/kb_reading/security/UrlSecurityLimits.py
# Feladat: Hálózati cím limit és segédfüggvények.
# Sárközi Mihály - 2026.06.07
from apps.kb.kb_reading.security.ReadingUrlSecurityError import ReadingUrlSecurityError
from core.kernel.config.config_loader import settings
from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig

_DEFAULT_ALLOWED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "application/json",
)

def max_url_response_bytes(*, config: ReadingConfig | None = None) -> int:
    """Megadja a letöltés maximális méretét."""
    _ = config
    return max(
        1024,
        int(
            getattr(settings, "kb_reading_url_max_response_bytes", None)
            or getattr(settings, "knowledge_url_ingest_max_response_bytes", 2 * 1024 * 1024)
            or (2 * 1024 * 1024),
        ),
    )
def max_url_redirects(*, config: ReadingConfig | None = None) -> int:
    """Megadja az átirányítások maximális számát."""
    _ = config
    return max(
        0,
        min(
            5,
            int(
                getattr(settings, "kb_reading_url_max_redirects", None)
                or getattr(settings, "knowledge_url_ingest_max_redirects", 3)
                or 3,
            ),
        ),
    )
def allowed_content_types() -> tuple[str, ...]:
    """Megadja az engedélyezett tartalom típusokat."""
    raw = getattr(
        settings,
        "kb_reading_url_allowed_content_types",
        getattr(settings, "knowledge_url_ingest_allowed_content_types", None),
    )
    if isinstance(raw, str) and raw.strip():
        values = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
        return values or _DEFAULT_ALLOWED_CONTENT_TYPES
    if isinstance(raw, (list, tuple, set)):
        values = tuple(str(item).strip().lower() for item in raw if str(item).strip())
        return values or _DEFAULT_ALLOWED_CONTENT_TYPES
    return _DEFAULT_ALLOWED_CONTENT_TYPES
def is_forbidden_ip(address: str) -> bool:
    """Eldönti, hogy tiltott cím-e."""
    ip = ipaddress.ip_address(address)
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ),
    )
def resolve_public_host(hostname: str) -> list[str]:
    """Feloldja a nyilvános gazdagép nevét."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ReadingUrlSecurityError(
            "DNS_RESOLUTION_FAILED",
            "The provided URL host could not be resolved.",
        ) from exc
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        address = str(sockaddr[0])
        if address in addresses:
            continue
        if is_forbidden_ip(address):
            raise ReadingUrlSecurityError(
                "PRIVATE_IP_BLOCKED",
                "The provided URL points to a blocked private IP.",
            )
        addresses.append(address)
    if not addresses:
        raise ReadingUrlSecurityError(
            "DNS_RESOLUTION_FAILED",
            "The provided URL host could not be resolved.",
        )
    return addresses
def _map_validation_error(message: str) -> str:
    """Validálási hibát fordít belső kódra."""
    lowered = message.lower()
    if "credential" in lowered or "userinfo" in lowered:
        return "USERINFO_NOT_ALLOWED"
    if "scheme" in lowered:
        return "INVALID_SCHEME"
    if "too long" in lowered:
        return "INVALID_SCHEME"
    if "invalid url" in lowered:
        return "INVALID_SCHEME"
    return "INVALID_SCHEME"


__all__ = ['allowed_content_types', 'is_forbidden_ip', 'max_url_redirects', 'max_url_response_bytes', 'resolve_public_host', '_map_validation_error']
