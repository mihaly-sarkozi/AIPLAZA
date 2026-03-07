# tests/test_auth_login.py
"""Login és refresh végpont automata tesztek: validáció, 401, sikeres login/refresh."""
from fastapi.testclient import TestClient

from main import app
from apps.core.security.auth_dependencies import get_current_user
from apps.auth.application.dto import LoginSuccess, LoginTwoFactorRequired
from apps.users.domain.user import User


# ---------- Paraméter / validáció tesztek (LoginReq → 422) ----------


def test_login_empty_body_returns_422(client: TestClient):
    """Üres body: sem 1., sem 2. lépés → Pydantic/validator 422."""
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 422


def test_login_only_email_returns_422(client: TestClient):
    """Csak email (nincs jelszó): nem teljes 1. lépés → 422."""
    r = client.post("/api/auth/login", json={"email": "a@b.com"})
    assert r.status_code == 422


def test_login_only_password_returns_422(client: TestClient):
    """Csak jelszó (nincs email): nem teljes 1. lépés → 422."""
    r = client.post("/api/auth/login", json={"password": "secret123"})
    assert r.status_code == 422


def test_login_step2_only_pending_token_returns_422(client: TestClient):
    """Csak pending_token (nincs two_factor_code): nem teljes 2. lépés → 422."""
    r = client.post("/api/auth/login", json={"pending_token": "abc123"})
    assert r.status_code == 422


def test_login_step2_only_two_factor_code_returns_422(client: TestClient):
    """Csak two_factor_code (nincs pending_token): nem teljes 2. lépés → 422."""
    r = client.post("/api/auth/login", json={"two_factor_code": "123456"})
    assert r.status_code == 422


def test_login_both_steps_same_body_returns_422(client: TestClient):
    """Email+jelszó ÉS pending_token+two_factor_code együtt → validator 422."""
    r = client.post(
        "/api/auth/login",
        json={
            "email": "a@b.com",
            "password": "secret",
            "pending_token": "pt",
            "two_factor_code": "123456",
        },
    )
    assert r.status_code == 422


def test_login_step1_empty_password_returns_422(client: TestClient):
    """1. lépés: üres jelszó (min_length=1) → 422."""
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": ""})
    assert r.status_code == 422


# ---------- Sikertelen belépés (service None → 401) ----------


def test_login_invalid_credentials_returns_401(client: TestClient):
    """Service None-t ad vissza (rossz email/jelszó vagy rossz 2FA) → 401."""
    r = client.post(
        "/api/auth/login",
        json={"email": "wrong@example.com", "password": "wrong"},
    )
    assert r.status_code == 401
    detail = r.json().get("detail")
    if isinstance(detail, str):
        assert "Invalid credentials" in detail or "Hibás" in detail
    else:
        assert detail is not None


def test_login_401_response_has_code_and_message(client: TestClient):
    """Hibás jelszó/email esetén a 401 detail tartalmazza a code és message mezőt (frontend számára)."""
    r = client.post(
        "/api/auth/login",
        json={"email": "u@example.com", "password": "wrong"},
    )
    assert r.status_code == 401
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "invalid_credentials"
    assert detail.get("message")
    assert "Hibás" in detail["message"] or "Invalid" in detail["message"]


def test_login_five_times_wrong_password_all_return_401(client: TestClient):
    """5x rossz jelszó: mindegyik hívás 401-et ad (service None); az 5. után a user zárolva (is_active=False), a 6. is 401."""
    for _ in range(6):
        r = client.post(
            "/api/auth/login",
            json={"email": "locked@example.com", "password": "wrong"},
        )
        assert r.status_code == 401
        detail = r.json().get("detail")
        assert detail is not None
        if isinstance(detail, dict):
            assert detail.get("code") == "invalid_credentials"


# ---------- Sikeres 1. lépés → TwoFactorRequiredResp (200) ----------


