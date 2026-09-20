from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.models.base import CamelModel
from app.models.member import Member
from app.models.stay import Stay
from app.schemas.common import PageData

MemberName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]


class MemberCreate(CamelModel):
    name: MemberName


class MemberPatch(CamelModel):
    name: MemberName | None = None

    @model_validator(mode="after")
    def check_patch(self) -> "MemberPatch":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if self.name is None:
            raise ValueError("name cannot be null")
        return self


class MemberItem(Member):
    stay_count: int = Field(ge=0)
    bill_count: int = Field(ge=0)


class MemberPage(PageData[MemberItem]):
    pass


class MemberDetail(CamelModel):
    member: Member
    stays: list[Stay]
    stay_count: int = Field(ge=0)
    bill_count: int = Field(ge=0)
    paid_bill_count: int = Field(ge=0)
