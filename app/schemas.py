from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import Audience, Category, Gravity, Role, Status


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    responsible_ateliers: str | None = None
    phone_numbers: str | None = None
    manager_id: int | None = None


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    role: Role
    password: str = Field(min_length=8, max_length=128)
    responsible_ateliers: str | None = Field(default=None, max_length=2000)
    phone_numbers: str | None = Field(default=None, max_length=500)
    manager_id: int | None = None


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: Role | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    responsible_ateliers: str | None = Field(default=None, max_length=2000)
    phone_numbers: str | None = Field(default=None, max_length=500)
    manager_id: int | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ResetDeclarationsIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_name: str
    content_type: str
    phase: str = "declaration"
    data_url: str | None = None
    created_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    actor_id: int | None = None
    created_at: datetime


class CollaboratorAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    full_name: str
    email: str
    task_description: str | None = None
    intervention_date: str | None = None
    intervention_days: int | None = None
    difficulties: str | None = None
    completed_at: datetime | None = None


class DeclarationCreate(BaseModel):
    atelier: str = Field(min_length=2, max_length=120)
    category: Category
    description: str = Field(min_length=5)
    gravity: Gravity = Gravity.moyen
    anonymous: bool = False
    reporter_name: str | None = None
    reporter_matricule: str | None = None
    reporter_function: str | None = None
    reporter_service: str | None = None
    location: str | None = None


class AnalysisIn(BaseModel):
    real_gravity: Gravity
    risk_type: str = Field(min_length=2, max_length=255)
    probable_cause: str | None = None
    comment: str | None = None


class AssignmentIn(BaseModel):
    service: str = Field(min_length=2, max_length=180)
    responsible: str = Field(min_length=2, max_length=180)
    responsible_ids: list[int] = Field(default_factory=list)
    priority: str = "Normale"
    sla_date: str | None = None
    resources: str | None = None
    email: str | None = Field(default=None, max_length=1000)
    phone_numbers: str | None = Field(default=None, max_length=500)


class PlanningIn(BaseModel):
    date: str
    time: str
    technicians: str | None = None
    collaborator_ids: list[int] = Field(default_factory=list)
    material: str | None = None


class InterventionIn(BaseModel):
    actions: str = Field(min_length=3)
    minutes: int = Field(default=0, ge=0)
    days: int = Field(default=0, ge=0)
    intervention_date: str = Field(min_length=10, max_length=80)
    difficulties: str | None = None


class VerificationIn(BaseModel):
    conform: bool
    comment: str | None = None


class CollaboratorTaskIn(BaseModel):
    task_description: str = Field(min_length=3)
    intervention_date: str | None = Field(default=None, max_length=80)
    days: int = Field(default=0, ge=0)
    difficulties: str | None = None


class DeclarationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    atelier: str
    category: Category
    description: str
    initial_gravity: Gravity
    real_gravity: Gravity
    status: Status
    anonymous: bool
    reporter_name: str | None = None
    reporter_matricule: str | None = None
    reporter_function: str | None = None
    reporter_service: str | None = None
    location: str | None = None

    risk_type: str | None = None
    probable_cause: str | None = None
    analysis_comment: str | None = None
    analysis_at: datetime | None = None

    assigned_service: str | None = None
    assigned_responsible: str | None = None
    assigned_responsible_ids: str | None = None
    priority: str | None = None
    sla_date: str | None = None
    resources: str | None = None
    assigned_email: str | None = None
    assigned_phone_numbers: str | None = None
    assigned_at: datetime | None = None

    planned_date: str | None = None
    planned_time: str | None = None
    planned_technicians: str | None = None
    planned_material: str | None = None
    planned_at: datetime | None = None

    intervention_actions: str | None = None
    intervention_minutes: int | None = None
    intervention_days: int | None = None
    intervention_date: str | None = None
    intervention_difficulties: str | None = None
    intervention_at: datetime | None = None

    verification_comment: str | None = None
    is_conform: bool | None = None
    closed_at: datetime | None = None

    created_at: datetime
    updated_at: datetime
    photos: list[PhotoOut] = []
    history: list[HistoryOut] = []
    collaborators: list[CollaboratorAssignmentOut] = []


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    declaration_id: int
    message: str
    audience: Audience
    read: bool
    created_at: datetime


class DashboardStats(BaseModel):
    totals: dict[str, int]
    by_gravity: dict[str, int]
    by_category: dict[str, int]
    by_status: dict[str, int]
    by_atelier: dict[str, int]
    latest: list[DeclarationOut]


class ErrorOut(BaseModel):
    detail: str | list[dict[str, Any]]
