from enum import StrEnum

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from app.models.base import CamelModel, StoredModel


class SettlementStatus(StrEnum):
    LOCKED = "LOCKED"
    SETTLED = "SETTLED"


class MemberBalance(CamelModel):
    member_id: StrictInt = Field(gt=0)
    paid_cents: int = Field(ge=0)
    share_cents: int = Field(ge=0)
    net_cents: int

    @model_validator(mode="after")
    def check_net(self) -> "MemberBalance":
        if self.net_cents != self.paid_cents - self.share_cents:
            raise ValueError("净余额必须等于垫付金额减去分摊金额")
        return self


class Transfer(CamelModel):
    from_member_id: StrictInt = Field(gt=0)
    to_member_id: StrictInt = Field(gt=0)
    amount_cents: int = Field(gt=0)

    @model_validator(mode="after")
    def check_members(self) -> "Transfer":
        if self.from_member_id == self.to_member_id:
            raise ValueError("转账付款人与收款人不能相同")
        return self


class MemberConfirmation(CamelModel):
    member_id: StrictInt = Field(gt=0)
    confirmed_at: AwareDatetime | None = None


class SettlementSnapshot(StoredModel):
    book_id: int = Field(gt=0)
    start_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    bill_ids: list[str] = Field(min_length=1)
    balances: list[MemberBalance]
    transfers: list[Transfer]
    confirmations: list[MemberConfirmation]
    status: SettlementStatus = SettlementStatus.LOCKED

    @model_validator(mode="after")
    def check_snapshot(self) -> "SettlementSnapshot":
        if self.end_month < self.start_month:
            raise ValueError("结束月份不能早于开始月份")
        if len(self.bill_ids) != len(set(self.bill_ids)):
            raise ValueError("账单 ID 不能重复")
        member_ids = [item.member_id for item in self.confirmations]
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("成员确认记录不能重复")
        return self
