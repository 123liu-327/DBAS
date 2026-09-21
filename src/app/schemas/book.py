from datetime import datetime
from typing import Annotated

from pydantic import Field, StrictInt, StringConstraints, model_validator

from app.models.base import CamelModel
from app.schemas.common import PageData
from app.schemas.stay import StayItem

BookName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
BookDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class BookCreate(CamelModel):
    name: BookName
    description: BookDescription | None = None


class BookPatch(CamelModel):
    name: BookName | None = None
    description: BookDescription | None = None

    @model_validator(mode="after")
    def check_patch(self) -> "BookPatch":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个要修改的字段")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("账本名称不能为 null")
        return self


class BookItem(CamelModel):
    id: StrictInt
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime
    member_count: int = Field(ge=0)
    bill_count: int = Field(ge=0)


class BookPage(PageData[BookItem]):
    pass


class BookBillCounts(CamelModel):
    draft: int = Field(ge=0)
    posted: int = Field(ge=0)
    locked: int = Field(ge=0)
    settled: int = Field(ge=0)


# 以下为待手写区域：BookDetail（现有实现为参考，实际改写后再标记为手写）
class BookDetail(CamelModel):
    book: BookItem
    stays: list[StayItem]
    bill_status_counts: BookBillCounts
# 待手写区域结束：BookDetail
