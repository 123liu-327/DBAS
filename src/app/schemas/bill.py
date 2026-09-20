from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import Field, StrictInt, model_validator

from app.models.base import CamelModel
from app.models.bill import Bill, BillPeriod, BillStatus, SplitMethod
from app.models.member import Member
from app.models.share import ShareDetail
from app.models.stay import Stay
from app.schemas.common import PageData


class BillFields(CamelModel):
    title: str | None = Field(default=None, max_length=20)
    category: str | None = None
    note: str | None = None
    amount_cents: StrictInt | None = None
    date: Date | None = None
    method: SplitMethod | None = None
    participants: list[StrictInt] = Field(default_factory=list)
    payer_id: StrictInt | None = None
    period: BillPeriod | None = None
    weights: dict[int, StrictInt] | None = None


class BillCreate(BillFields):
    status: Literal[BillStatus.DRAFT, BillStatus.POSTED] = BillStatus.POSTED


class BillPatch(CamelModel):
    title: str | None = Field(default=None, max_length=20)
    category: str | None = None
    note: str | None = None
    amount_cents: StrictInt | None = None
    date: Date | None = None
    method: SplitMethod | None = None
    participants: list[StrictInt] | None = None
    payer_id: StrictInt | None = None
    period: BillPeriod | None = None
    weights: dict[int, StrictInt] | None = None
    status: Literal[BillStatus.DRAFT, BillStatus.POSTED] | None = None

    @model_validator(mode="after")
    def check_patch(self) -> "BillPatch":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个要修改的字段")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("账单状态不能为 null")
        return self


class BillItem(CamelModel):
    id: str
    book_id: StrictInt
    title: str | None
    amount_cents: int | None
    date: Date | None
    method: SplitMethod | None
    status: BillStatus
    payer_id: int | None
    payer_name: str | None
    participant_count: int
    attachment_count: int
    created_at: datetime
    updated_at: datetime


class BillPage(PageData[BillItem]):
    pass


class BillShareItem(ShareDetail):
    member: Member
    stay: Stay


class BillParticipant(CamelModel):
    member: Member
    stay: Stay


class BillDetail(CamelModel):
    bill: Bill
    payer: Member | None
    participants: list[BillParticipant]
    shares: list[BillShareItem]


class BillPreview(CamelModel):
    total_cents: int
    payer: Member
    participants: list[BillParticipant]
    shares: list[BillShareItem]


class MemberShare(CamelModel):
    member_id: int
    share_cents: int


class MonthlyShares(CamelModel):
    month: str
    shares: list[MemberShare]
