from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import ATELIERS
from app.models import Role, User
from app.security import hash_password


DEFAULT_USERS = [
    ("qsse@gesprec.local", "Responsable QSSE", Role.hse, "Qsse2026!", "", ""),
    ("chef@gesprec.local", "Chef de technicentre TMLC", Role.chef_technicentre_tmlc, "Chef12345!", "", ""),
    ("etablissement@gesprec.local", "Chef d'établissement", Role.chef_etablissement, "Etab12345!", "", ""),
    ("coordination@gesprec.local", "Responsable Coordination", Role.coordination, "Coord12345!", "", ""),
    ("traitement@gesprec.local", "Responsable Traitement principal", Role.traitement, "Trait12345!", ", ".join(ATELIERS), ""),
    ("traitement1@gesprec.local", "Responsable Traitement HITACHI", Role.traitement, "Trait112345!", "HITACHI Remise, HITACHI VA", ""),
    ("traitement2@gesprec.local", "Responsable Traitement DIESEL", Role.traitement, "Trait212345!", "DIESEL, POSTE GASOIL, MAGASIN DIESEL", ""),
    ("traitement3@gesprec.local", "Responsable Traitement TOUR EN FOSSE", Role.traitement, "Trait312345!", "TOUR EN FOSSE", ""),
]


def seed_default_users(db: Session) -> None:
    with db.no_autoflush:
        old_hse = db.scalar(select(User).where(User.email == "hse@gesprec.local"))
        qsse_user = db.scalar(select(User).where(User.email == "qsse@gesprec.local"))
        role_hse = db.scalar(select(User).where(User.role == Role.hse))
        target_hse = qsse_user or old_hse or role_hse
        if target_hse:
            target_hse.email = "qsse@gesprec.local"
            target_hse.full_name = "Responsable QSSE"
            target_hse.role = Role.hse
            target_hse.is_active = True
            target_hse.hashed_password = hash_password("Qsse2026!")
        if old_hse and target_hse and old_hse.id != target_hse.id:
            old_hse.is_active = False

        for old_user in db.scalars(select(User).where(User.role == "chef_centre")):
            old_user.role = Role.chef_technicentre_tmlc
            if old_user.full_name == "Chef de centre":
                old_user.full_name = "Chef de technicentre TMLC"

        for old_declarant in db.scalars(select(User).where(User.role == "declarant")):
            old_declarant.is_active = False

        for email, full_name, role, password, responsible_ateliers, phone_numbers in DEFAULT_USERS:
            exists = db.scalar(select(User).where(User.email == email))
            if not exists and email == "qsse@gesprec.local":
                exists = target_hse
            if exists:
                exists.role = role
                exists.full_name = full_name
                exists.is_active = True
                if responsible_ateliers and not exists.responsible_ateliers:
                    exists.responsible_ateliers = responsible_ateliers
                if phone_numbers and not exists.phone_numbers:
                    exists.phone_numbers = phone_numbers
                if email == "qsse@gesprec.local":
                    exists.hashed_password = hash_password(password)
                continue
            db.add(
                User(
                    email=email,
                    full_name=full_name,
                    role=role,
                    hashed_password=hash_password(password),
                    responsible_ateliers=responsible_ateliers,
                    phone_numbers=phone_numbers,
                )
            )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
