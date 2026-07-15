from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.config import get_settings
from app.emailer import send_email, smtp_enabled
from app.constants import split_multi
from app.models import Declaration, HistoryEvent, Role, Status, User
from app.routers.declarations import send_or_trace_whatsapp
from app.whatsapp import send_whatsapp_message, whatsapp_enabled, whatsapp_link

router = APIRouter(prefix="/system", tags=["system"])


class EmailTestIn(BaseModel):
    to_email: str = Field(min_length=3, max_length=255)


class WhatsAppTestIn(BaseModel):
    phone_number: str = Field(min_length=6, max_length=40)


@router.get("/email-status")
def email_status(_: User = Depends(require_roles(Role.hse))) -> dict[str, bool | int]:
    settings = get_settings()
    return {
        "smtp_enabled": smtp_enabled(),
        "smtp_host_configured": bool(settings.smtp_host),
        "smtp_from_configured": bool(settings.smtp_from),
        "smtp_username_configured": bool(settings.smtp_username),
        "smtp_port": settings.smtp_port,
        "smtp_tls": settings.smtp_tls,
    }


@router.post("/email-test")
def email_test(payload: EmailTestIn, _: User = Depends(require_roles(Role.hse))) -> dict[str, bool]:
    try:
        sent = send_email(
            payload.to_email,
            "Test email Gesprec",
            "Ceci est un test d'envoi SMTP depuis la plateforme Gesprec.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Echec SMTP: {exc}")
    return {"sent": sent}


@router.get("/whatsapp-status")
def whatsapp_status(_: User = Depends(require_roles(Role.hse))) -> dict[str, bool]:
    settings = get_settings()
    return {
        "whatsapp_enabled": whatsapp_enabled(),
        "token_configured": bool(settings.whatsapp_token),
        "phone_number_id_configured": bool(settings.whatsapp_phone_number_id),
    }


@router.post("/whatsapp-test")
def whatsapp_test(payload: WhatsAppTestIn, _: User = Depends(require_roles(Role.hse))) -> dict[str, bool | str]:
    message = "Test WhatsApp Gesprec: la configuration de notification fonctionne."
    try:
        sent = send_whatsapp_message(payload.phone_number, message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Echec WhatsApp: {exc}")
    return {
        "sent": sent,
        "manual_link": "" if sent else whatsapp_link(payload.phone_number, message),
    }


@router.post("/whatsapp-reminders")
def whatsapp_reminders(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.hse)),
) -> dict[str, int]:
    return {"processed": process_whatsapp_reminders(db, user)}


def process_whatsapp_reminders(db: Session, user: User | None = None) -> int:
    target = (date.today() + timedelta(days=1)).isoformat()
    declarations = list(
        db.scalars(
            select(Declaration).where(
                or_(Declaration.planned_date == target, Declaration.sla_date == target),
                Declaration.status.in_([Status.affecte, Status.planifie]),
            )
        )
    )
    processed = 0
    for declaration in declarations:
        already_sent = db.scalar(
            select(HistoryEvent).where(
                HistoryEvent.declaration_id == declaration.id,
                HistoryEvent.action.like(f"%Rappel WhatsApp J-1%{target}%"),
            )
        )
        if already_sent:
            continue
        phones = split_multi(declaration.assigned_phone_numbers)
        send_or_trace_whatsapp(
            db,
            declaration,
            phones,
            reminder_j1_message(declaration),
            f"Rappel WhatsApp J-1 - {target}",
            user,
        )
        processed += 1
    db.commit()
    return processed


def reminder_j1_message(declaration: Declaration) -> str:
    planned = declaration.planned_date or "-"
    deadline = declaration.sla_date or "-"
    return (
        f"Rappel Gesprec J-1 - Declaration {declaration.reference}\n"
        f"Atelier: {declaration.atelier}\n"
        f"Date planifiee: {planned}\n"
        f"Deadline: {deadline}\n"
        "La declaration est encore en attente de traitement. Merci de finaliser l'action dans les delais."
    )
