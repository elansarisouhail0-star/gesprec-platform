from datetime import datetime
from io import BytesIO
import re

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.constants import split_multi
from app.database import get_db
from app.dependencies import get_optional_user, require_hse_group, require_roles
from app.emailer import send_email
from app.excel_export import build_declarations_xlsx
from app.models import Audience, Category, Declaration, Gravity, Role, Status, User, utcnow
from app.schemas import (
    AnalysisIn,
    AssignmentIn,
    DeclarationCreate,
    DeclarationOut,
    InterventionIn,
    PlanningIn,
    ResetDeclarationsIn,
    VerificationIn,
)
from app.security import verify_password
from app.services import add_history, add_notification, next_reference
from app.whatsapp import send_whatsapp_message, whatsapp_link

router = APIRouter(prefix="/declarations", tags=["declarations"])


def treatment_ateliers(user: User) -> list[str]:
    if Role(user.role) != Role.traitement:
        return []
    return split_multi(user.responsible_ateliers)


def assert_treatment_atelier_access(user: User, declaration: Declaration) -> None:
    if Role(user.role) != Role.traitement:
        return
    allowed_ateliers = treatment_ateliers(user)
    if not allowed_ateliers or declaration.atelier not in allowed_ateliers:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Atelier non autorisé pour ce responsable traitement")


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


def parse_phone_recipients(value: str | None) -> list[str]:
    return split_multi(value)


def treatment_users_for_atelier(db: Session, atelier: str) -> list[User]:
    users = list(db.scalars(select(User).where(User.role == Role.traitement, User.is_active == True)))  # noqa: E712
    return [user for user in users if atelier in split_multi(user.responsible_ateliers)]


def declaration_whatsapp_message(declaration: Declaration) -> str:
    return (
        "Bonjour,\n"
        f"Vous avez reçu une déclaration Gesprec au nom de votre atelier {declaration.atelier}.\n"
        f"Référence : {declaration.reference}\n"
        "Merci de visiter la plateforme pour consulter et traiter la déclaration."
    )


def deadline_whatsapp_message(declaration: Declaration) -> str:
    return (
        "Bonjour,\n"
        f"Rappel Gesprec : la déclaration {declaration.reference} arrive à sa date limite le {declaration.sla_date or '-'}.\n"
        f"Atelier : {declaration.atelier}\n"
        "Merci de finaliser le traitement dans les délais."
    )


def send_or_trace_whatsapp(db: Session, declaration: Declaration, phones: list[str], message: str, label: str, user: User | None = None) -> None:
    if not phones:
        add_history(db, declaration, f"{label} - aucun numéro WhatsApp renseigné", user)
        return
    sent_count = 0
    links = []
    for phone in phones:
        try:
            if send_whatsapp_message(phone, message):
                sent_count += 1
        except Exception as exc:
            add_history(db, declaration, f"{label} - échec WhatsApp vers {phone} : {exc}", user)
        link = whatsapp_link(phone, message)
        if link:
            links.append(link)
    if sent_count == len(phones):
        add_history(db, declaration, f"{label} - message WhatsApp envoyé à {sent_count}/{len(phones)} destinataire(s)", user)
    else:
        add_history(
            db,
            declaration,
            f"{label} - WhatsApp non envoyé automatiquement ({sent_count}/{len(phones)}). Liens à ouvrir : {' | '.join(links) or '-'}",
            user,
        )


