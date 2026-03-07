# apps/core/email/email_service.py
# Email küldés szolgáltatás (SMTP, pl. Gmail 587 + STARTTLS).
# Dev: szimulált küldésnél csak maszkolt body preview kerül logba (2FA kód, token, link token ne).
# 2026.03.07 - Sárközi Mihály

import re
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config.settings import settings
from apps.core.i18n.email_templates import get_email_template, get_2fa_token_block, DEFAULT_LANG

# Maximális body hossz a dev log preview-ban (maszkolás után).
_DEV_LOG_BODY_PREVIEW_LEN = 280


def mask_email_body_for_log(body: str, max_len: int = _DEV_LOG_BODY_PREVIEW_LEN) -> str:
    """
    Érzékeny részek maszkolása, hogy a dev email log ne tartalmazzon 2FA kódot, pending tokent vagy link tokent.
    Vissza: maszkolt szöveg, max_len hosszig; ha hosszabb, \"... (N chars)\" utótag.
    """
    if not body:
        return ""
    s = body
    # 6 számjegyű 2FA kód (önálló sor vagy szóközzel körülvéve) → ******
    s = re.sub(r"\b\d{6}\b", "******", s)
    # Hosszú hex/alfanumerikus token (pl. pending_token 32 hex, vagy link token) → [REDACTED]
    s = re.sub(r"\b[a-zA-Z0-9]{20,}\b", "[REDACTED]", s)
    # URL token= érték maszkolása (set_password_link): token=xxx → token=[REDACTED]
    s = re.sub(r"([?&]token=)([^&\s]+)", r"\1[REDACTED]", s, flags=re.IGNORECASE)
    if len(s) > max_len:
        s = s[:max_len].rstrip() + f" ... ({len(body)} chars)"
    return s


class EmailService:
    """Email küldés szolgáltatás SMTP-vel."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ):
        self.host = (host or settings.smtp_host or "").strip()
        self.port = port or settings.smtp_port
        self.user = (user or settings.smtp_user or "").strip()
        self.password = (password or settings.smtp_password or "").strip()
        self.from_email = (from_email or settings.smtp_from_email or "").strip()
        self.from_name = (from_name or settings.smtp_from_name or "").strip()
    
    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        """
        Email küldése.
        
        Returns:
            True ha sikeres, False ha hiba történt
        """
        if not self.user or not self.password:
            # Ha nincs beállítva SMTP, csak logoljuk (dev környezetben). Body NEM megy ki teljesen: maszkolt preview (2FA kód, token, link token ne).
            preview = mask_email_body_for_log(body)
            print(f"[EMAIL SERVICE] Email küldés szimulálva:")
            print(f"  To: {to_email}")
            print(f"  Subject: {subject}")
            print(f"  Body (masked preview): {preview}")
            return True
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email

            msg.attach(MIMEText(body, 'html' if is_html else 'plain', 'utf-8'))

            context = ssl.create_default_context()

            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                # Gmail app jelszó: egyes kliensek szóközzel, mások nélkül fogadja – mindkettőt kipróbáljuk
                try:
                    server.login(self.user, self.password)
                except smtplib.SMTPAuthenticationError:
                    pw_no_spaces = self.password.replace(" ", "")
                    if pw_no_spaces != self.password:
                        server.login(self.user, pw_no_spaces)
                    else:
                        raise
                server.send_message(msg)

            return True

        except Exception as e:
            # Stabil kód a logban (monitorozás); a felhasználói üzenet a routerben i18n (ErrorCode.TWO_FACTOR_EMAIL_FAILED)
            print(f"[EMAIL SERVICE] email_send_failed: {e}")
            return False
    
    
    def send_2fa_code(
        self,
        to_email: str,
        code: str,
        pending_token: str | None = None,
        lang: str | None = None,
        expiry_minutes: int = 10,
    ) -> bool:
        """
        Kétfaktoros kód (és opcionálisan pending_token) küldése emailben. Szöveg: i18n sablon.
        """
        token_block = get_2fa_token_block(pending_token or "", lang=lang)
        subject, body = get_email_template(
            "2fa",
            lang=lang or DEFAULT_LANG,
            code=code,
            token_block=token_block,
            expiry_minutes=expiry_minutes,
        )
        return self.send_email(to_email, subject, body)

    def send_set_password_invite(
        self,
        to_email: str,
        set_password_link: str,
        lang: str | None = None,
    ) -> bool:
        """
        Meghívó email: jelszó beállítás link. Szöveg: i18n sablon.
        """
        subject, body = get_email_template(
            "set_password",
            lang=lang or DEFAULT_LANG,
            set_password_link=set_password_link,
        )
        return self.send_email(to_email, subject, body)

