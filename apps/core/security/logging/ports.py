# apps/core/security/logging/ports.py
from abc import ABC, abstractmethod

class SecurityLoggerPort(ABC):

    @abstractmethod
    def invalid_user_attempt(self, email, ip, ua): ...

    @abstractmethod
    def inactive_user_attempt(self, user_id, ip, ua): ...

    @abstractmethod
    def bad_password_attempt(self, user_id, ip, ua): ...

    @abstractmethod
    def refresh_reuse_attempt(self, user_id, ip, ua): ...

    @abstractmethod
    def successful_login(self, user_id, ip, ua): ...
