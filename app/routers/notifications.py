from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import HSE_ROLES, get_current_user, parse_role
from app.constants import split_multi
from app.models import Audience, Declaration, Notification, Role, User
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Notification]:
    role = parse_role(user.role)
    if role in HSE_ROLES:
        stmt = select(Notification)
    elif role == Role.traitement:
        stmt = select(Notification).where(Notification.audience == Audience.all)
        allowed_ateliers = split_multi(user.responsible_ateliers)
        if not allowed_ateliers:
            return []
        if allowed_ateliers:
            stmt = stmt.join(Notification.declaration).where(Declaration.atelier.in_(allowed_ateliers))
    else:
        raise HTTPException(status_code=403, detail="Rôle non autorisé")
    return list(db.scalars(stmt.order_by(desc(Notification.created_at)).limit(200)))


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Notification:
    role = parse_role(user.role)
    if role not in HSE_ROLES and role != Role.traitement:
        raise HTTPException(status_code=403, detail="Rôle non autorisé")
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification
