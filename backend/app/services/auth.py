from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import AuthRefreshToken, AuthUser


def _utcnow() -> datetime:
    return datetime.utcnow()


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _json_compact(data: dict[str, object]) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def hash_password(plain_password: str) -> str:
    password = plain_password.strip()
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=64)
    return f"scrypt${n}${r}${p}${_b64url_encode(salt)}${_b64url_encode(key)}"


def verify_password(plain_password: str, encoded_hash: str) -> bool:
    try:
        algorithm, n_raw, r_raw, p_raw, salt_raw, key_raw = encoded_hash.split("$")
        if algorithm != "scrypt":
            return False
        n, r, p = int(n_raw), int(r_raw), int(p_raw)
        salt = _b64url_decode(salt_raw)
        expected_key = _b64url_decode(key_raw)
    except (ValueError, TypeError):
        return False

    derived_key = hashlib.scrypt(
        plain_password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=len(expected_key),
    )
    return hmac.compare_digest(derived_key, expected_key)


def _sign_token(payload: dict[str, object], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(_json_compact(header))
    payload_b64 = _b64url_encode(_json_compact(payload))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_and_verify_token(
    token: str,
    settings: Settings,
    expected_type: str | None = None,
) -> dict[str, object]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_signature = hmac.new(
        settings.auth_jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    provided_signature = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid token signature")

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Invalid token payload") from exc

    if header.get("alg") != "HS256":
        raise ValueError("Unsupported token algorithm")
    if not isinstance(payload, dict):
        raise ValueError("Invalid token payload")

    if payload.get("iss") != settings.auth_jwt_issuer:
        raise ValueError("Invalid token issuer")
    if payload.get("aud") != settings.auth_jwt_audience:
        raise ValueError("Invalid token audience")

    now = int(time.time())
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= now:
        raise ValueError("Token has expired")

    token_type = payload.get("type")
    if expected_type and token_type != expected_type:
        raise ValueError("Invalid token type")

    if "sub" not in payload or "jti" not in payload:
        raise ValueError("Token is missing required claims")

    return payload


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def _build_token_payload(
    user: AuthUser,
    token_type: str,
    expires_delta: timedelta,
    settings: Settings,
    token_jti: str,
) -> dict[str, object]:
    now = int(time.time())
    exp = int((datetime.fromtimestamp(now, tz=timezone.utc) + expires_delta).timestamp())
    return {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "type": token_type,
        "iss": settings.auth_jwt_issuer,
        "aud": settings.auth_jwt_audience,
        "iat": now,
        "exp": exp,
        "jti": token_jti,
    }


def issue_token_pair(db: Session, user: AuthUser, settings: Settings) -> TokenPair:
    access_jti = secrets.token_urlsafe(20)
    refresh_jti = secrets.token_urlsafe(28)
    access_delta = timedelta(minutes=settings.auth_access_token_minutes)
    refresh_delta = timedelta(days=settings.auth_refresh_token_days)

    access_payload = _build_token_payload(user, "access", access_delta, settings, access_jti)
    refresh_payload = _build_token_payload(user, "refresh", refresh_delta, settings, refresh_jti)

    access_token = _sign_token(access_payload, settings.auth_jwt_secret)
    refresh_token = _sign_token(refresh_payload, settings.auth_jwt_secret)

    db.add(
        AuthRefreshToken(
            user_id=user.id,
            token_jti=refresh_jti,
            expires_at=_utcnow() + refresh_delta,
        )
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_delta.total_seconds()),
    )


def authenticate_user(db: Session, email: str, password: str) -> AuthUser | None:
    normalized_email = normalize_email(email)
    user = db.query(AuthUser).filter(AuthUser.email == normalized_email).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def list_auth_users(db: Session) -> list[AuthUser]:
    return db.query(AuthUser).order_by(AuthUser.created_at.desc()).all()


def get_auth_user_by_id(db: Session, user_id: int) -> AuthUser | None:
    return db.query(AuthUser).filter(AuthUser.id == user_id).first()


def create_auth_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    role: str,
    password: str,
    is_active: bool = True,
) -> AuthUser:
    normalized_email = normalize_email(email)
    existing = db.query(AuthUser).filter(AuthUser.email == normalized_email).first()
    if existing:
        raise ValueError("Email is already in use.")

    user = AuthUser(
        email=normalized_email,
        full_name=full_name.strip(),
        role=role,
        password_hash=hash_password(password),
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def update_auth_user_role(db: Session, user_id: int, role: str) -> AuthUser | None:
    user = get_auth_user_by_id(db, user_id)
    if not user:
        return None
    user.role = role
    db.flush()
    return user


def update_auth_user_password(
    db: Session,
    user_id: int,
    *,
    current_password: str,
    new_password: str,
) -> AuthUser | None:
    user = get_auth_user_by_id(db, user_id)
    if not user:
        return None
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect.")
    user.password_hash = hash_password(new_password)
    db.flush()
    return user


def admin_reset_auth_user_password(
    db: Session,
    user_id: int,
    *,
    new_password: str,
) -> AuthUser | None:
    user = get_auth_user_by_id(db, user_id)
    if not user:
        return None
    user.password_hash = hash_password(new_password)
    db.flush()
    return user


def rotate_refresh_token(db: Session, refresh_token: str, settings: Settings) -> tuple[AuthUser, TokenPair]:
    payload = decode_and_verify_token(refresh_token, settings, expected_type="refresh")
    token_jti = str(payload["jti"])
    user_id = int(payload["sub"])
    token_row = (
        db.query(AuthRefreshToken)
        .filter(AuthRefreshToken.token_jti == token_jti)
        .first()
    )
    if not token_row:
        raise ValueError("Refresh token not recognized.")
    if token_row.revoked_at is not None:
        raise ValueError("Refresh token is already revoked.")
    if token_row.expires_at < _utcnow():
        raise ValueError("Refresh token has expired.")

    user = get_auth_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise ValueError("User account is not active.")

    token_row.revoked_at = _utcnow()
    new_pair = issue_token_pair(db, user, settings)
    new_payload = decode_and_verify_token(new_pair.refresh_token, settings, expected_type="refresh")
    token_row.replaced_by_token_jti = str(new_payload["jti"])
    return user, new_pair


def revoke_refresh_token(db: Session, refresh_token: str, settings: Settings) -> bool:
    payload = decode_and_verify_token(refresh_token, settings, expected_type="refresh")
    token_jti = str(payload["jti"])
    token_row = (
        db.query(AuthRefreshToken)
        .filter(AuthRefreshToken.token_jti == token_jti)
        .first()
    )
    if not token_row:
        return False
    if token_row.revoked_at is None:
        token_row.revoked_at = _utcnow()
    return True


def mark_login_success(db: Session, user: AuthUser) -> None:
    user.last_login_at = _utcnow()
    db.flush()


def ensure_bootstrap_admin(db: Session, settings: Settings) -> AuthUser | None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return None

    normalized_email = normalize_email(settings.bootstrap_admin_email)
    existing = db.query(AuthUser).filter(AuthUser.email == normalized_email).first()
    if existing:
        return existing

    user = create_auth_user(
        db,
        email=normalized_email,
        full_name=settings.bootstrap_admin_full_name,
        role="admin",
        password=settings.bootstrap_admin_password,
        is_active=True,
    )
    return user
