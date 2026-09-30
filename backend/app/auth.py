"""Verify Supabase sign-in tokens on the server.

The browser signs in with Supabase and sends its access token (a JWT) with
each request. We check the signature against the project's public keys (JWKS),
plus the audience, issuer and expiry, so a token can't be forged or reused
after it expires. Supabase only issues tokens to users who confirmed their email
("Confirm email" is on), and we double-check the verification claim when present.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException

from .config import get_settings


@dataclass(frozen=True)
class User:
    id: str
    email: str | None

    @property
    def is_admin(self) -> bool:
        return bool(self.email) and self.email.lower() in get_settings().admin_emails


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def verify_token(token: str) -> User:
    s = get_settings()
    if not s.supabase_url:
        raise HTTPException(503, "Accounts aren't configured on this server.")
    issuer = f"{s.supabase_url}/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            if not s.supabase_jwt_secret:
                raise HTTPException(401, "Sign-in token uses a legacy key this server can't check.")
            key, algorithms = s.supabase_jwt_secret, ["HS256"]
        else:
            key, algorithms = _jwks_client(s.supabase_url).get_signing_key_from_jwt(token).key, ["ES256", "RS256"]
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub"]},
        )
    except HTTPException:
        raise
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid or expired sign-in ({type(exc).__name__}).") from exc
    except Exception as exc:  # noqa: BLE001 - JWKS fetch problems etc.
        raise HTTPException(503, "Couldn't verify sign-in right now. Try again.") from exc

    if claims.get("role") != "authenticated":
        raise HTTPException(401, "Not a signed-in user.")
    if (claims.get("user_metadata") or {}).get("email_verified") is False:
        raise HTTPException(403, "Please verify your email first.")
    return User(id=str(claims["sub"]), email=claims.get("email"))


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


async def optional_user(authorization: str | None = Header(default=None)) -> User | None:
    token = _bearer(authorization)
    return verify_token(token) if token else None


async def require_user(authorization: str | None = Header(default=None)) -> User:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    return verify_token(token)
