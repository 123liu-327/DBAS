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
            raise ValueError("period.end cannot be earlier than period.start")
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
            raise ValueError("participants cannot contain duplicates")
        if any(member_id <= 0 for member_id in self.participants):
            raise ValueError("participant IDs must be positive")
        if self.amount_cents is not None and self.amount_cents <= 0:
            raise ValueError("amountCents must be positive")
        if (
            self.payer_id is not None
            and self.participants
            and self.payer_id not in self.participants
        ):
            raise ValueError("payerId must belong to participants")
        if self.weights is not None and any(weight <= 0 for weight in self.weights.values()):
            raise ValueError("weights must be positive integers")

        if self.status != BillStatus.DRAFT:
            if not self.title or not self.title.strip():
                raise ValueError("title is required for a posted bill")
            if self.amount_cents is None or self.date is None or self.method is None:
                raise ValueError("amountCents, date and method are required for a posted bill")
            if not self.participants or self.payer_id not in self.participants:
                raise ValueError("participants and payerId are required for a posted bill")
            if self.method == SplitMethod.BY_DAYS and self.period is None:
                raise ValueError("period is required for BY_DAYS")
            if self.method == SplitMethod.BY_WEIGHT:
                if self.weights is None or set(self.weights) != set(self.participants):
                    raise ValueError("weights must cover each participant exactly once")
        return self
