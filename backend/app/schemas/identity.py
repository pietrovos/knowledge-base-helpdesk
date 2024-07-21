from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GroupRef(ORM):
    id: int
    name: str


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: Role
    is_active: bool
    groups: list[GroupRef] = []


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    role: Role = Role.agent


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class UserRef(ORM):
    id: int
    name: str
    email: str


class GroupOut(ORM):
    id: int
    name: str
    description: str
    members: list[UserRef] = []


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""


class MemberIn(BaseModel):
    user_id: int


class CollectionOut(ORM):
    id: int
    name: str
    description: str
    created_at: datetime
    document_count: int = 0


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""


class GrantIn(BaseModel):
    user_id: int | None = None
    group_id: int | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> "GrantIn":
        if (self.user_id is None) == (self.group_id is None):
            raise ValueError("Provide exactly one of user_id or group_id")
        return self


class GrantOut(ORM):
    id: int
    collection_id: int
    user: UserRef | None
    group: GroupRef | None
    created_at: datetime
