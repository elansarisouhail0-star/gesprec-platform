from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import require_roles
from app.config import get_settings
from app.emailer import send_email, smtp_enabled
from app.models import Role, User

router = APIRouter(prefix="/system", tags=["system"])


class EmailTestIn(BaseModel):
    to_email: str = Field(min_length=3, max_length=255)


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
