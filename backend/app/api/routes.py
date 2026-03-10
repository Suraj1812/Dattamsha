from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    AccessContext,
    RBAC_PERMISSION_MATRIX,
    get_access_context,
    require_authenticated_access,
    require_permissions,
    require_roles,
)
from app.db.database import get_db
from app.models.entities import AuthUser, CollaborationEdge, Employee, IngestionRun, Nudge
from app.schemas.hr import (
    AuthConfigResponse,
    AuthAdminPasswordResetRequest,
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthPasswordChangeRequest,
    AuthRefreshRequest,
    AuthRoleUpdateRequest,
    AuthTokenResponse,
    AuthUserCreateRequest,
    AuthUserRead,
    AccessContextResponse,
    AuditEventRead,
    CohortAnalyticsResponse,
    CompensationSimulationRequest,
    CompensationSimulationResponse,
    EmployeeConsentRead,
    EmployeeConsentUpsert,
    EmployeeCreate,
    EmployeeDeleteResponse,
    EmployeeRead,
    EmployeeSummary,
    EmployeeUpdate,
    EmployeeTimelineResponse,
    HiringSimulationRequest,
    HiringSimulationResponse,
    IngestionRunRead,
    ManagerTeamOverviewResponse,
    NudgeDispatchLogRead,
    NudgeDispatchRequest,
    NudgeDispatchResponse,
    NudgeFeedbackCreate,
    NudgeFeedbackRead,
    NudgeRead,
    ONARequest,
    ONAResponse,
    OrgHealthResponse,
    RiskAnomalyResponse,
    PolicyQueryRequest,
    PolicyQueryResponse,
    ProfileResponse,
    RiskRecord,
    RiskTrendPoint,
    RolePermissions,
    SnapshotRefreshResponse,
    WorkforceFinanceResponse,
    WorkforceIngestRequest,
    WorkforceIngestResponse,
)
from app.services.compliance import (
    list_audit_events,
    list_employee_consents,
    log_audit_event,
    upsert_employee_consent,
)
from app.services.advanced_analytics import (
    build_employee_timeline,
    detect_risk_anomalies,
    get_cohort_analytics,
    get_risk_trends,
)
from app.services.auth import (
    admin_reset_auth_user_password,
    authenticate_user,
    create_auth_user,
    issue_token_pair,
    list_auth_users,
    mark_login_success,
    revoke_refresh_token,
    rotate_refresh_token,
    update_auth_user_password,
    update_auth_user_role,
)
from app.services.finance import get_workforce_finance
from app.services.insights import (
    build_employee_profile,
    create_employee,
    get_org_health,
    headcount_by_department,
    list_employees,
    list_risk_records,
    soft_delete_employee,
    update_employee,
)
from app.services.manager_insights import get_manager_team_overview
from app.services.nudge_delivery import (
    add_nudge_feedback,
    dispatch_nudges,
    list_nudge_dispatch_logs,
    list_nudge_feedback,
)
from app.services.nudge_engine import generate_nudges
from app.services.ona import run_ona
from app.services.policy_assistant import answer_policy_question
from app.services.risk_snapshot import refresh_risk_snapshots
from app.services.simulation import run_compensation_simulation, run_hiring_simulation
from app.services.workforce_ingest import ingest_workforce_payload

public_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_authenticated_access)])


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


@public_router.get("/auth/config", response_model=AuthConfigResponse)
def auth_config() -> AuthConfigResponse:
    settings = get_settings()
    return AuthConfigResponse(
        require_authentication=settings.require_authentication,
        require_api_key=settings.require_api_key,
        auth_allow_self_signup=settings.auth_allow_self_signup,
    )


@public_router.post("/auth/login", response_model=AuthTokenResponse)
def auth_login(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    settings = get_settings()
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token_pair = issue_token_pair(db, user, settings)
    mark_login_success(db, user)
    db.commit()
    db.refresh(user)
    return AuthTokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in,
        user=user,
        role=user.role,
        permissions=sorted(RBAC_PERMISSION_MATRIX.get(user.role, frozenset())),
    )


@public_router.post("/auth/refresh", response_model=AuthTokenResponse)
def auth_refresh(payload: AuthRefreshRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    settings = get_settings()
    try:
        user, token_pair = rotate_refresh_token(db, payload.refresh_token, settings)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    db.commit()
    db.refresh(user)
    return AuthTokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in,
        user=user,
        role=user.role,
        permissions=sorted(RBAC_PERMISSION_MATRIX.get(user.role, frozenset())),
    )


