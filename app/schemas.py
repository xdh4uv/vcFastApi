from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .country_codes import DIAL_CODES


GenderLiteral = Literal["Female", "Male", "Nonbinary", "Prefer not to say", "Other"]


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoogleLoginIn(BaseModel):
    credential: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int


def _validate_dob(v: date) -> date:
    today = date.today()
    if v > today:
        raise ValueError("date_of_birth cannot be in the future")
    if (today.year - v.year) > 120:
        raise ValueError("date_of_birth too far in the past")
    return v


def _validate_dial_code(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in DIAL_CODES:
        raise ValueError("phone_country_code not in known list")
    return v


class OnboardingIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=128)
    date_of_birth: date
    gender: GenderLiteral
    bio: Optional[str] = Field(default=None, max_length=500)
    phone_country_code: Optional[str] = Field(default=None, max_length=8)
    phone_number: Optional[str] = Field(default=None, max_length=32)

    @field_validator("date_of_birth")
    @classmethod
    def dob_sane(cls, v: date) -> date:
        return _validate_dob(v)

    @field_validator("phone_country_code")
    @classmethod
    def dial_code_known(cls, v: Optional[str]) -> Optional[str]:
        return _validate_dial_code(v)

    @model_validator(mode="after")
    def phone_pair_complete(self) -> "OnboardingIn":
        if bool(self.phone_country_code) != bool(self.phone_number):
            raise ValueError("phone_country_code and phone_number must be set together")
        return self


class ProfileUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=64)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    date_of_birth: Optional[date] = None
    gender: Optional[GenderLiteral] = None
    bio: Optional[str] = Field(default=None, max_length=500)
    phone_country_code: Optional[str] = Field(default=None, max_length=8)
    phone_number: Optional[str] = Field(default=None, max_length=32)

    @field_validator("date_of_birth")
    @classmethod
    def dob_sane(cls, v: Optional[date]) -> Optional[date]:
        return _validate_dob(v) if v is not None else v

    @field_validator("phone_country_code")
    @classmethod
    def dial_code_known(cls, v: Optional[str]) -> Optional[str]:
        return _validate_dial_code(v)


class ProfileOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: Optional[str]
    date_of_birth: Optional[date]
    age: Optional[int]
    gender: Optional[GenderLiteral]
    bio: Optional[str]
    phone_country_code: Optional[str]
    phone_number: Optional[str]
    avatar_url: Optional[str]
    initials: str
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
