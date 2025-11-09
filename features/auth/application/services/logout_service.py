# features/auth/application/services/logout_service.py
from infrastructure.security.tokens import TokenService
from features.auth.ports.repositories import SessionRepositoryPort

class LogoutService:
    def __init__(self, sessions: SessionRepositoryPort, tokens: TokenService):
        self.sessions = sessions
        self.tokens = tokens

    def logout(self, refresh_token: str):
        try:
            payload = self.tokens.verify(refresh_token)
            if payload.get("typ") != "refresh":
                return False

            hashed = self.tokens.hash_token(refresh_token)
            session = self.sessions.get_by_jti(payload["jti"])
            if not session or session.token_hash != hashed:
                return False

            updated = session.invalidate()
            self.sessions.update(updated)
            return True
        except Exception:
            return False