from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from apps.api.di import _token_service, get_login_service
from features.auth.domain.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    creds: HTTPAuthorizationCredentials = Depends(bearer)
) -> int:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = _token_service.verify(creds.credentials)
        if payload.get("typ") != "access":
            raise HTTPException(status_code=401, detail="Wrong token type")
        return int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    login_service = Depends(get_login_service)
) -> User:
    user = login_service.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
