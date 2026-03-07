# tests/test_token_service.py
"""TokenService tesztek: JWT iss / aud / nbf ellenőrzés verify() és decode_ignore_exp() esetén."""
import datetime
from datetime import timezone

import jwt
import pytest

from apps.core.security.token_service import TokenService


@pytest.fixture
def token_service_with_issuer():
    """TokenService issuerrel (éles szerint)."""
    return TokenService(
        secret="test-secret-key",
        issuer="AIPLAZA",
        access_exp_min=15,
        refresh_exp_min=60,
    )


@pytest.fixture
def token_service_with_issuer_and_audience():
    """TokenService issuer + audience-dal."""
    return TokenService(
        secret="test-secret-key",
        issuer="AIPLAZA",
        audience="api.aiplaza.local",
        access_exp_min=15,
        refresh_exp_min=60,
    )


def test_verify_accepts_token_with_correct_issuer(token_service_with_issuer):
    """Saját issuerrel kiadott token verify() → sikeres, payload vissza."""
    token, _ = token_service_with_issuer.make_access(1)
    payload = token_service_with_issuer.verify(token)
    assert payload["sub"] == "1"
    assert payload["typ"] == "access"
    assert payload["iss"] == "AIPLAZA"


def test_verify_rejects_token_with_wrong_issuer(token_service_with_issuer):
    """Más issuerű token verify() → InvalidIssuerError."""
    now = datetime.datetime.now(timezone.utc)
    wrong_issuer_token = jwt.encode(
        {
            "sub": "1",
            "typ": "access",
            "jti": "abc",
            "iss": "OTHER_ISSUER",
            "exp": now + datetime.timedelta(minutes=15),
            "iat": now,
            "nbf": now,
        },
        token_service_with_issuer.secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidIssuerError):
        token_service_with_issuer.verify(wrong_issuer_token)


def test_verify_rejects_token_with_wrong_audience(token_service_with_issuer_and_audience):
    """Audience beállítva: rossz aud → InvalidAudienceError."""
    now = datetime.datetime.now(timezone.utc)
    wrong_aud_token = jwt.encode(
        {
            "sub": "1",
            "typ": "access",
            "jti": "abc",
            "iss": "AIPLAZA",
            "aud": "other.api",
            "exp": now + datetime.timedelta(minutes=15),
            "iat": now,
            "nbf": now,
        },
        token_service_with_issuer_and_audience.secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidAudienceError):
        token_service_with_issuer_and_audience.verify(wrong_aud_token)


def test_verify_accepts_token_with_correct_audience(token_service_with_issuer_and_audience):
    """Helyes iss + aud → verify() sikeres."""
    token, _ = token_service_with_issuer_and_audience.make_access(1)
    payload = token_service_with_issuer_and_audience.verify(token)
    assert payload["iss"] == "AIPLAZA"
    assert payload["aud"] == "api.aiplaza.local"


def test_decode_ignore_exp_rejects_wrong_issuer_returns_none(token_service_with_issuer):
    """decode_ignore_exp: rossz iss → None (logoutnál ne fogadjunk el más környezet tokenjét)."""
    now = datetime.datetime.now(timezone.utc)
    # Lejárt, de más issuer
    wrong_issuer_token = jwt.encode(
        {
            "sub": "1",
            "typ": "refresh",
            "jti": "xyz",
            "iss": "OTHER",
            "exp": now - datetime.timedelta(hours=1),
            "iat": now - datetime.timedelta(hours=2),
            "nbf": now - datetime.timedelta(hours=2),
        },
        token_service_with_issuer.secret,
        algorithm="HS256",
    )
    result = token_service_with_issuer.decode_ignore_exp(wrong_issuer_token)
    assert result is None


def test_decode_ignore_exp_accepts_expired_token_with_correct_issuer(token_service_with_issuer):
    """decode_ignore_exp: lejárt, de helyes iss → payload (logoutnál sub kiolvasható)."""
    now = datetime.datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": "42",
            "typ": "refresh",
            "jti": "j",
            "iss": "AIPLAZA",
            "exp": now - datetime.timedelta(minutes=10),
            "iat": now - datetime.timedelta(hours=1),
            "nbf": now - datetime.timedelta(hours=1),
        },
        token_service_with_issuer.secret,
        algorithm="HS256",
    )
    result = token_service_with_issuer.decode_ignore_exp(expired_token)
    assert result is not None
    assert result["sub"] == "42"
    assert result["iss"] == "AIPLAZA"


def test_verify_rejects_token_with_nbf_in_future(token_service_with_issuer):
    """nbf a jövőben → verify() InvalidTokenError (vagy InvalidNotBeforeError)."""
    now = datetime.datetime.now(timezone.utc)
    future_nbf_token = jwt.encode(
        {
            "sub": "1",
            "typ": "access",
            "jti": "x",
            "iss": "AIPLAZA",
            "exp": now + datetime.timedelta(minutes=15),
            "iat": now,
            "nbf": now + datetime.timedelta(minutes=5),  # 5 perc múlva érvényes
        },
        token_service_with_issuer.secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        token_service_with_issuer.verify(future_nbf_token)
