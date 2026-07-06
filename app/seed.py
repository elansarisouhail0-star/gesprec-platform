from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security import hash_password


DEFAULT_USERS = [
    ("hse@gesprec.local", "Responsable HSE", Role.hse, "Hse12345!"),
    ("chef@gesprec.local", "Chef de technicentre TMLC", Role.chef_technicentre_tmlc, "Chef12345!"),
    ("etablissement@gesprec.local", "Chef d'établissement", Role.chef_etablissement, "Etab12345!"),
    ("coordination@gesprec.local", "Responsable Coordination", Role.coordination, "Coord12345!"),
    ("traitement@gesprec.local", "Responsable Traitement principal", Role.traitement, "Trait12345!"),
    ("traitement1@gesprec.local", "Responsable Traitement 1", Role.traitement, "Trait112345!"),
    ("traitement2@gesprec.local", "Responsable Traitement 2", Role.traitement, "Trait212345!"),
    ("traitement3@gesprec.local", "Responsable Traitement 3", Role.traitement, "Trait312345!"),
]


def seed_default_users(db: Session) -> None:
    for old_user in db.scalars(select(User).where(User.role == "chef_centre")):
        old_user.role = Role.chef_technicentre_tmlc
        if old_user.full_name == "Chef de centre":
            old_user.full_name = "Chef de technicentre TMLC"

    for old_declarant in db.scalars(select(User).where(User.role == "declarant")):
        old_declarant.is_active = False

    for email, full_name, role, password in DEFAULT_USERS:
        exists = db.scalar(select(User).where(User.email == email))
        if exists:
            exists.role = role
            exists.full_name = full_name
            exists.is_active = True
            exists.hashed_password = hash_password(password)
            continue
        db.add(
            User(
                email=email,
                full_name=full_name,
                role=role,
                hashed_password=hash_password(password),
            )
        )
    db.commit()