def test_login_step1_success_returns_two_factor_required(client: TestClient, mock_login_service):
    """Érvényes 1. lépés: service LoginTwoFactorRequired → 200, pending_token a válaszban."""
    mock_login_service.result = LoginTwoFactorRequired(pending_token="pending-xyz")
    r = client.post(
        "/api/auth/login",
        json={"email": "u@example.com", "password": "secret"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("pending_token") == "pending-xyz"


# ---------- Sikeres 2. lépés → TokenResp + cookie (200) ----------


def test_login_step2_success_returns_tokens_and_cookie(
    client: TestClient, mock_login_service, sample_user: User
):
    """Érvényes 2. lépés: service LoginSuccess → 200, access_token, user, refresh cookie."""
    mock_login_service.result = LoginSuccess(
        access_token="access-abc",
        refresh_token="refresh-xyz",
        user=sample_user,
    )
    r = client.post(
        "/api/auth/login",
        json={"pending_token": "pt", "two_factor_code": "123456"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("access_token") == "access-abc"
    assert data.get("refresh_token") == "refresh-xyz"
    assert "user" in data
    assert data["user"].get("email") == sample_user.email
    assert "refresh_token" in r.cookies
    assert r.cookies["refresh_token"] == "refresh-xyz"


# ---------- 409: már be vagy jelentkezve ----------
# A 409 akkor jön, ha request.state.user be van állítva (auth middleware).
# Ezt egy integration tesztben lehet ellenőrizni (valódi token + user), itt csak a route logikát mockoljuk.
# Opcionális: token nélkül nem tudjuk könnyen triggerelni a 409-et unit szinten.

def test_login_step1_valid_body_does_not_422(client: TestClient):
    """Érvényes 1. lépés body nem ad 422 (validáció rendben)."""
    # service visszaad None-t → 401, de a body validációt már átmentük
    r = client.post(
        "/api/auth/login",
        json={"email": "someone@example.com", "password": "any"},
    )
    assert r.status_code != 422
    assert r.status_code == 401  # mock default None


# ---------- Refresh token tesztek ----------


def test_refresh_no_cookie_returns_401(client: TestClient):
    """Nincs refresh_token cookie → 401."""
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401
    detail = r.json().get("detail")
    assert detail and "refresh" in str(detail).lower()


def test_refresh_invalid_or_revoked_returns_401(client_with_refresh, mock_refresh_service):
    """Érvénytelen vagy visszavont refresh token → 401."""
    mock_refresh_service.result = None
    client_with_refresh.cookies.set("refresh_token", "invalid-or-revoked-token")
    r = client_with_refresh.post("/api/auth/refresh")
    assert r.status_code == 401
    detail = r.json().get("detail")
    assert detail and ("Invalid" in str(detail) or "revoked" in str(detail).lower())


def test_refresh_success_returns_tokens_and_cookie(
    client_with_refresh, mock_refresh_service, sample_user: User
):
    """Érvényes refresh cookie → 200, új access_token, refresh_token (body + cookie), user."""
    mock_refresh_service.result = ("new-access-token", "new-refresh-token", "access-jti-123")
    mock_refresh_service.verify_payload = {"sub": "1", "typ": "refresh"}

    client_with_refresh.cookies.set("refresh_token", "valid-refresh-cookie")
    r = client_with_refresh.post("/api/auth/refresh")

    assert r.status_code == 200
    data = r.json()
    assert data.get("access_token") == "new-access-token"
    assert data.get("refresh_token") == "new-refresh-token"
    assert "user" in data
    assert data["user"].get("email") == sample_user.email
    assert data["user"].get("id") == 1
    assert "refresh_token" in r.cookies
    assert r.cookies["refresh_token"] == "new-refresh-token"


def test_refresh_with_x_refresh_token_header_success(
    client_with_refresh, mock_refresh_service, sample_user: User
):
    """X-Refresh-Token headerrel (cookie nélkül) is működik a refresh."""
    mock_refresh_service.result = ("access-from-header", "refresh-from-header", "access-jti-header")
    mock_refresh_service.verify_payload = {"sub": "1", "typ": "refresh"}
    r = client_with_refresh.post(
        "/api/auth/refresh",
        headers={"X-Refresh-Token": "valid-refresh-jwt"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("access_token") == "access-from-header"
    assert data.get("refresh_token") == "refresh-from-header"
    assert data["user"].get("email") == sample_user.email


def test_refresh_no_cookie_no_header_returns_401(client_with_refresh):
    """Nincs cookie és nincs X-Refresh-Token header → 401."""
    r = client_with_refresh.post("/api/auth/refresh")
    assert r.status_code == 401
    detail = r.json().get("detail")
    assert detail and "refresh" in str(detail).lower()


# ---------- ME (current user) tesztek ----------


def test_me_without_auth_returns_401(client: TestClient):
    """Nincs Authorization Bearer → 401."""
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    detail = r.json().get("detail")
    assert detail and ("token" in str(detail).lower() or "invalid" in str(detail).lower())


def test_me_success_returns_user_data(client_authenticated: TestClient, sample_user: User):
    """Bejelentkezett user (get_current_user override) → 200, id, email, role."""
    r = client_authenticated.get("/api/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data.get("id") == sample_user.id
    assert data.get("email") == sample_user.email
    assert data.get("role") == sample_user.role


# ---------- Logout tesztek ----------


def test_logout_without_auth_returns_200_ok(client: TestClient):
    """Nincs Bearer token: get_current_user_optional None → mindig 200, { ok: true } (cookie törlés)."""
    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_logout_success_returns_ok(client_authenticated: TestClient, mock_logout_service):
    """Bejelentkezett user + refresh token (cookie/header) → 200, { "ok": true }."""
    r = client_authenticated.post(
        "/api/auth/logout",
        headers={"X-Refresh-Token": "refresh-to-invalidate"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True


# ---------- Forgot password ----------


def test_forgot_password_returns_200(client: TestClient, mock_user_service):
    """POST /auth/forgot-password bármilyen emaillel → 200, { ok: true } (ne lehessen kideríteni, hogy létezik-e)."""
    from main import app
    from apps.core.di import get_user_service
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    try:
        r = client.post("/api/auth/forgot-password", json={"email": "any@example.com"})
        assert r.status_code == 200
        assert r.json().get("ok") is True
    finally:
        app.dependency_overrides.pop(get_user_service, None)


def test_forgot_password_empty_email_returns_422(client: TestClient):
    """POST /auth/forgot-password üres email → 422."""
    r = client.post("/api/auth/forgot-password", json={"email": ""})
    assert r.status_code == 422


# ---------- Change password (POST /auth/me/change-password) ----------


def test_change_password_without_auth_returns_401(client: TestClient):
    """Nincs Bearer → 401."""
    r = client.post(
        "/api/auth/me/change-password",
        json={"current_password": "old", "new_password": "NewPass1"},
    )
    assert r.status_code == 401


def test_change_password_wrong_current_returns_400(client_authenticated: TestClient, sample_user: User):
    """Hibás jelenlegi jelszó → 400 (érvényes hash, de rossz jelszó)."""
    from dataclasses import replace
    from passlib.hash import bcrypt_sha256 as pwd_hasher
    # Érvényes hash kell, különben passlib InvalidHashError-t dob; verify("wrong", hash) → False → 400
    user_with_hash = replace(sample_user, password_hash=pwd_hasher.hash("correct"))
    app.dependency_overrides[get_current_user] = lambda: user_with_hash
    try:
        r = client_authenticated.post(
            "/api/auth/me/change-password",
            json={"current_password": "wrong", "new_password": "NewPass1"},
        )
        assert r.status_code == 400
        detail = r.json().get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("code") == "current_password_wrong" or "jelszó" in str(detail).lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_change_password_success_returns_200(client_authenticated: TestClient, sample_user: User):
    """Helyes jelenlegi + erős új jelszó → 200, { ok: true }."""
    from dataclasses import replace
    from passlib.hash import bcrypt_sha256 as pwd_hasher
    from main import app
    user_with_pass = replace(sample_user, password_hash=pwd_hasher.hash("oldpass"))
    app.dependency_overrides[get_current_user] = lambda: user_with_pass
    try:
        r = client_authenticated.post(
            "/api/auth/me/change-password",
            json={"current_password": "oldpass", "new_password": "NewPass1"},
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------- PATCH /auth/me ----------


def test_patch_me_without_auth_returns_401(client: TestClient):
    """Nincs Bearer → 401."""
    r = client.patch("/api/auth/me", json={"name": "Foo"})
    assert r.status_code == 401


def test_patch_me_success_returns_updated(client_authenticated: TestClient, sample_user: User, mock_user_repo):
    """PATCH name / preferred_locale / preferred_theme → 200, frissített me."""
    updated = User(
        id=sample_user.id,
        email=sample_user.email,
        password_hash=sample_user.password_hash,
        is_active=sample_user.is_active,
        role=sample_user.role,
        created_at=sample_user.created_at,
        name="Updated Name",
        preferred_locale="en",
        preferred_theme="dark",
    )
    mock_user_repo.update.side_effect = lambda u: updated
    r = client_authenticated.patch(
        "/api/auth/me",
        json={"name": "Updated Name", "preferred_locale": "en", "preferred_theme": "dark"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("name") == "Updated Name"
    assert data.get("preferred_locale") == "en"
    assert data.get("preferred_theme") == "dark"
    assert data.get("locale") == "en"
    assert data.get("theme") == "dark"


# ---------- GET /auth/default-settings ----------


def test_default_settings_returns_locale_theme(client: TestClient, mock_user_repo):
    """GET /auth/default-settings auth nélkül → 200, locale + theme (owner alapértelmezés)."""
    r = client.get("/api/auth/default-settings")
    assert r.status_code == 200
    data = r.json()
    assert "locale" in data
    assert "theme" in data
    assert data["locale"] in ("hu", "en", "es")
    assert data["theme"] in ("light", "dark")
