from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload
from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies import require_roles
from app.models import Category, Declaration, Gravity, Role, Status, User
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


TREATMENT_ATELIERS = {
    "traitement1@gesprec.local": "Atelier HITACHI",
    "traitement2@gesprec.local": "Atelier levage",
    "traitement3@gesprec.local": "Atelier Tour en fosse",
}


def treatment_atelier(user: User) -> str | None:
    return TREATMENT_ATELIERS.get(user.email.lower())


def count_by(db: Session, column, atelier: str | None = None) -> dict[str, int]:
    stmt = select(column, func.count()).select_from(Declaration)
    if atelier:
        stmt = stmt.where(Declaration.atelier == atelier)
    rows = db.execute(stmt.group_by(column)).all()
    return {(key.value if hasattr(key, "value") else str(key)): count for key, count in rows}


@router.get("/stats", response_model=DashboardStats)
def stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.hse, Role.chef_technicentre_tmlc, Role.coordination, Role.traitement, Role.chef_etablissement)),
) -> DashboardStats:
    atelier = treatment_atelier(user)
    base_count = select(func.count()).select_from(Declaration)
    open_stmt = select(func.count()).select_from(Declaration).where(Declaration.status != Status.cloture)
    critical_stmt = select(func.count()).select_from(Declaration).where(Declaration.real_gravity == Gravity.critique)
    latest_stmt = select(Declaration).options(selectinload(Declaration.photos), selectinload(Declaration.history))
    if atelier:
        base_count = base_count.where(Declaration.atelier == atelier)
        open_stmt = open_stmt.where(Declaration.atelier == atelier)
        critical_stmt = critical_stmt.where(Declaration.atelier == atelier)
        latest_stmt = latest_stmt.where(Declaration.atelier == atelier)
    total = db.scalar(base_count) or 0
    open_count = db.scalar(open_stmt) or 0
    critical = db.scalar(critical_stmt) or 0
    latest = list(
        db.scalars(
            latest_stmt.order_by(desc(Declaration.created_at)).limit(10)
        )
    )
    by_gravity = {g.value: 0 for g in Gravity} | count_by(db, Declaration.real_gravity, atelier)
    by_category = {c.value: 0 for c in Category} | count_by(db, Declaration.category, atelier)
    by_status = {s.value: 0 for s in Status} | count_by(db, Declaration.status, atelier)
    return DashboardStats(
        totals={"total": total, "open": open_count, "critical": critical, "closed": total - open_count},
        by_gravity=by_gravity,
        by_category=by_category,
        by_status=by_status,
        by_atelier=count_by(db, Declaration.atelier, atelier),
        latest=latest,
    )
