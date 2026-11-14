from datetime import datetime

from pydantic import BaseModel, Field, UUID4, field_validator


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Tên môn học không được để trống")
        return normalized


class SubjectUpdate(SubjectCreate):
    pass


class SubjectResponse(BaseModel):
    id: UUID4
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