def load_declaration(db: Session, declaration_id: int) -> Declaration:
    declaration = db.scalar(
        select(Declaration)
        .where(Declaration.id == declaration_id)
        .options(selectinload(Declaration.photos), selectinload(Declaration.history))
    )
    if not declaration:
        raise HTTPException(status_code=404, detail="Déclaration introuvable")
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
    add_history(db, declaration, f"Phase déclaration - déclaration créée sur {declaration.atelier}", user)
    add_notification(
        db,
        declaration,
        f"{prefix}Nouvelle déclaration {declaration.reference} ({declaration.category}) sur {declaration.atelier}",
        Audience.admin,
    )
    treatment_users = treatment_users_for_atelier(db, declaration.atelier)
    phones = []
    for treatment_user in treatment_users:
        phones.extend(parse_phone_recipients(treatment_user.phone_numbers))
    if treatment_users:
        add_notification(
            db,
            declaration,
            f"Nouvelle déclaration {declaration.reference} à traiter sur {declaration.atelier}",
            Audience.all,
        )
    send_or_trace_whatsapp(
        db,
        declaration,
        phones,
        declaration_whatsapp_message(declaration),
        "Phase déclaration - notification WhatsApp atelier",
        user,
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
    allowed_ateliers = treatment_ateliers(user)
    if Role(user.role) == Role.traitement and not allowed_ateliers:
        return []
    if allowed_ateliers:
        stmt = stmt.where(Declaration.atelier.in_(allowed_ateliers))
    if status_filter:
        stmt = stmt.where(Declaration.status == status_filter)
    if atelier:
        stmt = stmt.where(Declaration.atelier == atelier)
    if category:
        stmt = stmt.where(Declaration.category == category)
    if gravity:
        stmt = stmt.where(Declaration.real_gravity == gravity)
    return list(db.scalars(stmt.order_by(desc(Declaration.created_at)).limit(limit)))


@router.get("/export.xlsx")
def export_declarations_xlsx(
    db: Session = Depends(get_db),
    user: User = Depends(require_hse_group),
) -> StreamingResponse:
    stmt = select(Declaration).options(selectinload(Declaration.photos), selectinload(Declaration.history))
    declarations = list(db.scalars(stmt.order_by(desc(Declaration.created_at))).unique())
    content = build_declarations_xlsx(declarations)
    filename = f"archive_precurseurs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("", status_code=204)
def delete_all_declarations(
    payload: ResetDeclarationsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_hse_group),
) -> None:
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mot de passe QSSE incorrect")
    declarations = list(db.scalars(select(Declaration)))
    for declaration in declarations:
        db.delete(declaration)
    db.commit()
    return None


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
        f"Phase analyse - gravité retenue : {payload.real_gravity.value}; risque : {payload.risk_type}; cause probable : {payload.probable_cause or '-'}",
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
    selected_users = []
    if payload.responsible_ids:
        selected_users = list(db.scalars(select(User).where(User.id.in_(payload.responsible_ids), User.role == Role.traitement)))
        invalid_users = [user for user in selected_users if declaration.atelier not in split_multi(user.responsible_ateliers)]
        if invalid_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un responsable sélectionné n'est pas rattaché à l'atelier ciblé",
            )
    selected_names = [user.full_name for user in selected_users]
    selected_phones: list[str] = []
    for selected_user in selected_users:
        selected_phones.extend(parse_phone_recipients(selected_user.phone_numbers))
    payload_phones = parse_phone_recipients(payload.phone_numbers)
    phone_recipients = list(dict.fromkeys(selected_phones + payload_phones))
    responsible_label = ", ".join(selected_names) if selected_names else payload.responsible
    declaration.assigned_service = payload.service
    declaration.assigned_responsible = responsible_label
    declaration.priority = payload.priority
    declaration.sla_date = payload.sla_date
    declaration.resources = payload.resources
    recipients = parse_email_recipients(payload.email)
    declaration.assigned_email = ", ".join(recipients) if recipients else None
    declaration.assigned_phone_numbers = ", ".join(phone_recipients) if phone_recipients else None
    declaration.assigned_at = utcnow()
    declaration.assigned_by_id = user.id
    declaration.status = Status.affecte
    add_history(
        db,
        declaration,
        (
            f"Phase affectation - service: {payload.service}; responsable: {responsible_label}; "
            f"priorité : {payload.priority}; date limite : {payload.sla_date or '-'}; "
            f"destinataire(s) WhatsApp : {declaration.assigned_phone_numbers or '-'}"
        ),
        user,
    )
    add_notification(db, declaration, f"Déclaration {declaration.reference} affectée à {payload.service}", Audience.all)
    if recipients:
        try:
            sent_count = 0
            body = (
                "Bonjour,\n\n"
                "Une déclaration Gesprec vous a été affectée.\n\n"
                f"Référence : {declaration.reference}\n"
                f"Atelier : {declaration.atelier}\n"
                f"Gravité : {declaration.real_gravity}\n"
                f"Service : {payload.service}\n"
                f"Responsable : {responsible_label}\n"
                f"Priorité : {payload.priority}\n"
                f"Date limite SLA : {payload.sla_date or '-'}\n\n"
                "Merci de planifier et réaliser le traitement dans les délais.\n"
            )
            for recipient in recipients:
                if send_email(recipient, f"Date limite de traitement - Déclaration {declaration.reference}", body):
                    sent_count += 1
            add_history(
                db,
                declaration,
                (
                    f"Phase affectation - email de date limite envoyé à {sent_count}/{len(recipients)} destinataire(s) : {', '.join(recipients)}"
                    if sent_count == len(recipients)
                    else f"Phase affectation - email de date limite non envoyé à tous les destinataires ({sent_count}/{len(recipients)}) - vérifier SMTP : {', '.join(recipients)}"
                ),
                user,
            )
        except Exception as exc:
            add_history(db, declaration, f"Phase affectation - échec de l'envoi de l'email de date limite aux destinataires {', '.join(recipients)} : {exc}", user)
    else:
        add_history(db, declaration, "Phase affectation - aucun destinataire email renseigné", user)
    send_or_trace_whatsapp(
        db,
        declaration,
        phone_recipients,
        deadline_whatsapp_message(declaration),
        "Phase affectation - notification WhatsApp de date limite",
        user,
    )
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
            detail="La date de planification ne peut pas être supérieure à la date limite",
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
        f"Phase planification - intervention planifiée le {payload.date} à {payload.time}; collaborateurs : {payload.technicians or '-'}; matériel : {payload.material or '-'}",
        user,
    )
    add_notification(db, declaration, f"Déclaration {declaration.reference} planifiée", Audience.admin)
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date de réalisation obligatoire")
    if planned_date and intervention_date < planned_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de réalisation ne peut pas être inférieure à la date de planification",
        )
    if deadline_date and intervention_date > deadline_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de réalisation ne peut pas être supérieure à la date limite",
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
        f"Phase intervention - actions correctives réalisées le {payload.intervention_date}; durée : {payload.days} jour(s); difficultés : {payload.difficulties or '-'}",
        user,
    )
    add_notification(db, declaration, f"Déclaration {declaration.reference} prête pour vérification", Audience.admin)
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
        add_history(db, declaration, f"Phase vérification - conforme; déclaration clôturée; commentaire : {payload.comment or '-'}", user)
        add_notification(db, declaration, f"Déclaration {declaration.reference} conforme et clôturée", Audience.all)
    else:
        declaration.status = Status.planifie
        add_history(db, declaration, f"Phase vérification - non conforme; replanification demandée; commentaire : {payload.comment or '-'}", user)
        add_notification(db, declaration, f"Déclaration {declaration.reference} non conforme - replanification requise", Audience.all)
    db.commit()
    return load_declaration(db, declaration_id)
