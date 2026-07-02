from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import require_roles
from app.emailer import send_email, smtp_enabled
from app.models import Role, User

router = APIRouter(prefix="/system", tags=["system"])


class EmailTestIn(BaseModel):
    to_email: str = Field(min_length=3, max_length=255)


@router.get("/email-status")
def email_status(_: User = Depends(require_roles(Role.hse))) -> dict[str, bool]:
    return {"smtp_enabled": smtp_enabled()}


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
