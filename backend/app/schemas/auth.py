from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str
    school_id: int | None = None


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class MeOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    school_id: int | None = None
