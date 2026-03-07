# apps/core/security/security_logger.py
# Biztonsági események logolása – hacking / érvénytelen belépés–kilépés
# Hol hívódik:
#   - LoginService: login_invalid_user_attempt, login_inactive_user_attempt,
#     login_bad_password_attempt, login_successful_login
#   - LogoutService: logout_expired_token, logout_invalid_token, logout_wrong_type,
#     logout_unknown_jti, logout_replay_detected, logout_success
#   - RefreshService: refresh_expired_token, refresh_invalid_token, refresh_wrong_type,
#     refresh_unknown_jti, refresh_reuse_detected, refresh_session_expired, refresh_success
#
# Monitoring: a "security" logger kimenetét érdemes külön fájlba / SIEM-be irányítani
# (logging config: handlers, formatters). Metrikához: itt vagy egy middleware-ben
# számolj pl. login_failures_total, logout_invalid_total (Prometheus, StatsD, stb.).
# 2026.03.07 - Sárközi Mihály

import logging

# Dedikált logger: konfigban külön kezelhető (fájl, szint, formátum)
_log = logging.getLogger("security")


class SecurityLogger:

    # --- LOGIN (érvénytelen / gyanús = WARNING, sikeres = INFO) ---
    def login_invalid_user_attempt(self, email, ip, ua):
        _log.warning("login_invalid_user email=%s ip=%s ua=%s", email, ip, ua)

    def login_inactive_user_attempt(self, user_id, ip, ua):
        _log.warning("login_inactive_user user_id=%s ip=%s ua=%s", user_id, ip, ua)

    def login_bad_password_attempt(self, user_id, ip, ua):
        _log.warning("login_bad_password user_id=%s ip=%s ua=%s", user_id, ip, ua)

    def login_successful_login(self, user_id, ip, ua):
        _log.info("login_ok user_id=%s ip=%s ua=%s", user_id, ip, ua)

    # --- LOGOUT (érvénytelen / támadás gyanú = WARNING/ERROR) ---
    def logout_expired_token(self, ip, ua):
        _log.warning("logout_expired_token ip=%s ua=%s", ip, ua)

    def logout_invalid_token(self, ip, ua):
        _log.error("logout_invalid_token ip=%s ua=%s", ip, ua)

    def logout_wrong_type(self, ip, ua):
        _log.warning("logout_wrong_type ip=%s ua=%s", ip, ua)

    def logout_unknown_jti(self, user_id, ip, ua):
        _log.warning("logout_unknown_jti user_id=%s ip=%s ua=%s", user_id, ip, ua)

    def logout_replay_detected(self, user_id, ip, ua):
        _log.error("logout_replay_detected user_id=%s ip=%s ua=%s", user_id, ip, ua)

    def logout_success(self, user_id, ip, ua):
        _log.info("logout_ok user_id=%s ip=%s ua=%s", user_id, ip, ua)

    # --- REFRESH (érvénytelen / token reuse = ERROR) ---
    def refresh_expired_token(self, ip, ua):
        _log.warning("refresh_expired_token ip=%s ua=%s", ip, ua)

    def refresh_invalid_token(self, ip, ua):
        _log.error("refresh_invalid_token ip=%s ua=%s", ip, ua)

    def refresh_wrong_type(self, ip, ua):
        _log.warning("refresh_wrong_type ip=%s ua=%s", ip, ua)

    def refresh_unknown_jti(self, user_id, ip, ua):
        _log.warning("refresh_unknown_jti user_id=%s ip=%s ua=%s", user_id, ip, ua)

    def refresh_reuse_detected(self, user_id, ip, ua):
        _log.error("refresh_reuse_detected user_id=%s ip=%s ua=%s", user_id, ip, ua)

    def refresh_session_expired(self, user_id, ip, ua):
        _log.warning("refresh_session_expired user_id=%s ip=%s ua=%s", user_id, ip, ua)

    def refresh_success(self, user_id, ip, ua):
        _log.info("refresh_ok user_id=%s ip=%s ua=%s", user_id, ip, ua)