# apps/core/validation/password.py
# Jelszó erősség: min hossz, max hossz, opcionális komplexitás (nagybetű, szám, speciális).
# Központi réteg: route/Pydantic és service is használhatja.

from typing import Tuple

PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128


def validate_password_strength(password: str | None) -> Tuple[bool, str]:
    """
    Ellenőrzi a jelszó erősségét.
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
    return True, ""
