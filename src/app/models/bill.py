from datetime import date as Date
from enum import StrEnum

from pydantic import Field, StrictInt, model_validator

from app.models.attachment import Attachment
from app.models.base import CamelModel, StoredModel


class SplitMethod(StrEnum):
    EVEN = "EVEN"
    BY_DAYS = "BY_DAYS"
    BY_WEIGHT = "BY_WEIGHT"


class BillStatus(StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    LOCKED = "LOCKED"
    SETTLED = "SETTLED"


class BillPeriod(CamelModel):
    start: Date
    end: Date

    @model_validator(mode="after")
    def check_dates(self) -> "BillPeriod":
        if self.end < self.start:
            raise ValueError("分摊周期结束日期不能早于开始日期")
        return self


class Bill(StoredModel):
    book_id: StrictInt = Field(gt=0)
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
    status: BillStatus = BillStatus.DRAFT
    attachments: list[Attachment] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def check_bill(self) -> "Bill":
        if len(self.participants) != len(set(self.participants)):
            raise ValueError("参与人不能重复")
        if any(member_id <= 0 for member_id in self.participants):
            raise ValueError("参与人 ID 必须为正整数")
        if self.amount_cents is not None and self.amount_cents <= 0:
            raise ValueError("账单金额必须为正整数分")
        if (
            self.payer_id is not None
            and self.participants
            and self.payer_id not in self.participants
        ):
            raise ValueError("垫付人必须属于参与人")
        if self.weights is not None and any(weight <= 0 for weight in self.weights.values()):
            raise ValueError("所有权重必须为正整数")

        if self.status != BillStatus.DRAFT:
            if not self.title or not self.title.strip():
                raise ValueError("已入账账单必须填写名称")
            if self.amount_cents is None or self.date is None or self.method is None:
                raise ValueError("已入账账单必须填写金额、记账日期和分摊方式")
            if not self.participants or self.payer_id not in self.participants:
                raise ValueError("已入账账单必须包含参与人和垫付人")
            if self.method == SplitMethod.BY_DAYS and self.period is None:
                raise ValueError("按天分摊必须提供分摊周期")
            if self.method == SplitMethod.BY_WEIGHT:
                if self.weights is None or set(self.weights) != set(self.participants):
                    raise ValueError("按权重分摊必须为每位参与人提供且只提供一个权重")
        return self
