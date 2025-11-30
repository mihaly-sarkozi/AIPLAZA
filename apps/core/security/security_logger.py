class SecurityLogger:

    # --- LOGIN LOGGER---
    def login_invalid_user_attempt(self, email, ip, ua):
        print(f"[SEC] Invalid user attempt: email={email}, ip={ip}, ua={ua}")

    def login_inactive_user_attempt(self, user_id, ip, ua):
        print(f"[SEC] Inactive user login: user={user_id}, ip={ip}, ua={ua}")

    def login_bad_password_attempt(self, user_id, ip, ua):
        print(f"[SEC] Wrong password: user={user_id}, ip={ip}, ua={ua}")

    def login_successful_login(self, user_id, ip, ua):
        print(f"[SEC] Login OK: user={user_id}, ip={ip}, ua={ua}")

    # --- LOGOUT LOGGER---
    def logout_expired_token(self, ip, ua):
        print(f"[SEC] Logout: expired token used. ip={ip}, ua={ua}")

    def logout_invalid_token(self, ip, ua):
        print(f"[SEC] Logout: invalid or forged token! ip={ip}, ua={ua}")

    def logout_wrong_type(self, ip, ua):
        print(f"[SEC] Logout: wrong JWT type (not refresh). ip={ip}, ua={ua}")

    def logout_unknown_jti(self, user_id, ip, ua):
        print(f"[SEC] Logout: refresh jti not found for user={user_id}. ip={ip}, ua={ua}")

    def logout_replay_detected(self, user_id, ip, ua):
        print(f"[SEC] Logout: replay attack detected for user={user_id}! ip={ip}, ua={ua}")

    def logout_success(self, user_id, ip, ua):
        print(f"[SEC] Logout OK: user={user_id}, ip={ip}, ua={ua}")

    # --- REFRESH LOGGER---
    def refresh_expired_token(self, ip, ua):
        print(f"[SEC] Refresh failed: expired token. ip={ip}, ua={ua}")

    def refresh_invalid_token(self, ip, ua):
        print(f"[SEC] Refresh failed: invalid/forged token! ip={ip}, ua={ua}")

    def refresh_wrong_type(self, ip, ua):
        print(f"[SEC] Refresh failed: wrong JWT typ. ip={ip}, ua={ua}")

    def refresh_unknown_jti(self, user_id, ip, ua):
        print(f"[SEC] Refresh failed: unknown JTI for user={user_id}. ip={ip}, ua={ua}")

    def refresh_reuse_detected(self, user_id, ip, ua):
        print(f"[SEC] Refresh REUSE DETECTED (stolen token!) user={user_id}, ip={ip}, ua={ua}")

    def refresh_session_expired(self, user_id, ip, ua):
        print(f"[SEC] Refresh failed: session expired for user={user_id}. ip={ip}, ua={ua}")

    def refresh_success(self, user_id, ip, ua):
        print(f"[SEC] Refresh OK: user={user_id}, ip={ip}, ua={ua}")