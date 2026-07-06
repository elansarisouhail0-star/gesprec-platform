from datetime import datetime
import re

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_optional_user, require_hse_group, require_roles
from app.emailer import send_email
from app.models import Audience, Category, Declaration, Gravity, Role, Status, User, utcnow
from app.schemas import (
    AnalysisIn,
    AssignmentIn,
    DeclarationCreate,
    DeclarationOut,
    InterventionIn,
    PlanningIn,
    VerificationIn,
)
from app.services import add_history, add_notification, next_reference

router = APIRouter(prefix="/declarations", tags=["declarations"])

TREATMENT_ATELIERS = {
    "traitement1@gesprec.local": "Atelier HITACHI",
    "traitement2@gesprec.local": "Atelier levage",
    "traitement3@gesprec.local": "Atelier Tour en fosse",
}


def treatment_atelier(user: User) -> str | None:
    return TREATMENT_ATELIERS.get(user.email.lower())


def assert_treatment_atelier_access(user: User, declaration: Declaration) -> None:
    if Role(user.role) != Role.traitement:
        return
    allowed_atelier = treatment_atelier(user)
    if allowed_atelier and declaration.atelier != allowed_atelier:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Atelier non autorise pour ce responsable traitement")


def parse_calendar_date(value: str | None) -> datetime | None:
    if not value or value in {"-", "—"}:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_email_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    raw_items = [item.strip() for item in re.split(r"[;,]", value) if item.strip()]
    recipients: list[str] = []
    invalid: list[str] = []
    for item in raw_items:
        try:
            recipients.append(validate_email(item, check_deliverability=False).normalized)
        except EmailNotValidError:
            invalid.append(item)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adresse email invalide: " + ", ".join(invalid),
        )
    return recipients


def load_declaration(db: Session, declaration_id: int) -> Declaration:
    declaration = db.scalar(
        select(Declaration)
        .where(Declaration.id == declaration_id)
        .options(selectinload(Declaration.photos), selectinload(Declaration.history))
    )
    if not declaration:
        raise HTTPException(status_code=404, detail="Declaration introuvable")
    return declaration


def assert_status(declaration: Declaration, expected: Status) -> None:
    if Status(declaration.status) != expected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Statut attendu: {expected.value}; statut actuel: {declaration.status}",
        )


@router.post("", response_model=DeclarationOut, status_code=201)
def create_declaration(
    payload: DeclarationCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Declaration:
    declaration = Declaration(
        reference=next_reference(db),
        atelier=payload.atelier,
        category=Category(payload.category),
        description=payload.description,
        initial_gravity=Gravity(payload.gravity),
        real_gravity=Gravity(payload.gravity),
        anonymous=payload.anonymous,
        reporter_name="Anonyme" if payload.anonymous else payload.reporter_name,
        reporter_matricule=payload.reporter_matricule,
        reporter_function=payload.reporter_function,
        reporter_service=payload.reporter_service,
        location=payload.location,
        created_by_id=user.id if user else None,
    )
    db.add(declaration)
    db.flush()
    prefix = "CRITIQUE - " if payload.gravity == Gravity.critique else ""
    add_history(db, declaration, f"Phase declaration - declaration creee sur {declaration.atelier}", user)
    add_notification(
        db,
        declaration,
        f"{prefix}Nouvelle declaration {declaration.reference} ({declaration.category}) sur {declaration.atelier}",
        Audience.admin,
    )
    db.commit()
    db.refresh(declaration)
    return load_declaration(db, declaration.id)


@router.get("", response_model=list[DeclarationOut])
def list_declarations(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.hse, Role.chef_technicentre_tmlc, Role.coordination, Role.traitement)),
    status_filter: Status | None = Query(default=None, alias="status"),
    atelier: str | None = None,
    category: Category | None = None,
    gravity: Gravity | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[Declaration]:
    stmt = select(Declaration).options(selectinload(Declaration.photos), selectinload(Declaration.history))
    allowed_atelier = treatment_atelier(user)
    if allowed_atelier:
        stmt = stmt.where(Declaration.atelier == allowed_atelier)
    if status_filter:
        stmt = stmt.where(Declaration.status == status_filter)
    if atelier:
        stmt = stmt.where(Declaration.atelier == atelier)
    if category:
        stmt = stmt.where(Declaration.category == category)
    if gravity:
        stmt = stmt.where(Declaration.real_gravity == gravity)
    return list(db.scalars(stmt.order_by(desc(Declaration.created_at)).limit(limit)))


