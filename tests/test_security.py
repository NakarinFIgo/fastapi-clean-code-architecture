import time

import jwt
import pytest

from app.shared.security import (
    TokenError,
    TokenService,
    TokenType,
    hash_password,
    verify_password,
)


def decode(token, settings):
    return jwt.decode(
        token, settings.goapp_secret_key, algorithms=["HS256"], options={"verify_aud": False}
    )


def test_password_roundtrip():
    hashed = hash_password("s3cret")
    assert hashed.startswith("$2")
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_verifies_hash_made_by_go_bcrypt():
    # Real "$2a$" cost-10 hash (the prefix Go's bcrypt emits) of "s3cret".
    go_hash = "$2a$10$kWxvjgYFmpRMMxky1P6IL./zmczCfmg93K57sPFVGGlmNmGcxnV6u"
    assert verify_password("s3cret", go_hash)
    assert not verify_password("wrong", go_hash)


def test_verify_password_with_garbage_hash_is_false():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_token_payload_matches_go_shape(settings):
    token = TokenService(settings).sign(TokenType.ACCESS, 7)
    payload = decode(token, settings)
    assert payload["claims"] == {"id": 7}
    assert payload["sub"] == "access-token"
    assert payload["aud"] == ["user", "admin"]
    assert payload["iss"] == "golang first api app"
    assert payload["exp"] - payload["iat"] == settings.goapp_jwt_access_expires
    assert payload["nbf"] == payload["iat"]


def test_refresh_token_matches_go_quirk_of_using_access_lifetime(settings):
    settings.goapp_jwt_access_expires = 111
    settings.goapp_jwt_refresh_expires = 999
    payload = decode(TokenService(settings).sign(TokenType.REFRESH, 7), settings)
    assert payload["sub"] == "refresh-token"
    assert payload["exp"] - payload["iat"] == 111


def test_parse_accepts_token_with_aud_claim(settings):
    # PyJWT rejects tokens with `aud` unless told not to verify it.
    svc = TokenService(settings)
    assert svc.parse(svc.sign(TokenType.ACCESS, 42)).user_id == 42


def test_sign_with_fixed_expiry_is_kept(settings):
    svc = TokenService(settings)
    exp = int(time.time()) + 1000
    assert svc.parse(svc.sign(TokenType.REFRESH, 1, expires_at=exp)).expires_at == exp


def test_parse_errors_use_go_messages(settings):
    svc = TokenService(settings)
    with pytest.raises(TokenError, match="token format is invalid"):
        svc.parse("")
    with pytest.raises(TokenError, match="token format is invalid"):
        svc.parse("abc")
    expired = jwt.encode(
        {"claims": {"id": 1}, "exp": int(time.time()) - 10}, settings.goapp_secret_key, "HS256"
    )
    with pytest.raises(TokenError, match="token had expired"):
        svc.parse(expired)
    forged = jwt.encode({"claims": {"id": 1}}, "other-secret-other-secret-other-secret", "HS256")
    with pytest.raises(TokenError, match="parse token failed"):
        svc.parse(forged)


def test_parse_rejects_token_without_claims(settings):
    token = jwt.encode({"exp": int(time.time()) + 100}, settings.goapp_secret_key, "HS256")
    with pytest.raises(TokenError, match="claims type is invalid"):
        TokenService(settings).parse(token)
