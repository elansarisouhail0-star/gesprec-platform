from collections import Counter

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload
from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies import require_roles
from app.constants import split_multi
from app.models import Category, Declaration, Gravity, Role, Status, User
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def empty_stats() -> DashboardStats:
    return DashboardStats(
        totals={"total": 0, "open": 0, "critical": 0, "closed": 0},
        by_gravity={g.value: 0 for g in Gravity},
        by_category={c.value: 0 for c in Category},
        by_status={s.value: 0 for s in Status},
        by_atelier={},
        latest=[],
    )


def treatment_ateliers(user: User) -> list[str]:
    if Role(user.role) != Role.traitement:
        return []
    return split_multi(user.responsible_ateliers)


def count_by(db: Session, column, ateliers: list[str] | None = None) -> dict[str, int]:
    stmt = select(column, func.count()).select_from(Declaration)
    if ateliers:
        stmt = stmt.where(Declaration.atelier.in_(ateliers))
    rows = db.execute(stmt.group_by(column)).all()
    return {(key.value if hasattr(key, "value") else str(key)): count for key, count in rows}


def assigned_to_treatment(user: User, declaration: Declaration) -> bool:
    assigned_ids = split_multi(declaration.assigned_responsible_ids)
    return not assigned_ids or str(user.id) in assigned_ids


def enum_value(value: object) -> str:
    return getattr(value, "value", value)


@router.get("/stats", response_model=DashboardStats)
def stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.hse, Role.chef_technicentre_tmlc, Role.coordination, Role.traitement, Role.chef_etablissement)),
) -> DashboardStats:
    ateliers = treatment_ateliers(user)
    if Role(user.role) == Role.traitement and not ateliers:
        return empty_stats()
    if Role(user.role) == Role.traitement:
        declarations = [
            declaration
            for declaration in db.scalars(
                select(Declaration)
                .where(Declaration.atelier.in_(ateliers))
                .options(selectinload(Declaration.photos), selectinload(Declaration.history))
                .order_by(desc(Declaration.created_at))
            )
            if assigned_to_treatment(user, declaration)
        ]
        total = len(declarations)
        open_count = len([d for d in declarations if enum_value(d.status) != Status.cloture.value])
        critical = len([d for d in declarations if enum_value(d.real_gravity) == Gravity.critique.value])
        by_gravity_counts = Counter(enum_value(d.real_gravity) for d in declarations)
        by_category_counts = Counter(enum_value(d.category) for d in declarations)
        by_status_counts = Counter(enum_value(d.status) for d in declarations)
        by_atelier_counts = Counter(d.atelier for d in declarations)
        return DashboardStats(
            totals={"total": total, "open": open_count, "critical": critical, "closed": total - open_count},
            by_gravity={g.value: by_gravity_counts.get(g.value, 0) for g in Gravity},
            by_category={c.value: by_category_counts.get(c.value, 0) for c in Category},
            by_status={s.value: by_status_counts.get(s.value, 0) for s in Status},
            by_atelier=dict(by_atelier_counts),
            latest=declarations[:10],
        )
    base_count = select(func.count()).select_from(Declaration)
    open_stmt = select(func.count()).select_from(Declaration).where(Declaration.status != Status.cloture)
    critical_stmt = select(func.count()).select_from(Declaration).where(Declaration.real_gravity == Gravity.critique)
    latest_stmt = select(Declaration).options(selectinload(Declaration.photos), selectinload(Declaration.history))
    if ateliers:
        base_count = base_count.where(Declaration.atelier.in_(ateliers))
        open_stmt = open_stmt.where(Declaration.atelier.in_(ateliers))
        critical_stmt = critical_stmt.where(Declaration.atelier.in_(ateliers))
        latest_stmt = latest_stmt.where(Declaration.atelier.in_(ateliers))
    total = db.scalar(base_count) or 0
    open_count = db.scalar(open_stmt) or 0
    critical = db.scalar(critical_stmt) or 0
    latest = list(
        db.scalars(
            latest_stmt.order_by(desc(Declaration.created_at)).limit(10)
        )
    )
    by_gravity = {g.value: 0 for g in Gravity} | count_by(db, Declaration.real_gravity, ateliers)
    by_category = {c.value: 0 for c in Category} | count_by(db, Declaration.category, ateliers)
    by_status = {s.value: 0 for s in Status} | count_by(db, Declaration.status, ateliers)
    return DashboardStats(
        totals={"total": total, "open": open_count, "critical": critical, "closed": total - open_count},
        by_gravity=by_gravity,
        by_category=by_category,
        by_status=by_status,
        by_atelier=count_by(db, Declaration.atelier, ateliers),
        latest=latest,
    )
