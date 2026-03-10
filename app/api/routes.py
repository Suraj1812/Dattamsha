from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_api_key
from app.db.database import get_db
from app.models.entities import CollaborationEdge, Nudge
from app.schemas.hr import (
    HiringSimulationRequest,
    HiringSimulationResponse,
    IngestResponse,
    NudgeRead,
    ONARequest,
    ONAResponse,
    OrgHealthResponse,
    PolicyQueryRequest,
    PolicyQueryResponse,
    ProfileResponse,
    RiskRecord,
)
from app.services.ingest import load_sample_data
from app.services.insights import (
    build_employee_profile,
    get_org_health,
    headcount_by_department,
    list_risk_records,
)
from app.services.nudge_engine import generate_nudges
from app.services.ona import run_ona
from app.services.policy_assistant import answer_policy_question
from app.services.simulation import run_hiring_simulation

public_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_api_key)])


@public_router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@public_router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "alive"}


@public_router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@protected_router.post("/ingest/{source}", response_model=IngestResponse)
def ingest(source: str, db: Session = Depends(get_db)) -> IngestResponse:
    try:
        return load_sample_data(db, source=source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@protected_router.get("/employees/{employee_id}/profile", response_model=ProfileResponse)
def employee_profile(employee_id: int, db: Session = Depends(get_db)) -> ProfileResponse:
    profile = build_employee_profile(db, employee_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Employee not found")
    return profile


@protected_router.get("/insights/org-health", response_model=OrgHealthResponse)
def org_health(db: Session = Depends(get_db)) -> OrgHealthResponse:
    settings = get_settings()
    return get_org_health(
        db,
        attrition_threshold=settings.nudge_threshold_attrition,
        burnout_threshold=settings.nudge_threshold_burnout,
    )


@protected_router.get("/insights/risks", response_model=list[RiskRecord])
def risks(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[RiskRecord]:
    return list_risk_records(db, limit=limit)


@protected_router.get("/insights/headcount-by-department")
def org_structure(db: Session = Depends(get_db)) -> dict[str, int]:
    return headcount_by_department(db)


@protected_router.post("/nudges/generate", response_model=list[NudgeRead])
def generate_nudges_endpoint(db: Session = Depends(get_db)) -> list[Nudge]:
    return generate_nudges(db)


@protected_router.get("/nudges", response_model=list[NudgeRead])
def list_nudges(
    status: Literal["open", "resolved", "all"] = Query(default="open"),
    db: Session = Depends(get_db),
) -> list[Nudge]:
    query = db.query(Nudge)
    if status != "all":
        query = query.filter(Nudge.status == status)
    return query.order_by(Nudge.created_at.desc()).all()


@protected_router.post("/nudges/{nudge_id}/resolve", response_model=NudgeRead)
def resolve_nudge(nudge_id: int, db: Session = Depends(get_db)) -> Nudge:
    nudge = db.query(Nudge).filter(Nudge.id == nudge_id).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")
    nudge.status = "resolved"
    db.commit()
    db.refresh(nudge)
    return nudge


@protected_router.post("/simulations/hiring-impact", response_model=HiringSimulationResponse)
def hiring_simulation(payload: HiringSimulationRequest) -> HiringSimulationResponse:
    return run_hiring_simulation(payload)


@protected_router.post("/assistant/policy-query", response_model=PolicyQueryResponse)
def policy_query(payload: PolicyQueryRequest) -> PolicyQueryResponse:
    answer, citation = answer_policy_question(payload.question)
    return PolicyQueryResponse(answer=answer, citation=citation)


@protected_router.post("/insights/ona", response_model=ONAResponse)
def ona(payload: ONARequest) -> ONAResponse:
    return run_ona(payload.edges)


@protected_router.get("/insights/ona-from-db", response_model=ONAResponse)
def ona_from_db(db: Session = Depends(get_db)) -> ONAResponse:
    edges = db.query(CollaborationEdge).all()
    payload = ONARequest(
        edges=[
            {
                "source_employee_id": edge.source_employee_id,
                "target_employee_id": edge.target_employee_id,
                "interaction_count": edge.interaction_count,
            }
            for edge in edges
        ]
    )
    return run_ona(payload.edges)