@router.get("/{declaration_id}", response_model=DeclarationOut)
def get_declaration(
    declaration_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.hse, Role.chef_technicentre_tmlc, Role.coordination, Role.traitement)),
) -> Declaration:
    declaration = load_declaration(db, declaration_id)
    assert_treatment_atelier_access(user, declaration)
    return declaration


@router.post("/{declaration_id}/analyse", response_model=DeclarationOut)
def analyse_declaration(
    declaration_id: int,
    payload: AnalysisIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_hse_group),
) -> Declaration:
    declaration = load_declaration(db, declaration_id)
    assert_status(declaration, Status.nouvelle)
    declaration.real_gravity = Gravity(payload.real_gravity)
    declaration.risk_type = payload.risk_type
    declaration.probable_cause = payload.probable_cause
    declaration.analysis_comment = payload.comment
    declaration.analysis_at = utcnow()
    declaration.analyzed_by_id = user.id
    declaration.status = Status.analyse
    add_history(
        db,
        declaration,
        f"Phase analyse - gravite retenue: {payload.real_gravity.value}; risque: {payload.risk_type}; cause probable: {payload.probable_cause or '-'}",
        user,
    )
    db.commit()
    return load_declaration(db, declaration_id)


@router.post("/{declaration_id}/affectation", response_model=DeclarationOut)
def assign_declaration(
    declaration_id: int,
    payload: AssignmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_hse_group),
) -> Declaration:
    declaration = load_declaration(db, declaration_id)
    assert_status(declaration, Status.analyse)
    declaration.assigned_service = payload.service
    declaration.assigned_responsible = payload.responsible
    declaration.priority = payload.priority
    declaration.sla_date = payload.sla_date
    declaration.resources = payload.resources
    recipients = parse_email_recipients(payload.email)
    declaration.assigned_email = ", ".join(recipients) if recipients else None
    declaration.assigned_at = utcnow()
    declaration.assigned_by_id = user.id
    declaration.status = Status.affecte
    add_history(
        db,
        declaration,
        (
            f"Phase affectation - service: {payload.service}; responsable: {payload.responsible}; "
            f"priorite: {payload.priority}; date limite: {payload.sla_date or '-'}; "
            f"destinataire email: {declaration.assigned_email or '-'}"
        ),
        user,
    )
    add_notification(db, declaration, f"Declaration {declaration.reference} affectee a {payload.service}", Audience.all)
    if recipients:
        try:
            sent_count = 0
            body = (
                "Bonjour,\n\n"
                "Une declaration Gesprec vous a ete affectee.\n\n"
                f"Reference: {declaration.reference}\n"
                f"Atelier: {declaration.atelier}\n"
                f"Gravite: {declaration.real_gravity}\n"
                f"Service: {payload.service}\n"
                f"Responsable: {payload.responsible}\n"
                f"Priorite: {payload.priority}\n"
                f"Date limite SLA: {payload.sla_date or '-'}\n\n"
                "Merci de planifier et realiser le traitement dans les delais.\n"
            )
            for recipient in recipients:
                if send_email(recipient, f"Deadline traitement - Declaration {declaration.reference}", body):
                    sent_count += 1
            add_history(
                db,
                declaration,
                (
                    f"Phase affectation - email deadline envoye a {sent_count}/{len(recipients)} destinataire(s): {', '.join(recipients)}"
                    if sent_count == len(recipients)
                    else f"Phase affectation - email deadline non envoye a tous les destinataires ({sent_count}/{len(recipients)}) - verifier SMTP: {', '.join(recipients)}"
                ),
                user,
            )
        except Exception as exc:
            add_history(db, declaration, f"Phase affectation - echec envoi email deadline aux destinataires {', '.join(recipients)}: {exc}", user)
    else:
        add_history(db, declaration, "Phase affectation - aucun destinataire email renseigne", user)
    db.commit()
    return load_declaration(db, declaration_id)


