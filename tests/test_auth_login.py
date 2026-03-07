# tests/test_auth_login.py
"""Login és refresh végpont automata tesztek: validáció, 401, sikeres login/refresh."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from apps.core.di import get_login_service
from apps.core.security.auth_dependencies import get_current_user
from apps.core.container.app_container import container
from apps.auth.application.dto import LoginSuccess, LoginTwoFactorRequired
from apps.auth.application.services.two_factor_service import TwoFactorService
from apps.auth.application.services.login_service import LoginService
from apps.users.domain.user import User
from config.settings import settings
from apps.auth.domain.tenant import Tenant


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
    """Érvényes 2. lépés: service LoginSuccess → 200, access_token, user; refresh csak cookie-ban (policy)."""
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
    assert "user" in data
    assert data["user"].get("email") == sample_user.email
    # Policy: refresh token NEM szerepel a response body-ban, csak HttpOnly cookie-ban.
    assert "refresh_token" not in data
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
    """Érvényes refresh cookie → 200, access_token + user; új refresh csak cookie-ban (policy)."""
    mock_refresh_service.result = ("new-access-token", "new-refresh-token", "access-jti-123", sample_user)
    mock_refresh_service.verify_payload = {"sub": "1", "typ": "refresh"}

    client_with_refresh.cookies.set("refresh_token", "valid-refresh-cookie")
    r = client_with_refresh.post("/api/auth/refresh")

    assert r.status_code == 200
    data = r.json()
    assert data.get("access_token") == "new-access-token"
    assert "user" in data
    assert data["user"].get("email") == sample_user.email
    assert data["user"].get("id") == 1
    # Policy: refresh token NEM szerepel a response body-ban, csak HttpOnly cookie-ban.
    assert "refresh_token" not in data
    assert "refresh_token" in r.cookies
    assert r.cookies["refresh_token"] == "new-refresh-token"


def test_refresh_only_header_no_cookie_returns_401(client_with_refresh):
    """Policy: refresh token csak cookie-ban; csak X-Refresh-Token header (nincs cookie) → 401."""
    r = client_with_refresh.post(
        "/api/auth/refresh",
        headers={"X-Refresh-Token": "valid-refresh-jwt"},
    )
    assert r.status_code == 401


def test_refresh_no_cookie_no_header_returns_401(client_with_refresh):
    """Nincs refresh_token cookie → 401 (header nem fogadható policy miatt)."""
    r = client_with_refresh.post("/api/auth/refresh")
    assert r.status_code == 401
    detail = r.json().get("detail")
    assert detail and "refresh" in str(detail).lower()


# ---------- Refresh: device/session binding (más fingerprint → re_2fa_required) ----------


def test_refresh_different_fingerprint_returns_re_2fa_required():
    """Ha a refresh más IP és más user-agenttal jön, mint a sessionben tárolt → (None, re_2fa_required) + audit."""
    from datetime import datetime, timezone, timedelta
    from unittest.mock import MagicMock
    from apps.auth.application.services.refresh_service import RefreshService
    from apps.auth.domain.session import Session

    session_repo = MagicMock()
    tokens = MagicMock()
    logger = MagicMock()
    audit = MagicMock()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    stored_session = Session(
        id=1,
        user_id=1,
        jti="jti-abc",
        token_hash="hash",
        valid=True,
        ip="1.2.3.4",
        user_agent="Mozilla/5.0 (Original)",
        expires_at=future,
        created_at=datetime.now(timezone.utc),
    )
    session_repo.get_by_jti.return_value = stored_session
    tokens.verify.return_value = {"sub": "1", "typ": "refresh", "jti": "jti-abc", "al": False}

    svc = RefreshService(session_repo, tokens, logger, audit)
    result = svc.refresh("refresh-token", ip="9.9.9.9", ua="OtherBrowser/99")

    assert result == (None, "re_2fa_required")
    audit.log.assert_called_once()
    call_args = audit.log.call_args
    assert call_args[0][0] == "refresh_suspicious_fingerprint"
    assert call_args[1].get("user_id") == 1
    assert call_args[1].get("details", {}).get("reason") == "fingerprint_mismatch"


def test_refresh_same_fingerprint_not_re_2fa():
    """Ugyanaz az IP és user_agent mint a sessionben → nincs re_2fa_required (normál refresh folytatódik)."""
    from datetime import datetime, timezone, timedelta
    from unittest.mock import MagicMock
    from apps.auth.application.services.refresh_service import RefreshService
    from apps.auth.domain.session import Session

    session_repo = MagicMock()
    tokens = MagicMock()
    logger = MagicMock()
    audit = MagicMock()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    stored_session = Session(
        id=1,
        user_id=1,
        jti="jti-xyz",
        token_hash="h",
        valid=True,
        ip="1.2.3.4",
        user_agent="Mozilla/5.0",
        expires_at=future,
        created_at=datetime.now(timezone.utc),
    )
    session_repo.get_by_jti.return_value = stored_session
    session_repo.update.return_value = None
    session_repo.create.return_value = None
    tokens.verify.return_value = {"sub": "1", "typ": "refresh", "jti": "jti-xyz", "al": False}
    tokens.make_refresh_pair.return_value = ("new-refresh", {"jti": "new-jti", "exp": future})
    tokens.hash_token.return_value = "new-hash"
    tokens.make_access.return_value = ("new-access", "access-jti")

    svc = RefreshService(session_repo, tokens, logger, audit)
    result = svc.refresh("refresh-token", ip="1.2.3.4", ua="Mozilla/5.0")

    assert result is not None
    assert result != (None, "re_2fa_required")
    assert len(result) == 4  # (access, new_refresh, access_jti, user)
    assert result[0] == "new-access" and result[1] == "new-refresh"
    assert result[3] is None  # nincs user_repository injektálva


def test_refresh_re_2fa_required_returns_401_with_code(client_with_refresh, mock_refresh_service):
    """Ha a refresh service (None, re_2fa_required)-et ad → 401, detail.code re_2fa_required."""
    mock_refresh_service.result = (None, "re_2fa_required")
    mock_refresh_service.verify_payload = {"sub": "1", "typ": "refresh"}
    client_with_refresh.cookies.set("refresh_token", "some-token")
    r = client_with_refresh.post("/api/auth/refresh")
    assert r.status_code == 401
    detail = r.json().get("detail", {})
    assert isinstance(detail, dict) and detail.get("code") == "re_2fa_required"


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


# ---------- 2FA brute-force védelem (429: túl sok sikertelen próbálkozás) ----------


def test_login_step2_too_many_attempts_returns_429(client: TestClient, mock_login_service):
    """Ha a login service TwoFactorTooManyAttemptsError-t dob step2-nál → 429, two_factor_too_many_attempts."""
    mock_login_service.raise_2fa_too_many = True
    r = client.post(
        "/api/auth/login",
        json={"pending_token": "any-token", "two_factor_code": "123456"},
    )
    assert r.status_code == 429
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("code") == "two_factor_too_many_attempts"
    assert "two_factor" in str(detail).lower() or "429" in str(r.status_code)


class InMemory2FAAttemptRepo:
    """In-memory 2FA attempt repo a brute-force teszthez (token / user / IP limit)."""
    def __init__(self, max_attempts=5, window_minutes=15):
        self._store = {}  # (scope, scope_key) -> (attempts, window_start)
        self._max_attempts = max_attempts
        self._window = timedelta(minutes=window_minutes)

    def _now(self):
        return datetime.now(timezone.utc)

    def is_blocked(self, scope: str, scope_key: str, max_attempts: int, window_minutes: int) -> bool:
        if not scope_key:
            return False
        key = (scope, scope_key)
        if key not in self._store:
            return False
        attempts, start = self._store[key]
        if self._now() - start > timedelta(minutes=window_minutes):
            return False
        return attempts >= max_attempts

    def record_failed(self, scope: str, scope_key: str, window_minutes: int) -> int:
        if not scope_key:
            return 0
        key = (scope, scope_key)
        now = self._now()
        if key in self._store:
            attempts, start = self._store[key]
            if now - start > timedelta(minutes=window_minutes):
                attempts = 0
                start = now
        else:
            attempts = 0
            start = now
        attempts += 1
        self._store[key] = (attempts, start)
        return attempts

    def reset_for_success(self, pending_token_key: str, user_id: int, ip: str | None) -> None:
        for scope, key in [
            ("token", pending_token_key),
            ("user", str(user_id)),
            ("ip", ip or ""),
        ]:
            if key:
                self._store.pop((scope, key), None)


def test_login_step2_five_wrong_codes_then_sixth_returns_429(
    mock_user_repo, sample_user,
):
    """5 rossz 2FA kód után a 6. step2 hívás 429 (too many attempts); új login step1 kell."""
    DEMO_TENANT = Tenant(id=1, slug="demo", name="Demo", created_at=datetime.now(timezone.utc))
    in_memory_attempt_repo = InMemory2FAAttemptRepo(max_attempts=5, window_minutes=15)
    mock_two_factor_repo = MagicMock()
    mock_two_factor_repo.get_valid_code.return_value = None  # mindig rossz kód
    mock_pending_2fa = MagicMock()
    mock_pending_2fa.get_user_id.return_value = 1
    mock_pending_2fa.consume.side_effect = None
    mock_session = MagicMock()
    mock_token_service = MagicMock()
    mock_logger = MagicMock()
    mock_audit = MagicMock()
    two_factor_service = TwoFactorService(
        mock_two_factor_repo,
        MagicMock(),
        attempt_repo=in_memory_attempt_repo,
        max_attempts=5,
        attempt_window_minutes=15,
    )
    login_service = LoginService(
        mock_user_repo,
        mock_session,
        mock_pending_2fa,
        mock_token_service,
        mock_logger,
        two_factor_service,
        mock_audit,
        settings_service=MagicMock(),
    )
    mock_user_repo.get_by_id.side_effect = lambda uid: sample_user if uid == 1 else None
    app.dependency_overrides[get_login_service] = lambda: login_service
    base_url = f"http://demo.{settings.tenant_base_domain}"
    try:
        with patch.object(container.tenant_repo, "get_by_slug", return_value=DEMO_TENANT):
            with TestClient(app, base_url=base_url) as c:
                pending = "pending-token-xyz"
                # 1–5. rossz kód → 401
                for i in range(5):
                    r = c.post(
                        "/api/auth/login",
                        json={"pending_token": pending, "two_factor_code": "000000"},
                    )
                    assert r.status_code == 401, f"Attempt {i+1} expected 401"
                # 6. → 429
                r = c.post(
                    "/api/auth/login",
                    json={"pending_token": pending, "two_factor_code": "000000"},
                )
                assert r.status_code == 429, r.json()
                detail = r.json().get("detail", {})
                if isinstance(detail, dict):
                    # 6. kérés: vagy a célzott rate limit (5/perc/pending_token) → auth_rate_limit, vagy a service → two_factor_too_many_attempts
                    assert detail.get("code") in ("two_factor_too_many_attempts", "auth_rate_limit")
    finally:
        app.dependency_overrides.pop(get_login_service, None)
