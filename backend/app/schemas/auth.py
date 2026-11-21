import re
from datetime import datetime

from pydantic import BaseModel, Field, UUID4, field_validator


class CredentialsRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Email không hợp lệ")
        return normalized


class GoogleCredentialRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)


class UserResponse(BaseModel):
    id: UUID4
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}
