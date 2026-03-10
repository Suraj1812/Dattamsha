from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.core.middleware import get_request_id
from app.models.entities import AuditEvent, Employee, EmployeeConsent
from app.schemas.hr import EmployeeConsentUpsert


def _serialize_details(details: dict[str, object] | str | None) -> str | None:
    if details is None:
        return None
    if isinstance(details, str):
        return details
    return json.dumps(details, ensure_ascii=True, separators=(",", ":"))


def log_audit_event(
    db: Session,
    *,
    action: str,
    resource: str,
    outcome: str = "success",
    actor: str = "system",
    details: dict[str, object] | str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        resource=resource,
        outcome=outcome,
        actor=actor,
        request_id=get_request_id() or None,
        details=_serialize_details(details),
    )
    db.add(event)
    return event


def upsert_employee_consent(
    db: Session,
    *,
    employee_id: int,
    payload: EmployeeConsentUpsert,
) -> EmployeeConsent | None:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    consent = EmployeeConsent(
        employee_id=employee_id,
        consent_type=payload.consent_type,
        status=payload.status,
        source=payload.source,
        captured_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=payload.expires_at,
        details=payload.details,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def list_employee_consents(
    db: Session,
    *,
    employee_id: int,
    consent_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[EmployeeConsent]:
    query = db.query(EmployeeConsent).filter(EmployeeConsent.employee_id == employee_id)
    if consent_type:
        query = query.filter(EmployeeConsent.consent_type == consent_type)
    if status:
        query = query.filter(EmployeeConsent.status == status)
    return (
        query.order_by(EmployeeConsent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def is_consent_granted(
    db: Session,
    *,
    employee_id: int,
    consent_type: str,
) -> bool:
    consent = (
        db.query(EmployeeConsent)
        .filter(
            EmployeeConsent.employee_id == employee_id,
            EmployeeConsent.consent_type == consent_type,
        )
        .order_by(EmployeeConsent.created_at.desc())
        .first()
    )
    if not consent:
        return False
    if consent.status != "granted":
        return False
    if consent.expires_at is None:
        return True
    return consent.expires_at >= datetime.now(timezone.utc).replace(tzinfo=None)


def list_audit_events(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    outcome: str | None = None,
    search: str | None = None,
) -> list[AuditEvent]:
    query = db.query(AuditEvent)
    if action:
        query = query.filter(AuditEvent.action == action)
    if outcome:
        query = query.filter(AuditEvent.outcome == outcome)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (AuditEvent.resource.ilike(pattern))
            | (AuditEvent.actor.ilike(pattern))
            | (AuditEvent.details.ilike(pattern))
            | (cast(AuditEvent.id, String).ilike(pattern))
            | (AuditEvent.request_id.ilike(pattern))
        )
    return (
        query.order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
