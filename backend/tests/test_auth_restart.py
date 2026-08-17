from datetime import timedelta

import jwt
import pytest

from app.auth.jwt import create_jwt, decode_jwt
from app.core.config import DEVELOPMENT_JWT_SECRET, Settings, get_settings


@pytest.fixture(autouse=True)
def clear_cached_settings() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_access_token_survives_settings_reload_with_same_persistent_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "persistent-restart-test-secret-at-least-32-characters"
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    token, _jti = create_jwt("restart-user", "access", timedelta(minutes=5))

    # Clearing the settings singleton models a fresh application process reading
    # the same persistent environment configuration.
    get_settings.cache_clear()

    assert decode_jwt(token, "access")["sub"] == "restart-user"


def test_access_token_is_rejected_after_an_actual_key_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "first-persistent-secret-at-least-32-characters")
    token, _jti = create_jwt("restart-user", "access", timedelta(minutes=5))
    monkeypatch.setenv("JWT_SECRET_KEY", "second-persistent-secret-at-least-32-characters")
    get_settings.cache_clear()

    with pytest.raises(jwt.InvalidSignatureError):
        decode_jwt(token, "access")


@pytest.mark.parametrize("secret", ["", "too-short", DEVELOPMENT_JWT_SECRET])
def test_production_rejects_missing_insecure_or_short_jwt_secret(secret: str) -> None:
    settings = Settings(
        _env_file=None,
        app_environment="production",
        jwt_secret_key=secret,
        auth_cookie_secure=True,
    )

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        settings.validate_security()


def test_development_uses_a_stable_explicit_default_secret() -> None:
    first = Settings(_env_file=None)
    second = Settings(_env_file=None)

    assert first.jwt_secret_key == second.jwt_secret_key == DEVELOPMENT_JWT_SECRET