@router.post("/{declaration_id}/planification", response_model=DeclarationOut)
def plan_declaration(
    declaration_id: int,
    payload: PlanningIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.traitement)),
) -> Declaration:
    declaration = load_declaration(db, declaration_id)
    assert_treatment_atelier_access(user, declaration)
    assert_status(declaration, Status.affecte)
    deadline_date = parse_calendar_date(declaration.sla_date)
    planned_date = parse_calendar_date(payload.date)
    if not planned_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date de planification obligatoire")
    if deadline_date and planned_date > deadline_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de planification ne peut pas etre superieure a la date limite",
        )
    declaration.planned_date = payload.date
    declaration.planned_time = payload.time
    declaration.planned_technicians = payload.technicians
    declaration.planned_material = payload.material
    declaration.planned_at = utcnow()
    declaration.planned_by_id = user.id
    declaration.status = Status.planifie
    add_history(
        db,
        declaration,
        f"Phase planification - intervention planifiee le {payload.date} a {payload.time}; techniciens: {payload.technicians or '-'}; materiel: {payload.material or '-'}",
        user,
    )
    add_notification(db, declaration, f"Declaration {declaration.reference} planifiee", Audience.admin)
    db.commit()
    return load_declaration(db, declaration_id)


@router.post("/{declaration_id}/intervention", response_model=DeclarationOut)
def complete_intervention(
    declaration_id: int,
    payload: InterventionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.traitement)),
) -> Declaration:
    declaration = load_declaration(db, declaration_id)
    assert_treatment_atelier_access(user, declaration)
    assert_status(declaration, Status.planifie)
    deadline_date = parse_calendar_date(declaration.sla_date)
    planned_date = parse_calendar_date(declaration.planned_date)
    intervention_date = parse_calendar_date(payload.intervention_date)
    if not intervention_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date de realisation obligatoire")
    if planned_date and intervention_date < planned_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de realisation ne peut pas etre inferieure a la date de planification",
        )
    if deadline_date and intervention_date > deadline_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de realisation ne peut pas etre superieure a la date limite",
        )
    declaration.intervention_actions = payload.actions
    declaration.intervention_minutes = payload.minutes
    declaration.intervention_days = payload.days
    declaration.intervention_date = payload.intervention_date
    declaration.intervention_difficulties = payload.difficulties
    declaration.intervention_at = utcnow()
    declaration.intervention_by_id = user.id
    declaration.status = Status.realisee
    add_history(
        db,
        declaration,
        f"Phase intervention - actions correctives realisees le {payload.intervention_date}; duree: {payload.days} jour(s); difficultes: {payload.difficulties or '-'}",
        user,
    )
    add_notification(db, declaration, f"Declaration {declaration.reference} prete pour verification", Audience.admin)
    db.commit()
    return load_declaration(db, declaration_id)


@router.post("/{declaration_id}/verification", response_model=DeclarationOut)
def verify_declaration(
    declaration_id: int,
    payload: VerificationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_hse_group),
) -> Declaration:
    declaration = load_declaration(db, declaration_id)
    assert_status(declaration, Status.realisee)
    declaration.verification_comment = payload.comment
    declaration.is_conform = payload.conform
    declaration.closed_by_id = user.id if payload.conform else None
    if payload.conform:
        declaration.status = Status.cloture
        declaration.closed_at = utcnow()
        add_history(db, declaration, f"Phase verification - conforme; declaration cloturee; commentaire: {payload.comment or '-'}", user)
        add_notification(db, declaration, f"Declaration {declaration.reference} conforme et cloturee", Audience.all)
    else:
        declaration.status = Status.planifie
        add_history(db, declaration, f"Phase verification - non conforme; replanification demandee; commentaire: {payload.comment or '-'}", user)
        add_notification(db, declaration, f"Declaration {declaration.reference} non conforme - replanification requise", Audience.all)
    db.commit()
    return load_declaration(db, declaration_id)
