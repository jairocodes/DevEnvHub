from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_admin: bool
    max_environments: int | None
    cpu_limit: float | None
    mem_limit_mb: int | None
    created_at: datetime


class QuotaUpdate(BaseModel):
    max_environments: int | None = None
    cpu_limit: float | None = None
    mem_limit_mb: int | None = None
