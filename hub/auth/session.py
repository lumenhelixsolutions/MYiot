"""Session/auth primitives: password hashing, JWT, dependency, cookie helpers."""

import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, Response
from jose import JWTError, jwt
from passlib.context import CryptContext

from auth.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
COOKIE_NAME = "myiot_session"


@dataclass
class AuthenticatedUser:
    username: str
    role: str


def hash_password(plain: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(username: str, role: str = "admin") -> str:
    """Create a JWT access token."""
    expire = time.time() + settings.access_token_expire_minutes * 60
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the HTTP-only auth cookie."""
    secure = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the auth cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


async def require_auth(request: Request) -> AuthenticatedUser:
    """FastAPI dependency that enforces a valid session cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    username = payload.get("sub")
    role = payload.get("role", "admin")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return AuthenticatedUser(username=username, role=role)


async def require_auth_ws(token: str) -> AuthenticatedUser:
    """Validate a token passed via WebSocket query param."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    username = payload.get("sub")
    role = payload.get("role", "admin")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return AuthenticatedUser(username=username, role=role)
