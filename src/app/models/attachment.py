from pydantic import Field

from app.models.base import StoredModel


class Attachment(StoredModel):
    bill_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
