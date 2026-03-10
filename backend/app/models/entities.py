from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    department: Mapped[str] = mapped_column(String(120), index=True)
    role: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(120))
    hire_date: Mapped[date] = mapped_column(Date)
    employment_status: Mapped[str] = mapped_column(String(60), default="active")
    base_salary: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    manager: Mapped["Employee | None"] = relationship(
        "Employee", remote_side="Employee.id", backref="direct_reports"
    )
    profile_details: Mapped["EmployeeProfileDetails | None"] = relationship(
        "EmployeeProfileDetails",
        back_populates="employee",
        uselist=False,
        cascade="all, delete-orphan",
    )


class EmployeeProfileDetails(Base):
    __tablename__ = "employee_profile_details"
    __table_args__ = (
        Index("ix_employee_profile_details_updated_at", "updated_at"),
    )

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    preferred_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_image_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    employee: Mapped[Employee] = relationship("Employee", back_populates="profile_details")


class EngagementMetric(Base):
    __tablename__ = "engagement_metrics"
    __table_args__ = (
        UniqueConstraint("employee_id", "snapshot_date", name="uq_engagement_employee_snapshot"),
        CheckConstraint("engagement_score >= 0 AND engagement_score <= 1", name="ck_engagement_score"),
        CheckConstraint("sentiment_score >= 0 AND sentiment_score <= 1", name="ck_sentiment_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    engagement_score: Mapped[float] = mapped_column(Float)
    sentiment_score: Mapped[float] = mapped_column(Float)

    employee: Mapped[Employee] = relationship("Employee")


class WorkloadMetric(Base):
    __tablename__ = "workload_metrics"
    __table_args__ = (
        UniqueConstraint("employee_id", "snapshot_date", name="uq_workload_employee_snapshot"),
        CheckConstraint("overtime_hours >= 0", name="ck_overtime_non_negative"),
        CheckConstraint("meeting_hours >= 0", name="ck_meeting_hours_non_negative"),
        CheckConstraint("after_hours_messages >= 0", name="ck_after_hours_msgs_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0)
    meeting_hours: Mapped[float] = mapped_column(Float, default=0)
    after_hours_messages: Mapped[int] = mapped_column(Integer, default=0)

    employee: Mapped[Employee] = relationship("Employee")


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    __table_args__ = (
        UniqueConstraint("employee_id", "snapshot_date", name="uq_performance_employee_snapshot"),
        CheckConstraint("performance_rating >= 0 AND performance_rating <= 1", name="ck_perf_rating"),
        CheckConstraint("goal_completion_pct >= 0 AND goal_completion_pct <= 1", name="ck_goal_completion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    performance_rating: Mapped[float] = mapped_column(Float)
    goal_completion_pct: Mapped[float] = mapped_column(Float)

    employee: Mapped[Employee] = relationship("Employee")


class EmployeeRiskSnapshot(Base):
    __tablename__ = "employee_risk_snapshots"
    __table_args__ = (
        CheckConstraint("attrition_risk >= 0 AND attrition_risk <= 1", name="ck_snapshot_attrition"),
        CheckConstraint("burnout_risk >= 0 AND burnout_risk <= 1", name="ck_snapshot_burnout"),
        Index("ix_employee_risk_snapshots_attrition", "attrition_risk"),
        Index("ix_employee_risk_snapshots_burnout", "burnout_risk"),
        Index("ix_employee_risk_snapshots_snapshot_date", "snapshot_date"),
    )

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date)
    engagement_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overtime_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    meeting_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_hours_messages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performance_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_completion_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    attrition_risk: Mapped[float] = mapped_column(Float)
    burnout_risk: Mapped[float] = mapped_column(Float)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    employee: Mapped[Employee] = relationship("Employee")


class CollaborationEdge(Base):
    __tablename__ = "collaboration_edges"
    __table_args__ = (
        UniqueConstraint("source_employee_id", "target_employee_id", name="uq_collab_edge"),
        CheckConstraint("interaction_count >= 1", name="ck_interaction_count_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    target_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    interaction_count: Mapped[int] = mapped_column(Integer, default=1)
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Nudge(Base):
    __tablename__ = "nudges"
    __table_args__ = (Index("ix_nudges_status_created_at", "status", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    nudge_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    employee: Mapped[Employee] = relationship("Employee")


class NudgeDispatchLog(Base):
    __tablename__ = "nudge_dispatch_logs"
    __table_args__ = (
        Index("ix_nudge_dispatch_logs_nudge_channel", "nudge_id", "channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nudge_id: Mapped[int] = mapped_column(ForeignKey("nudges.id"), index=True)
    channel: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    nudge: Mapped[Nudge] = relationship("Nudge")


class NudgeFeedback(Base):
    __tablename__ = "nudge_feedback"
    __table_args__ = (
        CheckConstraint("effectiveness_rating >= 1 AND effectiveness_rating <= 5", name="ck_nudge_effectiveness"),
        Index("ix_nudge_feedback_nudge_created", "nudge_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nudge_id: Mapped[int] = mapped_column(ForeignKey("nudges.id"), index=True)
    manager_identifier: Mapped[str] = mapped_column(String(120), index=True)
    action_taken: Mapped[str] = mapped_column(Text)
    effectiveness_rating: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    nudge: Mapped[Nudge] = relationship("Nudge")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    employees_upserted: Mapped[int] = mapped_column(Integer, default=0)
    metrics_upserted: Mapped[int] = mapped_column(Integer, default=0)
    edges_upserted: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), index=True, default="success")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class EmployeeConsent(Base):
    __tablename__ = "employee_consents"
    __table_args__ = (
        CheckConstraint("status IN ('granted','revoked','expired')", name="ck_employee_consent_status"),
        Index("ix_employee_consents_employee_type_created", "employee_id", "consent_type", "created_at"),
        Index("ix_employee_consents_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    consent_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    source: Mapped[str] = mapped_column(String(80), default="system")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    employee: Mapped[Employee] = relationship("Employee")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_action_created", "action", "created_at"),
        Index("ix_audit_events_outcome_created", "outcome", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(120), index=True)
    outcome: Mapped[str] = mapped_column(String(20), index=True, default="success")
    actor: Mapped[str] = mapped_column(String(120), default="system")
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuthUser(Base):
    __tablename__ = "auth_users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','hr_admin','manager','analyst','employee')",
            name="ck_auth_users_role",
        ),
        Index("ix_auth_users_role_active", "role", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_jti", name="uq_auth_refresh_tokens_jti"),
        Index("ix_auth_refresh_tokens_user_active", "user_id", "revoked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_users.id"), index=True)
    token_jti: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    replaced_by_token_jti: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped[AuthUser] = relationship("AuthUser")
