# apps/auth/application/services/user_service.py
"""
User kezelési szolgáltatás.
"""

from __future__ import annotations
from passlib.hash import bcrypt_sha256 as pwd_hasher
from apps.auth.ports.repositories import UserRepositoryPort
from apps.auth.domain.user import User


class UserService:
    def __init__(self, users: UserRepositoryPort):
        self.users = users

    def list_all(self) -> list[User]:
        """Összes user listázása."""
        return self.users.list_all()

    def get_by_id(self, user_id: int) -> User | None:
        """User lekérése ID alapján."""
        return self.users.get_by_id(user_id)

    def create(self, email: str, password: str, role: str = "user", is_superuser: bool = False) -> User:
        """Új user létrehozása."""
        # Email ellenőrzés
        if self.users.get_by_email(email):
            raise ValueError("Email already exists")
        
        # Role ellenőrzés
        if role not in ["user", "admin"]:
            raise ValueError("Invalid role. Must be 'user' or 'admin'")
        
        # Superuser csak admin role-lal lehet
        if is_superuser and role != "admin":
            raise ValueError("Superuser must have admin role")
        
        # Jelszó hash
        password_hash = pwd_hasher.hash(password)
        
        # User létrehozása
        user = User.new(
            email=email,
            password_hash=password_hash,
            role=role,
            is_superuser=is_superuser
        )
        
        return self.users.create(user)

    def update(self, user_id: int, email: str | None = None, role: str | None = None, is_active: bool | None = None) -> User:
        """User frissítése."""
        user = self.users.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Superuser nem módosítható
        if user.is_superuser:
            raise ValueError("Superuser cannot be modified")
        
        # Email ellenőrzés (ha változott)
        if email and email != user.email:
            if self.users.get_by_email(email):
                raise ValueError("Email already exists")
        
        # Role ellenőrzés
        if role and role not in ["user", "admin"]:
            raise ValueError("Invalid role. Must be 'user' or 'admin'")
        
        # Frissítés
        updates = {}
        if email:
            updates["email"] = email
        if role:
            updates["role"] = role
        if is_active is not None:
            updates["is_active"] = is_active
        
        updated_user = user.with_updates(**updates)
        return self.users.update(updated_user)

    def delete(self, user_id: int) -> None:
        """User törlése."""
        user = self.users.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Superuser nem törölhető
        if user.is_superuser:
            raise ValueError("Superuser cannot be deleted")
        
        self.users.delete(user_id)

