from __future__ import annotations

import json
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models.entities import Nudge, NudgeDispatchLog, NudgeFeedback
from app.schemas.hr import (
    NudgeDispatchItem,
    NudgeDispatchLogRead,
    NudgeDispatchRequest,
    NudgeDispatchResponse,
    NudgeFeedbackCreate,
)


def dispatch_nudges(db: Session, payload: NudgeDispatchRequest) -> NudgeDispatchResponse:
    query = db.query(Nudge)
    if not payload.include_resolved:
        query = query.filter(Nudge.status == "open")

    nudges = query.order_by(Nudge.created_at.desc()).limit(payload.max_items).all()
    items: list[NudgeDispatchItem] = []

    for nudge in nudges:
        status = "queued"
        response_code: int | None = None
        error_message: str | None = None

        if payload.channel == "webhook":
            if not payload.webhook_url:
                status = "failed"
                error_message = "webhook_url is required for webhook channel"
            else:
                message_payload = {
                    "nudge_id": nudge.id,
                    "employee_id": nudge.employee_id,
                    "nudge_type": nudge.nudge_type,
                    "severity": nudge.severity,
                    "message": nudge.message,
                    "evidence": nudge.evidence,
                    "created_at": nudge.created_at.isoformat(),
                }
                try:
                    response = httpx.post(
                        payload.webhook_url,
                        json=message_payload,
                        timeout=8.0,
                    )
                    response_code = response.status_code
                    status = "sent" if 200 <= response.status_code < 300 else "failed"
                    if status == "failed":
                        error_message = f"Webhook returned status {response.status_code}"
                except Exception as exc:  # noqa: BLE001
                    status = "failed"
                    error_message = str(exc)
        else:
            status = "sent"

        db.add(
            NudgeDispatchLog(
                nudge_id=nudge.id,
                channel=payload.channel,
                status=status,
                response_code=response_code,
                error_message=error_message,
                dispatched_at=datetime.utcnow(),
            )
        )

        items.append(
            NudgeDispatchItem(
                nudge_id=nudge.id,
                channel=payload.channel,
                status=status,
                response_code=response_code,
                error_message=error_message,
            )
        )

    db.commit()

    sent = sum(1 for item in items if item.status == "sent")
    failed = sum(1 for item in items if item.status == "failed")

    return NudgeDispatchResponse(
        attempted=len(items),
        sent=sent,
        failed=failed,
        items=items,
    )


def add_nudge_feedback(db: Session, *, nudge_id: int, payload: NudgeFeedbackCreate) -> NudgeFeedback | None:
    nudge = db.query(Nudge).filter(Nudge.id == nudge_id).first()
    if not nudge:
        return None

    feedback = NudgeFeedback(
        nudge_id=nudge_id,
        manager_identifier=payload.manager_identifier,
        action_taken=payload.action_taken,
        effectiveness_rating=payload.effectiveness_rating,
        notes=payload.notes,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_nudge_feedback(
    db: Session,
    *,
    nudge_id: int,
    search: str | None = None,
    rating: int | None = None,
) -> list[NudgeFeedback]:
    query = db.query(NudgeFeedback).filter(NudgeFeedback.nudge_id == nudge_id)
    if rating is not None:
        query = query.filter(NudgeFeedback.effectiveness_rating == rating)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (NudgeFeedback.manager_identifier.ilike(pattern))
            | (NudgeFeedback.action_taken.ilike(pattern))
            | (NudgeFeedback.notes.ilike(pattern))
        )

    return query.order_by(NudgeFeedback.created_at.desc()).all()


def list_nudge_dispatch_logs(db: Session, *, nudge_id: int) -> list[NudgeDispatchLog]:
    return (
        db.query(NudgeDispatchLog)
        .filter(NudgeDispatchLog.nudge_id == nudge_id)
        .order_by(NudgeDispatchLog.dispatched_at.desc())
        .all()
    )


def nudge_dispatch_logs_as_json(rows: list[NudgeDispatchLog]) -> str:
    payload = [
        NudgeDispatchLogRead.model_validate(row).model_dump(mode="json")
        for row in rows
    ]
    return json.dumps(payload)
