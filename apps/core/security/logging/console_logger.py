# apps/core/security/logging/console_logger.py
from apps.core.security.logging.ports import SecurityLoggerPort

class ConsoleSecurityLogger(SecurityLoggerPort):
    def invalid_user_attempt(self, email, ip, ua):
        print(f"[SEC][INVALID USER] email={email}, ip={ip}, ua={ua}")

    def inactive_user_attempt(self, user_id, ip, ua):
        print(f"[SEC][INACTIVE USER] user={user_id}, ip={ip}, ua={ua}")

    def bad_password_attempt(self, user_id, ip, ua):
        print(f"[SEC][BAD PASSWORD] user={user_id}, ip={ip}, ua={ua}")

    def refresh_reuse_attempt(self, user_id, ip, ua):
        print(f"[SEC][REFRESH REUSE] user={user_id}, ip={ip}, ua={ua}")

    def successful_login(self, user_id, ip, ua):
        print(f"[SEC][LOGIN OK] user={user_id}, ip={ip}, ua={ua}")
