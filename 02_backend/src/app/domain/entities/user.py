from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime


class UserTokenEntity(BaseModel):
    access: str
    refresh: str


class UserLoginResponse(BaseModel):
    user: UserEntity
    token: UserTokenEntity


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserRefreshTokenRequest(BaseModel):
    refresh_token: str
