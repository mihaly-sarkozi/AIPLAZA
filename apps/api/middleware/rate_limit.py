from slowapi import Limiter
from slowapi.util import get_remote_address

def user_or_ip_key(request):
    user = getattr(request.state, "user", None)
    if user and getattr(user, "sub", None):
        return f"user:{user.sub}"
    return f"ip:{get_remote_address(request)}"

limiter = Limiter(key_func=user_or_ip_key)