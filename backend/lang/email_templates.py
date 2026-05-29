# backend/lang/email_templates.py
# Feladat: Többnyelvű email subject/body sablonokat ad 2FA, set-password, demo login és demo set-password folyamatokhoz. Hu/en/es nyelvkódokra azonos template kulcsokat és placeholdereket tart, fallbackkel a default magyar nyelvre, valamint nyelvenkénti signature értékeket kezel. Email lokalizációs contract az EmailService számára.
# Sárközi Mihály - 2026.05.21

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
        "confirm_email_change": {
            "subject": "AIPLAZA - Erősítsd meg az új email címed",
            "body": """Kedves Felhasználó!

Email cím módosítást kezdeményeztél az AIPLAZA fiókodhoz.

Jelenlegi belépési email címed:
{current_email}

Megerősítésre váró új email címed:
{new_email}

Az új email cím aktiválásához kattints az alábbi linkre:

{confirm_email_link}

Amíg ezt nem erősíted meg, továbbra is a régi email címeddel tudsz belépni.

Ha nem te kezdeményezted ezt a módosítást, hagyd figyelmen kívül ezt az emailt.

Üdvözlettel,
{signature}""",
        },
        "demo_login": {
            "subject": "BrainBankCenter demo - A rendszered elkészült",
            "body": """Szia!

A demo környezeted elkészült, és az alábbi linken azonnal be tudsz lépni:

{demo_login_link}

A demo hozzáférés pontosan eddig érvényes:
{demo_expires_at}

Ha nem te kérted a demo létrehozását, hagyd figyelmen kívül ezt az emailt.

Üdvözlettel,
{signature}""",
        },
        "demo_set_password": {
            "subject": "BrainBankCenter demo - Állítsd be a jelszavad",
            "body": """Szia!

A demo környezeted elkészült. A továbblépéshez állítsd be a jelszavad az alábbi linken:

{set_password_link}

Ha beállítottad a jelszavadat, már tesztelheted is a rendszeredet.

A demo hozzáférés pontosan eddig érvényes:
{demo_expires_at}

Ha nem te kérted a demo létrehozását, hagyd figyelmen kívül ezt az emailt.

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
        "confirm_email_change": {
            "subject": "AIPLAZA - Confirm your new email address",
            "body": """Dear User,

You requested an email address change for your AIPLAZA account.

Current sign-in email:
{current_email}

New email waiting for confirmation:
{new_email}

To activate the new email address, open this link:

{confirm_email_link}

Until you confirm it, you can continue signing in with your old email address.

If you did not request this change, please ignore this email.

Best regards,
{signature}""",
        },
        "demo_login": {
            "subject": "BrainBankCenter demo - Your workspace is ready",
            "body": """Hello,

Your demo workspace is ready, and you can sign in immediately using this link:

{demo_login_link}

The demo access is valid exactly until:
{demo_expires_at}

If you did not request this demo, please ignore this email.

Best regards,
{signature}""",
        },
        "demo_set_password": {
            "subject": "BrainBankCenter demo - Set your password",
            "body": """Hello,

Your demo workspace is ready. To continue, set your password using the link below:

{set_password_link}

Once your password is set, you can start testing immediately.

The demo access is valid exactly until:
{demo_expires_at}

If you did not request this demo, please ignore this email.

Best regards,
{signature}""",
        },
    },
    "es": {
        "2fa": {
            "subject": "AIPLAZA - Código de autenticación de dos factores",
            "body": """Estimado/a usuario/a:

Tu código de autenticación de dos factores:

{code}

Este código es válido durante {expiry_minutes} minutos.

Si no solicitaste este inicio de sesión, ignora este correo.

Saludos,
{signature}""",
        },
        "2fa_token_block": "Token necesario para completar el inicio de sesión (paso 2, úsalo junto con el código):\n\n{pending_token}\n\n",
        "set_password": {
            "subject": "AIPLAZA - Configura tu contraseña",
            "body": """Estimado/a usuario/a:

Tu cuenta de AIPLAZA ha sido creada. Para iniciar sesión, configura tu contraseña en el siguiente enlace (dentro de 24 horas):

{set_password_link}

La contraseña debe tener al menos 6 caracteres e incluir minúsculas, mayúsculas y un número.

Si no solicitaste este registro, ignora este correo.

Saludos,
{signature}""",
        },
        "confirm_email_change": {
            "subject": "AIPLAZA - Confirma tu nueva dirección de correo",
            "body": """Estimado/a usuario/a:

Has solicitado cambiar la dirección de correo de tu cuenta de AIPLAZA.

Correo actual para iniciar sesión:
{current_email}

Nuevo correo pendiente de confirmación:
{new_email}

Para activar el nuevo correo, abre este enlace:

{confirm_email_link}

Hasta que lo confirmes, podrás seguir iniciando sesión con tu correo anterior.

Si no solicitaste este cambio, ignora este correo.

Saludos,
{signature}""",
        },
        "demo_login": {
            "subject": "BrainBankCenter demo - Tu entorno está listo",
            "body": """Hola:

Tu entorno demo está listo y puedes iniciar sesión inmediatamente con este enlace:

{demo_login_link}

El acceso demo es válido exactamente hasta:
{demo_expires_at}

Si no solicitaste esta demo, ignora este correo.

Saludos,
{signature}""",
        },
        "demo_set_password": {
            "subject": "BrainBankCenter demo - Configura tu contraseña",
            "body": """Hola:

Tu entorno demo está listo. Para continuar, configura tu contraseña en el siguiente enlace:

{set_password_link}

Cuando hayas configurado tu contraseña, podrás empezar a probar tu sistema.

El acceso demo es válido exactamente hasta:
{demo_expires_at}

Si no solicitaste esta demo, ignora este correo.

Saludos,
{signature}""",
        },
    },
}

DEFAULT_SIGNATURE = "AIPLAZA csapata"
DEFAULT_SIGNATURE_EN = "AIPLAZA Team"
DEFAULT_SIGNATURE_ES = "Equipo de AIPLAZA"


# Ez a függvény visszaadja a(z) lang logikáját.
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
    signatures = {
        "hu": DEFAULT_SIGNATURE,
        "en": DEFAULT_SIGNATURE_EN,
        "es": DEFAULT_SIGNATURE_ES,
    }
    kwargs.setdefault("signature", signatures.get(lang, DEFAULT_SIGNATURE))
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
