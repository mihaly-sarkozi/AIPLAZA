# apps/core/i18n/email_templates.py
# Email sablonok többnyelvűen. Kulcs: template_id (pl. "2fa", "set_password"), nyelv: "hu", "en", stb.
# A body placeholdereket a hívó tölti ki: {code}, {token_block}, {expiry_minutes}, {set_password_link}, stb.

from typing import Any

DEFAULT_LANG = "hu"

# template_id -> (subject, body) sablon; a body .format(**kwargs)-ra van készítve
_EMAIL_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "hu": {
        "2fa": {
            "subject": "AIPLAZA - Kétfaktoros autentikációs kód",
            "body": """Kedves Felhasználó!

A kétfaktoros autentikációs kódod:

{code}

Ez a kód {expiry_minutes} percig érvényes.

Ha nem te kezdeményezted ezt a bejelentkezést, kérjük, hagyd figyelmen kívül ezt az emailt.

Üdvözlettel,
{signature}""",
        },
        "2fa_token_block": "A belépés befejezéséhez szükséges token (2. lépésben add meg a kód mellett):\n\n{pending_token}\n\n",
        "set_password": {
            "subject": "AIPLAZA - Állítsd be a jelszavad",
            "body": """Kedves Felhasználó!

Az AIPLAZA fiókod létrejött. A belépéshez állítsd be a jelszavad az alábbi linken (24 órán belül):

{set_password_link}

A jelszónak legalább 6 karakter hosszúnak kell lennie, és tartalmazzon kisbetűt, nagybetűt és számot.

Ha nem kérted a regisztrációt, hagyd figyelmen kívül ezt az emailt.

Üdvözlettel,
{signature}""",
        },
    },
    "en": {
        "2fa": {
            "subject": "AIPLAZA - Two-factor authentication code",
            "body": """Dear User,

Your two-factor authentication code:

{code}

This code is valid for {expiry_minutes} minutes.

If you did not request this login, please ignore this email.

Best regards,
{signature}""",
        },
        "2fa_token_block": "Token required to complete login (step 2, use together with the code):\n\n{pending_token}\n\n",
        "set_password": {
            "subject": "AIPLAZA - Set your password",
            "body": """Dear User,

Your AIPLAZA account has been created. To sign in, set your password at the link below (within 24 hours):

{set_password_link}

The password must be at least 6 characters and contain lowercase, uppercase and a number.

If you did not request this registration, please ignore this email.

Best regards,
{signature}""",
        },
    },
}

DEFAULT_SIGNATURE = "AIPLAZA csapata"
DEFAULT_SIGNATURE_EN = "AIPLAZA Team"


def _get_lang(lang: str | None) -> str:
    if not lang or lang not in _EMAIL_TEMPLATES:
        return DEFAULT_LANG
    return lang


def get_email_template(
    template_id: str,
    lang: str | None = None,
    **kwargs: Any,
) -> tuple[str, str]:
    """
    Visszaadja (subject, body) a megadott sablonhoz és nyelvhez.
    A body placeholdereit a kwargs tölti ki (code, token_block, expiry_minutes, set_password_link, signature, stb.).
    """
    lang = _get_lang(lang)
    templates = _EMAIL_TEMPLATES.get(lang) or _EMAIL_TEMPLATES[DEFAULT_LANG]
    if template_id not in templates or "subject" not in templates[template_id]:
        raise ValueError(f"Unknown email template: {template_id}")
    t = templates[template_id]
    kwargs.setdefault("signature", DEFAULT_SIGNATURE if lang == "hu" else DEFAULT_SIGNATURE_EN)
    subject = t["subject"]
    body = t["body"].format(**kwargs)
    return subject, body


def get_2fa_token_block(pending_token: str, lang: str | None = None) -> str:
    """2FA emailhez: a token blokk szövege (ha van pending_token)."""
    if not pending_token:
        return ""
    lang = _get_lang(lang)
    templates = _EMAIL_TEMPLATES.get(lang) or _EMAIL_TEMPLATES[DEFAULT_LANG]
    block_tpl = templates.get("2fa_token_block", _EMAIL_TEMPLATES[DEFAULT_LANG]["2fa_token_block"])
    return block_tpl.format(pending_token=pending_token)
