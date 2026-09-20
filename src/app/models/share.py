from pydantic import Field, StrictInt

from app.models.base import CamelModel


class ShareDetail(CamelModel):
    bill_id: str = Field(min_length=1)
    member_id: StrictInt = Field(gt=0)
    share_cents: int = Field(ge=0)
    effective_days: int | None = Field(default=None, ge=0)
    weight: int | None = Field(default=None, gt=0)
