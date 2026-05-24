"""
Pydantic v2 models for the GSD Curriculum Development Consultancy dashboard.
Every field traces to either the TOR (Annex 2) or the action plan documents.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PhaseStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE    = "complete"


class DeliverableStatus(str, Enum):
    NOT_STARTED  = "not_started"
    IN_PROGRESS  = "in_progress"
    SUBMITTED    = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED     = "approved"
    REJECTED     = "rejected"


class QualityGate(str, Enum):
    DRAFT           = "draft"
    INTERNAL_REVIEW = "internal_review"
    IOM_REVIEW      = "iom_review"
    APPROVED        = "approved"


class ModuleStatus(str, Enum):
    NOT_STARTED       = "not_started"
    OUTLINE_COMPLETE  = "outline_complete"
    DRAFT_COMPLETE    = "draft_complete"
    STANDARDS_ALIGNED = "standards_aligned"
    FINALIZED         = "finalized"


class StakeholderRole(str, Enum):
    INFORMANT = "informant"
    REVIEWER  = "reviewer"
    APPROVER  = "approver"
    END_USER  = "end_user"


class ConsultationMethod(str, Enum):
    INTERVIEW       = "interview"
    FOCUS_GROUP     = "focus_group"
    DOCUMENT_REVIEW = "document_review"
    WORKSHOP        = "workshop"


class AccessStatus(str, Enum):
    CONFIRMED       = "confirmed"
    PENDING         = "pending"
    TO_BE_REQUESTED = "to_be_requested"


class ActorCategory(str, Enum):
    GSD_LEADERSHIP        = "GSD_leadership"
    GSD_ACADEMY           = "GSD_academy"
    GSD_OPERATIONAL       = "GSD_operational"
    GSD_LEGAL_IT          = "GSD_legal_it"
    IOM                   = "IOM"
    NATIONAL_PARTNER      = "national_partner"
    INTERNATIONAL_PARTNER = "international_partner"


class RiskCategory(str, Enum):
    ACCESS       = "access"
    COORDINATION = "coordination"
    SCOPE        = "scope"
    DELIVERY     = "delivery"


class RiskStatus(str, Enum):
    ACTIVE    = "active"
    MITIGATED = "mitigated"
    ESCALATED = "escalated"
    CLOSED    = "closed"


class IssueCategory(str, Enum):
    ACCESS       = "access"
    DOCUMENT     = "document"
    COORDINATION = "coordination"
    SCOPE        = "scope"


class IssueStatus(str, Enum):
    OPEN      = "open"
    RESOLVED  = "resolved"
    ESCALATED = "escalated"


class RiskLevel(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class StandardsMappingStatus(str, Enum):
    PENDING   = "pending"
    MAPPED    = "mapped"
    VALIDATED = "validated"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class ReportingLine(BaseModel):
    direct:  str
    overall: str


class Programme(BaseModel):
    id:             str
    title:          str
    org:            str
    beneficiary:    str
    unit:           str
    consultant:     str
    duty_station:   str
    start_date:     date
    duration_days:  int = Field(gt=0)
    reporting_line: ReportingLine


class Phase(BaseModel):
    id:         str
    name:       str
    start_week: int = Field(ge=1)
    end_week:   int = Field(ge=1)
    status:     PhaseStatus = PhaseStatus.NOT_STARTED

    @field_validator("end_week")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        start = info.data.get("start_week")
        if start is not None and v < start:
            raise ValueError("end_week must be >= start_week")
        return v

    def abs_start(self, programme_start: date) -> date:
        from datetime import timedelta
        return programme_start + timedelta(weeks=self.start_week - 1)

    def abs_end(self, programme_start: date) -> date:
        from datetime import timedelta
        return programme_start + timedelta(weeks=self.end_week) - timedelta(days=1)


class Milestone(BaseModel):
    id:             str
    description:    str
    target_date:    date
    completed:      bool = False
    completed_date: Optional[date] = None


class StatusHistoryEntry(BaseModel):
    status:     DeliverableStatus
    changed_at: datetime
    changed_by: str


class Deliverable(BaseModel):
    id:             str
    name:           str
    description:    str
    phase_id:       str
    due_week:       int = Field(ge=1)
    due_date:       date
    payment_pct:    float = Field(ge=0.0, le=100.0)
    status:         DeliverableStatus = DeliverableStatus.NOT_STARTED
    submitted_at:   Optional[date] = None
    approved_at:    Optional[date] = None
    reviewer:       str
    quality_gate:   QualityGate = QualityGate.DRAFT
    status_history: List[StatusHistoryEntry] = Field(default_factory=list)

    @property
    def days_to_deadline(self) -> int:
        return (self.due_date - date.today()).days

    @property
    def variance_days(self) -> Optional[int]:
        if self.submitted_at:
            return (self.submitted_at - self.due_date).days
        return None

    @property
    def is_overdue(self) -> bool:
        return (
            self.days_to_deadline < 0
            and self.status not in {
                DeliverableStatus.SUBMITTED,
                DeliverableStatus.UNDER_REVIEW,
                DeliverableStatus.APPROVED,
            }
        )


class Module(BaseModel):
    id:                     str
    title:                  str
    phase_id:               str
    status:                 ModuleStatus = ModuleStatus.NOT_STARTED
    standards_mapped:       List[str] = Field(default_factory=list)
    applicable_deliverable: str


class Stakeholder(BaseModel):
    id:                  str
    org_unit:            str
    contact_name:        Optional[str] = None   # PII — filtered at data layer
    contact_title:       Optional[str] = None   # PII — filtered at data layer
    actor_category:      ActorCategory
    role:                StakeholderRole
    method:              ConsultationMethod
    access_status:       AccessStatus = AccessStatus.TO_BE_REQUESTED
    consultation_window: Optional[str] = None
    engagement_score:    Optional[float] = Field(None, ge=0.0, le=10.0)


class RiskHistoryEntry(BaseModel):
    date:       date
    likelihood: int = Field(ge=1, le=5)
    impact:     int = Field(ge=1, le=5)
    status:     RiskStatus


class Risk(BaseModel):
    id:                 str
    description:        str
    category:           RiskCategory
    likelihood:         int = Field(ge=1, le=5)
    impact:             int = Field(ge=1, le=5)
    mitigation:         str
    escalation_trigger: str
    status:             RiskStatus = RiskStatus.ACTIVE
    owner:              str
    raised_date:        date
    history:            List[RiskHistoryEntry] = Field(default_factory=list)

    @property
    def risk_score(self) -> int:
        return self.likelihood * self.impact


class Issue(BaseModel):
    id:             int
    date_raised:    date
    description:    str
    category:       IssueCategory
    risk_level:     RiskLevel
    assigned_to:    str
    target_date:    date
    status:         IssueStatus = IssueStatus.OPEN

    @property
    def is_overdue(self) -> bool:
        return self.status == IssueStatus.OPEN and date.today() > self.target_date


class StandardsReference(BaseModel):
    id:      str
    source:  str
    standard: str
    modules: List[str]
    status:  StandardsMappingStatus = StandardsMappingStatus.MAPPED


class KPITrendPoint(BaseModel):
    date:  date
    value: float


class KPI(BaseModel):
    id:            str
    name:          str
    definition:    str
    unit:          str
    baseline:      float
    target:        float
    current_value: Optional[float] = None
    trend:         List[KPITrendPoint] = Field(default_factory=list)
    data_source:   str

    @property
    def trend_delta(self) -> Optional[float]:
        if len(self.trend) >= 2:
            return round(self.trend[-1].value - self.trend[-2].value, 2)
        return None

    @property
    def pct_to_target(self) -> Optional[float]:
        if self.target == self.baseline or self.current_value is None:
            return None
        return round((self.current_value - self.baseline) / (self.target - self.baseline) * 100, 1)


# ---------------------------------------------------------------------------
# Root payload
# ---------------------------------------------------------------------------

class ProgrammePayload(BaseModel):
    programme:          Programme
    phases:             List[Phase]
    milestones:         List[Milestone]
    deliverables:       List[Deliverable]
    modules:            List[Module]
    stakeholders:       List[Stakeholder]
    risks:              List[Risk]
    standards_reference: List[StandardsReference] = Field(default_factory=list)
    issues:             List[Issue] = Field(default_factory=list)
    kpis:               List[KPI] = Field(default_factory=list)
