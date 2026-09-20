from datetime import date

from pydantic import StrictInt, model_validator

from app.models.base import CamelModel
from app.models.member import Member
from app.models.stay import Stay, StayInterval
from app.schemas.common import PageData


class StayCreate(StayInterval):
    member_id: StrictInt

    @model_validator(mode="after")
    def check_member_id(self) -> "StayCreate":
        if self.member_id <= 0:
            raise ValueError("成员 ID 必须为正整数")
        return self


class StayPatch(CamelModel):
    join_date: date | None = None
    leave_date: date | None = None

    @model_validator(mode="after")
    def check_patch(self) -> "StayPatch":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个要修改的字段")
        if "join_date" in self.model_fields_set and self.join_date is None:
            raise ValueError("入住日期不能为 null")
        if (
            self.join_date is not None
            and self.leave_date is not None
            and self.leave_date < self.join_date
        ):
            raise ValueError("退宿日期不能早于入住日期")
        return self


class StayItem(Stay):
    member: Member
    bill_count: int = 0
    paid_bill_count: int = 0


class StayPage(PageData[StayItem]):
    pass


class StayDetail(CamelModel):
    stay: Stay
    member: Member
    bill_count: int
    paid_bill_count: int
