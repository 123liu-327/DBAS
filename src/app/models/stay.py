from datetime import date
from typing import Any, Self

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from app.models.base import CamelModel, utc_now


class StayInterval(CamelModel):
    join_date: date
    leave_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "StayInterval":
        if self.leave_date is not None and self.leave_date < self.join_date:
            raise ValueError("leaveDate cannot be earlier than joinDate")
        return self


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
            raise ValueError("createdAt and updatedAt must be supplied together")
        return data

    @model_validator(mode="after")
    def check_timestamps(self) -> "Stay":
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt cannot be earlier than createdAt")
        return self

    def with_updates(self, **changes: Any) -> Self:
        if {
            "book_id", "bookId", "member_id", "memberId",
            "created_at", "createdAt", "updated_at", "updatedAt",
        } & changes.keys():
            raise ValueError("Stay identity and audit timestamps cannot be edited directly")
        values = self.model_dump(mode="python", by_alias=False)
        values.update(changes)
        values["updated_at"] = utc_now()
        return type(self).model_validate(values)
