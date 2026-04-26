# Email formatum es hossz validacio kozponti hasznalatra.
#
# Fontos: ez best-effort szintu validacio, nem teljes RFC 5322 megfeleles.

import re

# Best-effort minta: local@domain.tld
# - Local: betu/szam es ._%+- , de nincs kezdo/zaro pont, nincs ket egymast koveto pont
# - Domain: label.label.tld; label = betu/szam es kotjel, nincs kezdo/zaro kotjel vagy pont
# - TLD: legalabb 2 betu
EMAIL_PATTERN = re.compile(
    r"^"
    r"[a-zA-Z0-9_%+-]+(?:\.[a-zA-Z0-9_%+-]+)*"
    r"@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}"
    r"$"
)
EMAIL_MAX_LEN = 255
EMAIL_MIN_LEN = 5  # a@b.co


def is_valid_email(value: str | None) -> bool:
    """
    Best-effort email formatum es hossz ellenorzes.
    Koznapi szint: kiszuri a nyilvanvaloan hibas es tul hosszu/rovid ertekeket.
    Nem teljes koru RFC validacio; sok legitim vagy edge-case cim kieshet/atcsuszhat.
    """
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    if len(s) > EMAIL_MAX_LEN or len(s) < EMAIL_MIN_LEN:
        return False
    return bool(EMAIL_PATTERN.match(s))
