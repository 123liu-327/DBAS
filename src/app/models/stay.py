from datetime import date
from typing import Any, Self

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from app.models.base import CamelModel, utc_now


# 以下为待手写区域：StayInterval（现有实现为参考，实际改写后再标记为手写）
class StayInterval(CamelModel):
    join_date: date
    leave_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "StayInterval":
        if self.leave_date is not None and self.leave_date < self.join_date:
            raise ValueError("退宿日期不能早于入住日期")
        return self
# 待手写区域结束：StayInterval


# 以下为待手写区域：Stay（现有实现为参考，实际改写后再标记为手写）
class Stay(StayInterval):
    """One member's single stay in one book, keyed by (bookId, memberId)."""

    book_id: StrictInt = Field(gt=0)
    member_id: StrictInt = Field(gt=0)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="before")
    @classmethod
    def add_timestamps(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        created = data.get("createdAt", data.get("created_at"))
        updated = data.get("updatedAt", data.get("updated_at"))
        if created is None and updated is None:
            now = utc_now()
            data["created_at"] = now
            data["updated_at"] = now
        elif created is None or updated is None:
            raise ValueError("createdAt 和 updatedAt 必须同时提供")
        return data

    @model_validator(mode="after")
    def check_timestamps(self) -> "Stay":
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt 不能早于 createdAt")
        return self

    def with_updates(self, **changes: Any) -> Self:
        if {
            "book_id", "bookId", "member_id", "memberId",
            "created_at", "createdAt", "updated_at", "updatedAt",
        } & changes.keys():
            raise ValueError("不能直接修改入住记录标识和审计时间")
        values = self.model_dump(mode="python", by_alias=False)
        values.update(changes)
        values["updated_at"] = utc_now()
        return type(self).model_validate(values)
# 待手写区域结束：Stay
