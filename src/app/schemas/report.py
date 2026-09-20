from pydantic import Field, model_validator

from app.models.base import CamelModel
from app.models.settlement import MemberBalance, Transfer

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class SettlementRange(CamelModel):
    start_month: str = Field(pattern=MONTH_PATTERN)
    end_month: str = Field(pattern=MONTH_PATTERN)

    @model_validator(mode="after")
    def check_range(self) -> "SettlementRange":
        if self.start_month > self.end_month:
            raise ValueError("startMonth cannot be later than endMonth")
        return self


class SettlementPlan(SettlementRange):
    balances: list[MemberBalance]
    net_sum_cents: int
    balanced: bool
    transfers: list[Transfer]


class MonthlyTrend(CamelModel):
    month: str
    total_cents: int = Field(ge=0)
    per_capita_cents: int = Field(ge=0)
