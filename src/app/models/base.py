from datetime import UTC, datetime
from typing import Any, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


def utc_now() -> datetime:
    return datetime.now(UTC)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class StoredModel(CamelModel):
    id: str = Field(min_length=1)
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
    def check_timestamps(self) -> "StoredModel":
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt 不能早于 createdAt")
        return self

    def with_updates(self, **changes: Any) -> Self:
        """Validate a modified record while preserving its ID and creation time."""
        if {"id", "created_at", "createdAt", "updated_at", "updatedAt"} & changes.keys():
            raise ValueError("不能直接修改 ID 和审计时间")
        values = self.model_dump(mode="python", by_alias=False)
        values.update(changes)
        values["updated_at"] = utc_now()
        return type(self).model_validate(values)
