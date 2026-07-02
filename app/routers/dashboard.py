from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload
from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies import require_roles
from app.models import Category, Declaration, Gravity, Role, Status, User
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def count_by(db: Session, column) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).select_from(Declaration).group_by(column)).all()
    return {(key.value if hasattr(key, "value") else str(key)): count for key, count in rows}


@router.get("/stats", response_model=DashboardStats)
def stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.hse, Role.chef_technicentre_tmlc, Role.coordination, Role.traitement, Role.chef_etablissement)),
) -> DashboardStats:
    total = db.scalar(select(func.count()).select_from(Declaration)) or 0
    open_count = db.scalar(select(func.count()).select_from(Declaration).where(Declaration.status != Status.cloture)) or 0
    critical = db.scalar(select(func.count()).select_from(Declaration).where(Declaration.real_gravity == Gravity.critique)) or 0
    latest = list(
        db.scalars(
            select(Declaration)
            .options(selectinload(Declaration.photos), selectinload(Declaration.history))
            .order_by(desc(Declaration.created_at))
            .limit(10)
        )
    )
    by_gravity = {g.value: 0 for g in Gravity} | count_by(db, Declaration.real_gravity)
    by_category = {c.value: 0 for c in Category} | count_by(db, Declaration.category)
    by_status = {s.value: 0 for s in Status} | count_by(db, Declaration.status)
    return DashboardStats(
        totals={"total": total, "open": open_count, "critical": critical, "closed": total - open_count},
        by_gravity=by_gravity,
        by_category=by_category,
        by_status=by_status,
        by_atelier=count_by(db, Declaration.atelier),
        latest=latest,
    )
