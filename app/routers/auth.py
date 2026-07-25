from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import Declaration, DeclarationCollaborator, HistoryEvent, Role, User
from app.schemas import PasswordChange, Token, UserCreate, UserOut, UserUpdate
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe invalide")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Utilisateur inactif")
    try:
        Role(user.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rôle obsolète ou non autorisé")
    return Token(access_token=create_access_token(str(user.id)), user=UserOut.model_validate(user))


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.hse, Role.traitement)),
) -> User:
    requested_role = Role(payload.role)
    if Role(current_user.role) == Role.traitement and requested_role != Role.collaborateur:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Le responsable traitement ne peut creer que des collaborateurs")
    if Role(current_user.role) == Role.hse and requested_role == Role.collaborateur:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Les collaborateurs doivent etre crees par le responsable traitement")
    exists = db.scalar(select(User).where(User.email == payload.email))
    if exists:
        raise HTTPException(status_code=409, detail="Email deja utilise")
    manager_id = current_user.id if Role(current_user.role) == Role.traitement else payload.manager_id
    responsible_ateliers = payload.responsible_ateliers
    if Role(current_user.role) == Role.traitement and not responsible_ateliers:
        responsible_ateliers = current_user.responsible_ateliers
    user = User(
        email=str(payload.email),
        full_name=payload.full_name,
        role=requested_role,
        hashed_password=hash_password(payload.password),
        responsible_ateliers=responsible_ateliers,
        phone_numbers=payload.phone_numbers,
        manager_id=manager_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.hse, Role.chef_technicentre_tmlc, Role.coordination, Role.traitement)),
) -> list[User]:
    if Role(current_user.role) == Role.traitement:
        return list(
            db.scalars(
                select(User)
                .where(User.role == Role.collaborateur, User.manager_id == current_user.id)
                .order_by(User.full_name)
            )
        )
    return list(db.scalars(select(User).where(User.role != Role.collaborateur).order_by(User.role, User.full_name)))


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.hse, Role.traitement)),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if Role(current_user.role) == Role.traitement:
        if Role(user.role) != Role.collaborateur or user.manager_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Collaborateur non rattache a ce responsable traitement")
        if payload.role is not None and Role(payload.role) != Role.collaborateur:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role non autorise")
    if payload.email and payload.email != user.email:
        exists = db.scalar(select(User).where(User.email == payload.email))
        if exists:
            raise HTTPException(status_code=409, detail="Email deja utilise")
        user.email = payload.email
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = Role(payload.role)
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.responsible_ateliers is not None:
        user.responsible_ateliers = payload.responsible_ateliers
    if payload.phone_numbers is not None:
        user.phone_numbers = payload.phone_numbers
    if Role(current_user.role) == Role.hse and payload.manager_id is not None:
        user.manager_id = payload.manager_id
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.hse, Role.traitement)),
) -> None:
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vous ne pouvez pas supprimer votre propre compte")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if Role(current_user.role) == Role.traitement:
        if Role(user.role) != Role.collaborateur or user.manager_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Collaborateur non rattache a ce responsable traitement")

    for collaborator in db.scalars(select(User).where(User.manager_id == user_id)):
        collaborator.manager_id = None
    for field in (
        Declaration.created_by_id,
        Declaration.analyzed_by_id,
        Declaration.assigned_by_id,
        Declaration.planned_by_id,
        Declaration.intervention_by_id,
        Declaration.closed_by_id,
    ):
        for declaration in db.scalars(select(Declaration).where(field == user_id)):
            setattr(declaration, field.key, None)
    for event in db.scalars(select(HistoryEvent).where(HistoryEvent.actor_id == user_id)):
        event.actor_id = None
    for assignment in db.scalars(select(DeclarationCollaborator).where(DeclarationCollaborator.user_id == user_id)):
        db.delete(assignment)

    db.delete(user)
    db.commit()


@router.post("/change-password", response_model=UserOut)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.hse, Role.chef_technicentre_tmlc, Role.coordination, Role.traitement, Role.chef_etablissement, Role.collaborateur)),
) -> User:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe actuel incorrect")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return user
