import hmac
from dataclasses import dataclass
from typing import Literal, cast

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.models.entities import AuthUser
from app.services.auth import decode_and_verify_token

UserRole = Literal["admin", "hr_admin", "manager", "analyst", "employee"]

RBAC_PERMISSION_MATRIX: dict[UserRole, frozenset[str]] = {
    "admin": frozenset(
        {
            "settings.read",
            "settings.write",
            "ingest.read",
            "ingest.write",
            "employees.read",
            "employees.write",
            "employees.consent.read",
            "employees.consent.write",
            "insights.read",
            "manager.read",
            "nudges.read",
            "nudges.write",
            "simulations.run",
            "compliance.read",
            "assistant.query",
        }
    ),
    "hr_admin": frozenset(
        {
            "settings.read",
            "settings.write",
            "ingest.read",
            "ingest.write",
            "employees.read",
            "employees.write",
            "employees.consent.read",
            "employees.consent.write",
            "insights.read",
            "manager.read",
            "nudges.read",
            "nudges.write",
            "simulations.run",
            "compliance.read",
            "assistant.query",
        }
    ),
    "manager": frozenset(
        {
            "settings.read",
            "employees.read",
            "employees.consent.read",
            "insights.read",
            "manager.read",
            "nudges.read",
            "nudges.write",
            "simulations.run",
            "assistant.query",
        }
    ),
    "analyst": frozenset(
        {
            "settings.read",
            "ingest.read",
            "employees.read",
            "insights.read",
            "manager.read",
            "nudges.read",
            "simulations.run",
            "assistant.query",
        }
    ),
    "employee": frozenset(
        {
            "settings.read",
            "assistant.query",
        }
    ),
}


@dataclass(frozen=True)
class AccessContext:
    role: UserRole
    permissions: frozenset[str]
    auth_type: Literal["token", "api_key", "dev_fallback"]
    user_id: int | None = None
    user_email: str | None = None
    is_authenticated: bool = False

    def has_permissions(self, *required_permissions: str) -> bool:
        return set(required_permissions).issubset(self.permissions)


def _normalize_role_or_403(role_value: str) -> UserRole:
    normalized = role_value.strip().lower()
    if normalized not in RBAC_PERMISSION_MATRIX:
        allowed = ", ".join(sorted(RBAC_PERMISSION_MATRIX))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unsupported role '{normalized}'. Allowed roles: {allowed}",
        )
    return cast(UserRole, normalized)


def _parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _build_context_from_role(
    role: UserRole,
    auth_type: Literal["token", "api_key", "dev_fallback"],
    *,
    user_id: int | None = None,
    user_email: str | None = None,
    is_authenticated: bool = False,
) -> AccessContext:
    return AccessContext(
        role=role,
        permissions=RBAC_PERMISSION_MATRIX[role],
        auth_type=auth_type,
        user_id=user_id,
        user_email=user_email,
        is_authenticated=is_authenticated,
    )


def _validate_api_key_or_401(x_api_key: str | None, settings: Settings) -> None:
    if not settings.require_api_key:
        return
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    _validate_api_key_or_401(x_api_key, settings)


def get_access_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AccessContext:
    bearer_token = _parse_bearer_token(authorization)
    if bearer_token:
        try:
            payload = decode_and_verify_token(
                bearer_token,
                settings,
                expected_type="access",
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

        try:
            user_id = int(str(payload["sub"]))
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject",
            ) from exc

        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is inactive or not found",
            )
        role = _normalize_role_or_403(user.role)
        return _build_context_from_role(
            role,
            "token",
            user_id=user.id,
            user_email=user.email,
            is_authenticated=True,
        )

    if settings.require_api_key or x_api_key:
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
            )
        if not hmac.compare_digest(x_api_key, settings.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        role = _normalize_role_or_403(settings.api_key_role)
        return _build_context_from_role(
            role,
            "api_key",
            is_authenticated=True,
        )

    if settings.require_authentication:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    fallback_role = _normalize_role_or_403(x_user_role or settings.default_user_role)
    return _build_context_from_role(
        fallback_role,
        "dev_fallback",
        is_authenticated=False,
    )


def require_authenticated_access(access: AccessContext = Depends(get_access_context)) -> AccessContext:
    return access


def require_roles(*required_roles: UserRole):
    required = {
        _normalize_role_or_403(role)
        for role in required_roles
    }

    def role_dependency(access: AccessContext = Depends(get_access_context)) -> AccessContext:
        if access.role in required:
            return access
        allowed = ", ".join(sorted(required))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{access.role}' is not allowed. Required role(s): {allowed}",
        )

    return role_dependency


def require_permissions(*required_permissions: str):
    required = tuple(sorted({permission.strip() for permission in required_permissions if permission.strip()}))

    def permission_dependency(access: AccessContext = Depends(get_access_context)) -> AccessContext:
        if access.has_permissions(*required):
            return access
        missing = [permission for permission in required if permission not in access.permissions]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{access.role}' is not allowed to perform this action. "
                f"Missing permissions: {', '.join(missing)}"
            ),
        )

    return permission_dependency
