from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Audience, Declaration, HistoryEvent, Notification, User


def next_reference(db: Session) -> str:
    year = datetime.now().year
    prefix = f"PRC-{year}-"
    count = db.scalar(select(func.count()).select_from(Declaration).where(Declaration.reference.like(f"{prefix}%"))) or 0
    return f"{prefix}{count + 1:04d}"


def add_history(db: Session, declaration: Declaration, action: str, actor: User | None = None) -> None:
    db.add(HistoryEvent(declaration_id=declaration.id, action=action, actor_id=actor.id if actor else None))


def add_notification(
    db: Session,
    declaration: Declaration,
    message: str,
    audience: Audience = Audience.admin,
) -> None:
    db.add(Notification(declaration_id=declaration.id, message=message, audience=audience))
