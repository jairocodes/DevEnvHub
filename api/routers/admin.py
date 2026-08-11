from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from api.core.deps import DbSession, get_current_admin_user
from api.models.user import User
from api.schemas.user import AdminUserOut, QuotaUpdate

router = APIRouter(prefix="/admin", tags=["admin"])

RequireAdmin = Annotated[User, Depends(get_current_admin_user)]


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: DbSession, _admin: RequireAdmin) -> list[User]:
    return list(db.scalars(select(User)))


@router.patch("/users/{user_id}/quota", response_model=AdminUserOut)
def update_user_quota(
    user_id: int, payload: QuotaUpdate, db: DbSession, _admin: RequireAdmin
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user
