from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    hse = "hse"
    chef_technicentre_tmlc = "chef_technicentre_tmlc"
    chef_etablissement = "chef_etablissement"
    coordination = "coordination"
    traitement = "traitement"


class Category(str, Enum):
    securite = "Securite"
    surete = "Surete"
    maintenance = "Maintenance"
    qualite = "Qualite"
    environnement = "Environnement"


class Gravity(str, Enum):
    faible = "faible"
    moyen = "moyen"
    important = "important"
    critique = "critique"


class Status(str, Enum):
    nouvelle = "nouvelle"
    analyse = "analyse"
    affecte = "affecte"
    planifie = "planifie"
    realisee = "realisee"
    cloture = "cloture"


class Audience(str, Enum):
    admin = "admin"
    all = "all"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(String(40), index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Declaration(Base):
    __tablename__ = "declarations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    atelier: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[Category] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(Text)
    initial_gravity: Mapped[Gravity] = mapped_column(String(30))
    real_gravity: Mapped[Gravity] = mapped_column(String(30), index=True)
    status: Mapped[Status] = mapped_column(String(30), default=Status.nouvelle, index=True)

    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    reporter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporter_matricule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reporter_function: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reporter_service: Mapped[str | None] = mapped_column(String(150), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    risk_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    probable_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    analysis_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyzed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    assigned_service: Mapped[str | None] = mapped_column(String(180), nullable=True)
    assigned_responsible: Mapped[str | None] = mapped_column(String(180), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sla_date: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resources: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    planned_date: Mapped[str | None] = mapped_column(String(80), nullable=True)
    planned_time: Mapped[str | None] = mapped_column(String(80), nullable=True)
    planned_technicians: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_material: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    intervention_actions: Mapped[str | None] = mapped_column(Text, nullable=True)
    intervention_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intervention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intervention_date: Mapped[str | None] = mapped_column(String(80), nullable=True)
    intervention_difficulties: Mapped[str | None] = mapped_column(Text, nullable=True)
    intervention_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intervention_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    verification_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_conform: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    photos: Mapped[list["Photo"]] = relationship(cascade="all, delete-orphan", back_populates="declaration")
    history: Mapped[list["HistoryEvent"]] = relationship(cascade="all, delete-orphan", back_populates="declaration")
    notifications: Mapped[list["Notification"]] = relationship(cascade="all, delete-orphan", back_populates="declaration")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    declaration_id: Mapped[int] = mapped_column(ForeignKey("declarations.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    path: Mapped[str] = mapped_column(String(500))
    phase: Mapped[str] = mapped_column(String(40), default="declaration", index=True)
    data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    declaration: Mapped[Declaration] = relationship(back_populates="photos")


class HistoryEvent(Base):
    __tablename__ = "history_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    declaration_id: Mapped[int] = mapped_column(ForeignKey("declarations.id"), index=True)
    action: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    declaration: Mapped[Declaration] = relationship(back_populates="history")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    declaration_id: Mapped[int] = mapped_column(ForeignKey("declarations.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    audience: Mapped[Audience] = mapped_column(String(30), default=Audience.admin, index=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    declaration: Mapped[Declaration] = relationship(back_populates="notifications")
