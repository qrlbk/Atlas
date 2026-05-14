from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.entities import User, UserRole


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"key": "errors.couldNotValidateCredentials"},
    )
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise credentials_exception from exc
    user_id = int(payload.get("sub", 0))
    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


def require_roles(*roles: UserRole):
    def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail={"key": "errors.insufficientPermissions"})
        return current_user

    return _guard


def enforce_school_scope(current_user: User, school_id: int | None) -> None:
    if current_user.role == UserRole.admin:
        return
    if school_id is None or current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail={"key": "errors.crossSchoolAccessDenied"})
