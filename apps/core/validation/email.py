# apps/core/validation/email.py
# Email formátum és hossz validáció (központi; audit/regisztráció/bejelentkezés).
#
# Fontos: ez „józan ész” / best-effort szintű validáció, NEM teljes RFC 5322 megfelelés.
# Cél: nyilvánvaló hibák és túl hosszú/rovid értékek kiszűrése; nem „max hardening”.
#
# Amit NEM kezelünk (legitim címek vagy edge case-ek kieshetnek / átcsúszhatnak):
#   - idézett local part ("...@domain.com"), szóköz, komment
#   - domain literálok (pl. [IPv6:...])
#   - nemzetközi címek (IDN / punycode)
#   - minden RFC 5322 speciális karakter a local part-ban
# Teljes megfeleléshez: pl. email-validator könyvtár vagy külső szolgáltatás (deliverability).
# 2026.03 - Sárközi Mihály

import re

# Best-effort minta: local@domain.tld
# - Local: betű/szám és ._%+- , de nincs kezdő/záró pont, nincs két egymást követő pont
# - Domain: label.label.tld; label = betű/szám és kötjel, nincs kezdő/záró kötjel vagy pont
# - TLD: legalább 2 betű
EMAIL_PATTERN = re.compile(
    r"^"
    r"[a-zA-Z0-9_%+-]+(?:\.[a-zA-Z0-9_%+-]+)*"  # local: pl. user.name+tag
    r"@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*"  # domain labels
    r"\.[a-zA-Z]{2,}"
    r"$"
)
EMAIL_MAX_LEN = 255
EMAIL_MIN_LEN = 5  # a@b.co


def is_valid_email(value: str | None) -> bool:
    """
    Best-effort email formátum és hossz ellenőrzés.
    Köznapi szint: kiszűri a nyilvánvalóan hibás és túl hosszú/rovid értékeket.
    Nem teljes körű RFC validáció; sok legitim vagy edge-case cím kieshet/átcsúszhat.
    """
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    if len(s) > EMAIL_MAX_LEN or len(s) < EMAIL_MIN_LEN:
        return False
    return bool(EMAIL_PATTERN.match(s))
