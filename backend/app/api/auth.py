from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import create_access_token, verify_password
from app.models.entities import User
from app.schemas.auth import LoginInput, MeOut, Token


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginInput, db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"key": "errors.invalidCredentials"})

    token = create_access_token(subject=str(user.id), role=user.role.value, school_id=user.school_id)
    return Token(access_token=token)


@router.get("/me", response_model=MeOut)
def me(current_user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        school_id=current_user.school_id,
    )
