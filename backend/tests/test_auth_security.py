from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth.csrf import validate_csrf
from app.auth.jwt import create_jwt, decode_jwt
from app.auth.passwords import hash_password, validate_password_policy, verify_password
from app.auth.tokens import generate_token, hash_token


def test_password_hashing_uses_argon2_and_verifies() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed.startswith("$argon2")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password value", hashed)


def test_password_policy_rejects_short_password() -> None:
    with pytest.raises(ValueError):
        validate_password_policy("too-short")


def test_jwt_rejects_wrong_type_claim() -> None:
    token, _ = create_jwt("user-id", "access", timedelta(minutes=5))

    with pytest.raises(jwt.InvalidTokenError):
        decode_jwt(token, "refresh")


def test_refresh_token_hash_is_not_plaintext() -> None:
    token = generate_token()
    token_hash = hash_token(token)

    assert token_hash != token
    assert len(token_hash) == 64
    assert hash_token(token) == token_hash


def test_csrf_rejects_missing_header_for_mutating_request() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/polygons",
            "headers": [],
        }
    )

    with pytest.raises(HTTPException) as exc:
        validate_csrf(request)

    assert exc.value.status_code == 403
