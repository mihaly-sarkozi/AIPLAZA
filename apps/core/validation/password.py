# apps/core/validation/password.py
# Jelszó erősség: min hossz, max hossz, nagybetű, kisbetű, szám, speciális karakter.
# Központi réteg: route/Pydantic és service is használhatja.

from typing import Tuple

PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128


def _has_special_char(s: str) -> bool:
    """Legalább egy nem betű és nem szám karakter (pl. !@#$%^&*)."""
    return any(not c.isalnum() for c in s)


def validate_password_strength(password: str | None) -> Tuple[bool, str]:
    """
    Ellenőrzi a jelszó erősségét.
    Követelmények: min/max hossz, nagybetű, kisbetű, szám, speciális karakter.
    Vissza: (True, "") ha ok, (False, "hibaüzenet") ha gyenge.
    """
    if not password or not isinstance(password, str):
        return False, "Jelszó megadása kötelező."
    p = password
    if len(p) < PASSWORD_MIN_LEN:
        return False, f"A jelszónak legalább {PASSWORD_MIN_LEN} karakter hosszúnak kell lennie."
    if len(p) > PASSWORD_MAX_LEN:
        return False, f"A jelszó legfeljebb {PASSWORD_MAX_LEN} karakter lehet."
    if not any(c.isupper() for c in p):
        return False, "A jelszónak tartalmaznia kell legalább egy nagybetűt."
    if not any(c.islower() for c in p):
        return False, "A jelszónak tartalmaznia kell legalább egy kisbetűt."
    if not any(c.isdigit() for c in p):
        return False, "A jelszónak tartalmaznia kell legalább egy számot."
    if not _has_special_char(p):
        return False, "A jelszónak tartalmaznia kell legalább egy speciális karaktert (pl. !@#$%)."
    return True, ""
