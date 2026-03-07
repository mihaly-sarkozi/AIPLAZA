# apps/auth/application/dto/__init__.py
"""Login use case application rétegbeli DTO-k: bemenet (LoginInput) és kimenet (LoginSuccess, LoginTwoFactorRequired)."""
from typing import Optional

from apps.auth.application.dto.login_input_dto import LoginInput
from apps.auth.application.dto.login_success_dto import LoginSuccess
from apps.auth.application.dto.login_two_factor_required_dto import LoginTwoFactorRequired

LoginResult = Optional[LoginSuccess | LoginTwoFactorRequired]

__all__ = ["LoginInput", "LoginSuccess", "LoginTwoFactorRequired", "LoginResult"]
