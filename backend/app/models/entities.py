from datetime import date, datetime

from sqlalchemy import (
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
