from core.kernel.config.config_loader import settings
from shared.validation.password import validate_password_policy


def test_basic_password_policy_accepts_simple_password():
    ok, message = validate_password_policy("simple1", security_level="basic")

    assert ok is True
    assert message == ""


def test_standard_password_policy_requires_uppercase():
    ok, message = validate_password_policy("password1", security_level="standard")

    assert ok is False
    assert "nagybet" in message.lower()


def test_high_password_policy_requires_special_character():
    ok, message = validate_password_policy("Password12", security_level="high")

    assert ok is False
    assert "speci" in message.lower()


def test_default_policy_comes_from_settings(monkeypatch):
    original_level = settings.password_security_level
    monkeypatch.setattr(settings, "password_security_level", "high")
    try:
        ok, message = validate_password_policy("Password12")
    finally:
        monkeypatch.setattr(settings, "password_security_level", original_level)

    assert ok is False
    assert "speci" in message.lower()