@protected_router.get(
    "/auth/me",
    response_model=AccessContextResponse,
)
def auth_me(
    access: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
) -> AccessContextResponse:
    role_permissions = [
        RolePermissions(role=role, permissions=sorted(permissions))
        for role, permissions in RBAC_PERMISSION_MATRIX.items()
    ]
    role_permissions.sort(key=lambda item: item.role)
    user = db.query(AuthUser).filter(AuthUser.id == access.user_id).first() if access.user_id else None
    return AccessContextResponse(
        role=access.role,
        permissions=sorted(access.permissions),
        available_roles=sorted(RBAC_PERMISSION_MATRIX),
        role_permissions=role_permissions,
        auth_type=access.auth_type,
        is_authenticated=access.is_authenticated,
        user=user,
    )


@protected_router.post("/auth/logout")
def auth_logout(payload: AuthLogoutRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    settings = get_settings()
    try:
        revoked = revoke_refresh_token(db, payload.refresh_token, settings)
    except ValueError:
        revoked = False
    db.commit()
    return {"status": "ok" if revoked else "not_found"}


@protected_router.get(
    "/auth/users",
    response_model=list[AuthUserRead],
    dependencies=[Depends(require_roles("admin"))],
)
def auth_users_list(db: Session = Depends(get_db)) -> list[AuthUserRead]:
    return list_auth_users(db)


@protected_router.post(
    "/auth/users",
    response_model=AuthUserRead,
    dependencies=[Depends(require_roles("admin"))],
)
def auth_users_create(payload: AuthUserCreateRequest, db: Session = Depends(get_db)) -> AuthUserRead:
    try:
        user = create_auth_user(
            db,
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
            password=payload.password,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_audit_event(
        db,
        action="auth.users.create",
        resource=f"user:{user.id}",
        details={"email": user.email, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@protected_router.patch(
    "/auth/users/{user_id}/role",
    response_model=AuthUserRead,
    dependencies=[Depends(require_roles("admin"))],
)
def auth_users_update_role(
    user_id: int,
    payload: AuthRoleUpdateRequest,
    db: Session = Depends(get_db),
) -> AuthUserRead:
    user = update_auth_user_role(db, user_id, payload.role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit_event(
        db,
        action="auth.users.role.update",
        resource=f"user:{user_id}",
        details={"role": payload.role},
    )
    db.commit()
    db.refresh(user)
    return user


@protected_router.post(
    "/auth/users/{user_id}/reset-password",
    response_model=AuthUserRead,
    dependencies=[Depends(require_roles("admin"))],
)
def auth_users_reset_password(
    user_id: int,
    payload: AuthAdminPasswordResetRequest,
    db: Session = Depends(get_db),
) -> AuthUserRead:
    user = admin_reset_auth_user_password(
        db,
        user_id,
        new_password=payload.new_password,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit_event(
        db,
        action="auth.users.password.reset",
        resource=f"user:{user_id}",
    )
    db.commit()
    db.refresh(user)
    return user


@protected_router.post("/auth/change-password")
def auth_change_password(
    payload: AuthPasswordChangeRequest,
    access: AccessContext = Depends(get_access_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if access.user_id is None:
        raise HTTPException(status_code=400, detail="Password change requires user token authentication")
    try:
        user = update_auth_user_password(
            db,
            access.user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit_event(
        db,
        action="auth.password.change",
        resource=f"user:{access.user_id}",
    )
    db.commit()
    return {"status": "ok"}


@protected_router.post(
    "/ingest/workforce",
    response_model=WorkforceIngestResponse,
    dependencies=[Depends(require_permissions("ingest.write"))],
)
def ingest_workforce(
    payload: WorkforceIngestRequest,
    db: Session = Depends(get_db),
) -> WorkforceIngestResponse:
    settings = get_settings()
    try:
        result = ingest_workforce_payload(
            db,
            payload,
            snapshot_batch_size=settings.snapshot_refresh_batch_size,
        )
        log_audit_event(
            db,
            action="ingest.workforce",
            resource=f"source:{payload.source}",
            details={
                "employees_upserted": result.employees_upserted,
                "metrics_upserted": result.metrics_upserted,
                "edges_upserted": result.edges_upserted,
            },
        )
        db.commit()
        return result
    except ValueError as exc:
        db.add(
            IngestionRun(
                source=payload.source,
                records_received=(
                    len(payload.employees)
                    + len(payload.engagement_metrics)
                    + len(payload.workload_metrics)
                    + len(payload.performance_metrics)
                    + len(payload.collaboration_edges)
                ),
                employees_upserted=0,
                metrics_upserted=0,
                edges_upserted=0,
                status="failed",
                details=str(exc),
            )
        )
        log_audit_event(
            db,
            action="ingest.workforce",
            resource=f"source:{payload.source}",
            outcome="failed",
            details={"error": str(exc)},
        )
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@protected_router.get(
    "/ingest/runs",
    response_model=list[IngestionRunRead],
    dependencies=[Depends(require_permissions("ingest.read"))],
)
def list_ingest_runs(
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    status: Literal["success", "failed", "all"] = Query(default="all"),
    db: Session = Depends(get_db),
) -> list[IngestionRun]:
    query = db.query(IngestionRun)
    if status != "all":
        query = query.filter(IngestionRun.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (cast(IngestionRun.id, String).ilike(pattern))
            | (IngestionRun.source.ilike(pattern))
            | (IngestionRun.status.ilike(pattern))
            | (IngestionRun.details.ilike(pattern))
        )
    return query.order_by(IngestionRun.created_at.desc()).offset(offset).limit(limit).all()


@protected_router.get(
    "/employees",
    response_model=list[EmployeeSummary],
    dependencies=[Depends(require_permissions("employees.read"))],
)
def employees_list(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    manager_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> list[EmployeeSummary]:
    return list_employees(db, limit=limit, offset=offset, search=search, manager_id=manager_id)


@protected_router.post(
    "/employees",
    response_model=EmployeeRead,
    dependencies=[Depends(require_permissions("employees.write"))],
)
def employees_create(payload: EmployeeCreate, db: Session = Depends(get_db)) -> EmployeeRead:
    try:
        employee = create_employee(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Employee with same email or external_id already exists") from exc
    log_audit_event(
        db,
        action="employees.create",
        resource=f"employee:{employee.id}",
        details={"email": employee.email, "department": employee.department},
    )
    db.commit()
    db.refresh(employee)
    return employee


@protected_router.patch(
    "/employees/{employee_id}",
    response_model=EmployeeRead,
    dependencies=[Depends(require_permissions("employees.write"))],
)
def employees_update(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
) -> EmployeeRead:
    try:
        employee = update_employee(db, employee_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Employee with same email or external_id already exists") from exc
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    log_audit_event(
        db,
        action="employees.update",
        resource=f"employee:{employee_id}",
        details={"employment_status": employee.employment_status},
    )
    db.commit()
    db.refresh(employee)
    return employee


@protected_router.delete(
    "/employees/{employee_id}",
    response_model=EmployeeDeleteResponse,
    dependencies=[Depends(require_permissions("employees.write"))],
)
def employees_delete(employee_id: int, db: Session = Depends(get_db)) -> EmployeeDeleteResponse:
    employee = soft_delete_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    log_audit_event(
        db,
        action="employees.delete",
        resource=f"employee:{employee_id}",
        details={"employment_status": "inactive"},
    )
    db.commit()
    return EmployeeDeleteResponse(status="deleted", employee_id=employee_id)


@protected_router.post(
    "/employees/{employee_id}/consents",
    response_model=EmployeeConsentRead,
    dependencies=[Depends(require_permissions("employees.consent.write"))],
)
def create_employee_consent(
    employee_id: int,
    payload: EmployeeConsentUpsert,
    db: Session = Depends(get_db),
) -> EmployeeConsentRead:
    consent = upsert_employee_consent(db, employee_id=employee_id, payload=payload)
    if consent is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    log_audit_event(
        db,
        action="consent.upsert",
        resource=f"employee:{employee_id}",
        details={
            "consent_type": payload.consent_type,
            "status": payload.status,
        },
    )
    db.commit()
    return consent


@protected_router.get(
    "/employees/{employee_id}/consents",
    response_model=list[EmployeeConsentRead],
    dependencies=[Depends(require_permissions("employees.consent.read"))],
)
def employee_consents(
    employee_id: int,
    consent_type: str | None = Query(default=None, min_length=1, max_length=60),
    status: Literal["granted", "revoked", "expired", "all"] = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EmployeeConsentRead]:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return list_employee_consents(
        db,
        employee_id=employee_id,
        consent_type=consent_type,
        status=None if status == "all" else status,
        limit=limit,
        offset=offset,
    )


@protected_router.get(
    "/employees/{employee_id}/profile",
    response_model=ProfileResponse,
    dependencies=[Depends(require_permissions("employees.read"))],
)
def employee_profile(employee_id: int, db: Session = Depends(get_db)) -> ProfileResponse:
    profile = build_employee_profile(db, employee_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Employee not found")
    return profile


@protected_router.get(
    "/employees/{employee_id}/timeline",
    response_model=EmployeeTimelineResponse,
    dependencies=[Depends(require_permissions("employees.read"))],
)
def employee_timeline(
    employee_id: int,
    days: int = Query(default=180, ge=1, le=730),
    limit: int = Query(default=60, ge=1, le=365),
    search_date: str | None = Query(default=None, min_length=1, max_length=20),
    risk_band: Literal["all", "high", "medium", "low"] = Query(default="all"),
    db: Session = Depends(get_db),
) -> EmployeeTimelineResponse:
    profile = build_employee_profile(db, employee_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Employee not found")
    return build_employee_timeline(
        db,
        employee_id=employee_id,
        days=days,
        limit=limit,
        search_date=search_date,
        risk_band=risk_band,
    )


@protected_router.get(
    "/insights/org-health",
    response_model=OrgHealthResponse,
    dependencies=[Depends(require_permissions("insights.read"))],
)
def org_health(db: Session = Depends(get_db)) -> OrgHealthResponse:
    settings = get_settings()
    return get_org_health(
        db,
        attrition_threshold=settings.nudge_threshold_attrition,
        burnout_threshold=settings.nudge_threshold_burnout,
    )


@protected_router.get(
    "/insights/risks",
    response_model=list[RiskRecord],
    dependencies=[Depends(require_permissions("insights.read"))],
)
def risks(
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    department: str | None = Query(default=None, min_length=1, max_length=120),
    min_risk: float | None = Query(default=None, ge=0, le=1),
    db: Session = Depends(get_db),
) -> list[RiskRecord]:
    return list_risk_records(
        db,
        limit=limit,
        offset=offset,
        search=search,
        department=department,
        min_risk=min_risk,
    )


@protected_router.get(
    "/insights/trends",
    response_model=list[RiskTrendPoint],
    dependencies=[Depends(require_permissions("insights.read"))],
)
def risk_trends(
    days: int = Query(default=90, ge=1, le=365),
    search_date: str | None = Query(default=None, min_length=1, max_length=20),
    db: Session = Depends(get_db),
) -> list[RiskTrendPoint]:
    return get_risk_trends(db, days=days, search_date=search_date)


@protected_router.get(
    "/insights/cohorts",
    response_model=CohortAnalyticsResponse,
    dependencies=[Depends(require_permissions("insights.read"))],
)
def cohort_analytics(
    dimension: Literal["department", "location", "manager"] = Query(default="department"),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> CohortAnalyticsResponse:
    settings = get_settings()
    return get_cohort_analytics(
        db,
        dimension=dimension,
        attrition_threshold=settings.nudge_threshold_attrition,
        burnout_threshold=settings.nudge_threshold_burnout,
        search=search,
    )


@protected_router.get(
    "/insights/anomalies",
    response_model=RiskAnomalyResponse,
    dependencies=[Depends(require_permissions("insights.read"))],
)
def risk_anomalies(
    dimension: Literal["department", "location", "manager"] = Query(default="department"),
    min_population: int = Query(default=3, ge=1, le=1000),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    severity: Literal["all", "high", "medium", "low"] = Query(default="all"),
    db: Session = Depends(get_db),
) -> RiskAnomalyResponse:
    settings = get_settings()
    return detect_risk_anomalies(
        db,
        dimension=dimension,
        attrition_threshold=settings.nudge_threshold_attrition,
        burnout_threshold=settings.nudge_threshold_burnout,
        min_population=min_population,
        search=search,
        severity=severity,
    )


@protected_router.post(
    "/insights/refresh-risk-snapshots",
    response_model=SnapshotRefreshResponse,
    dependencies=[Depends(require_permissions("ingest.write"))],
)
def refresh_snapshots_endpoint(
    batch_size: int | None = Query(default=None, ge=1, le=50_000),
    db: Session = Depends(get_db),
) -> SnapshotRefreshResponse:
    settings = get_settings()
    processed = refresh_risk_snapshots(
        db,
        batch_size=batch_size or settings.snapshot_refresh_batch_size,
    )
    log_audit_event(
        db,
        action="snapshots.refresh",
        resource="employee_risk_snapshots",
        details={"processed_employees": processed},
    )
    db.commit()
    return SnapshotRefreshResponse(processed_employees=processed)


@protected_router.get(
    "/insights/headcount-by-department",
    dependencies=[Depends(require_permissions("insights.read"))],
)
def org_structure(
    search: str | None = Query(default=None, min_length=1, max_length=120),
    department: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return headcount_by_department(db, search=search, department=department)


@protected_router.get(
    "/analytics/workforce-finance",
    response_model=WorkforceFinanceResponse,
    dependencies=[Depends(require_permissions("insights.read"))],
)
def workforce_finance(
    annual_revenue: float | None = Query(default=None, ge=0),
    department_search: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> WorkforceFinanceResponse:
    return get_workforce_finance(
        db,
        annual_revenue=annual_revenue,
        department_search=department_search,
    )


@protected_router.get(
    "/managers/{manager_id}/team-overview",
    response_model=ManagerTeamOverviewResponse,
    dependencies=[Depends(require_permissions("manager.read"))],
)
def manager_team_overview(
    manager_id: int,
    member_search: str | None = Query(default=None, min_length=1, max_length=120),
    risk_band: Literal["all", "high", "medium", "low"] = Query(default="all"),
    db: Session = Depends(get_db),
) -> ManagerTeamOverviewResponse:
    response = get_manager_team_overview(
        db,
        manager_id=manager_id,
        member_search=member_search,
        risk_band=risk_band,
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Manager not found")
    return response


@protected_router.post(
    "/nudges/generate",
    response_model=list[NudgeRead],
    dependencies=[Depends(require_permissions("nudges.write"))],
)
def generate_nudges_endpoint(db: Session = Depends(get_db)) -> list[Nudge]:
    nudges = generate_nudges(db)
    log_audit_event(
        db,
        action="nudges.generate",
        resource="nudges",
        details={"generated_or_updated": len(nudges)},
    )
    db.commit()
    return nudges


@protected_router.get(
    "/nudges",
    response_model=list[NudgeRead],
    dependencies=[Depends(require_permissions("nudges.read"))],
)
def list_nudges(
    status: Literal["open", "resolved", "all"] = Query(default="open"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    severity: Literal["all", "high", "medium", "low"] = Query(default="all"),
    nudge_type: str | None = Query(default=None, min_length=1, max_length=60),
    employee_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> list[Nudge]:
    query = db.query(Nudge).join(Employee, Employee.id == Nudge.employee_id)
    if status != "all":
        query = query.filter(Nudge.status == status)
    if severity != "all":
        query = query.filter(Nudge.severity == severity)
    if nudge_type:
        query = query.filter(Nudge.nudge_type == nudge_type)
    if employee_id is not None:
        query = query.filter(Nudge.employee_id == employee_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (cast(Nudge.id, String).ilike(pattern))
            | (cast(Nudge.employee_id, String).ilike(pattern))
            | (Nudge.message.ilike(pattern))
            | (Nudge.evidence.ilike(pattern))
            | (Nudge.nudge_type.ilike(pattern))
            | (Nudge.severity.ilike(pattern))
            | (Employee.full_name.ilike(pattern))
            | (Employee.department.ilike(pattern))
        )
    return query.order_by(Nudge.created_at.desc()).offset(offset).limit(limit).all()


@protected_router.post(
    "/nudges/{nudge_id}/resolve",
    response_model=NudgeRead,
    dependencies=[Depends(require_permissions("nudges.write"))],
)
def resolve_nudge(nudge_id: int, db: Session = Depends(get_db)) -> Nudge:
    nudge = db.query(Nudge).filter(Nudge.id == nudge_id).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")
    nudge.status = "resolved"
    log_audit_event(
        db,
        action="nudges.resolve",
        resource=f"nudge:{nudge_id}",
    )
    db.commit()
    db.refresh(nudge)
    return nudge


@protected_router.post(
    "/nudges/dispatch",
    response_model=NudgeDispatchResponse,
    dependencies=[Depends(require_permissions("nudges.write"))],
)
def dispatch_nudges_endpoint(
    payload: NudgeDispatchRequest,
    db: Session = Depends(get_db),
) -> NudgeDispatchResponse:
    result = dispatch_nudges(db, payload)
    log_audit_event(
        db,
        action="nudges.dispatch",
        resource=f"channel:{payload.channel}",
        details={
            "attempted": result.attempted,
            "sent": result.sent,
            "failed": result.failed,
        },
    )
    db.commit()
    return result


@protected_router.get(
    "/nudges/{nudge_id}/dispatches",
    response_model=list[NudgeDispatchLogRead],
    dependencies=[Depends(require_permissions("nudges.read"))],
)
def list_nudge_dispatches(nudge_id: int, db: Session = Depends(get_db)) -> list[NudgeDispatchLogRead]:
    nudge = db.query(Nudge).filter(Nudge.id == nudge_id).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")
    return list_nudge_dispatch_logs(db, nudge_id=nudge_id)


@protected_router.post(
    "/nudges/{nudge_id}/feedback",
    response_model=NudgeFeedbackRead,
    dependencies=[Depends(require_permissions("nudges.write"))],
)
def create_nudge_feedback(
    nudge_id: int,
    payload: NudgeFeedbackCreate,
    db: Session = Depends(get_db),
) -> NudgeFeedbackRead:
    feedback = add_nudge_feedback(db, nudge_id=nudge_id, payload=payload)
    if feedback is None:
        raise HTTPException(status_code=404, detail="Nudge not found")
    log_audit_event(
        db,
        action="nudges.feedback.create",
        resource=f"nudge:{nudge_id}",
        details={"effectiveness_rating": payload.effectiveness_rating},
    )
    db.commit()
    return feedback


@protected_router.get(
    "/nudges/{nudge_id}/feedback",
    response_model=list[NudgeFeedbackRead],
    dependencies=[Depends(require_permissions("nudges.read"))],
)
def get_nudge_feedback(
    nudge_id: int,
    search: str | None = Query(default=None, min_length=1, max_length=120),
    rating: int | None = Query(default=None, ge=1, le=5),
    db: Session = Depends(get_db),
) -> list[NudgeFeedbackRead]:
    nudge = db.query(Nudge).filter(Nudge.id == nudge_id).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")
    return list_nudge_feedback(db, nudge_id=nudge_id, search=search, rating=rating)


@protected_router.post(
    "/simulations/hiring-impact",
    response_model=HiringSimulationResponse,
    dependencies=[Depends(require_permissions("simulations.run"))],
)
def hiring_simulation(payload: HiringSimulationRequest) -> HiringSimulationResponse:
    return run_hiring_simulation(payload)


@protected_router.post(
    "/simulations/compensation-adjustment",
    response_model=CompensationSimulationResponse,
    dependencies=[Depends(require_permissions("simulations.run"))],
)
def compensation_simulation(
    payload: CompensationSimulationRequest,
    db: Session = Depends(get_db),
) -> CompensationSimulationResponse:
    return run_compensation_simulation(db, payload)


@protected_router.get(
    "/compliance/audit-events",
    response_model=list[AuditEventRead],
    dependencies=[Depends(require_permissions("compliance.read"))],
)
def compliance_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, min_length=1, max_length=80),
    outcome: Literal["success", "failed", "all"] = Query(default="all"),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> list[AuditEventRead]:
    return list_audit_events(
        db,
        limit=limit,
        offset=offset,
        action=action,
        outcome=None if outcome == "all" else outcome,
        search=search,
    )


@protected_router.post(
    "/assistant/policy-query",
    response_model=PolicyQueryResponse,
    dependencies=[Depends(require_permissions("assistant.query"))],
)
def policy_query(payload: PolicyQueryRequest) -> PolicyQueryResponse:
    answer, citation = answer_policy_question(payload.question)
    return PolicyQueryResponse(answer=answer, citation=citation)


@protected_router.post(
    "/insights/ona",
    response_model=ONAResponse,
    dependencies=[Depends(require_permissions("insights.read"))],
)
def ona(payload: ONARequest) -> ONAResponse:
    return run_ona(payload.edges)


@protected_router.get(
    "/insights/ona-from-db",
    response_model=ONAResponse,
    dependencies=[Depends(require_permissions("insights.read"))],
)
def ona_from_db(
    limit: int = Query(default=50_000, ge=1, le=200_000),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> ONAResponse:
    edges = db.query(CollaborationEdge).order_by(CollaborationEdge.id.desc()).limit(limit).all()
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
    result = run_ona(payload.edges)
    if search:
        needle = search.strip()
        result.most_central_employee_ids = [
            employee_id
            for employee_id in result.most_central_employee_ids
            if needle in str(employee_id)
        ]
        result.most_isolated_employee_ids = [
            employee_id
            for employee_id in result.most_isolated_employee_ids
            if needle in str(employee_id)
        ]
    return result
