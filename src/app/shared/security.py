import time
from dataclasses import dataclass
from enum import Enum

import bcrypt
import jwt

from app.config import Settings

BCRYPT_COST = 10


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=BCRYPT_COST)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    expires_at: int


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.goapp_secret_key
        self._issuer = settings.goapp_name.lower()
        # Parity with Go: refresh tokens are issued with GOAPP_JWT_ACCESS_EXPIRES too.
        self._lifetimes = {
            TokenType.ACCESS: settings.goapp_jwt_access_expires,
            TokenType.REFRESH: settings.goapp_jwt_access_expires,
        }

    def sign(self, token_type: TokenType, user_id: int, expires_at: int | None = None) -> str:
        now = int(time.time())
        payload = {
            "claims": {"id": user_id},
            "iss": self._issuer,
            "sub": f"{token_type.value}-token",
            "aud": ["user", "admin"],
            "exp": expires_at if expires_at is not None else now + self._lifetimes[token_type],
            "nbf": now,
            "iat": now,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def parse(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=["HS256"], options={"verify_aud": False}
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("token had expired") from exc
        except jwt.InvalidSignatureError as exc:
            raise TokenError(f"parse token failed: {exc}") from exc
        except jwt.DecodeError as exc:
            raise TokenError("token format is invalid") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenError(f"parse token failed: {exc}") from exc

        claims = payload.get("claims")
        if not isinstance(claims, dict) or not isinstance(claims.get("id"), int):
            raise TokenError("claims type is invalid")
        return TokenClaims(user_id=claims["id"], expires_at=int(payload["exp"]))
