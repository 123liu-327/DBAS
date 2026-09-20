from pydantic import Field, StrictInt

from app.models.base import StoredModel


class Member(StoredModel):
    """A global fee participant profile. Authentication is intentionally out of scope."""

    id: StrictInt = Field(gt=0)
    name: str = Field(min_length=1, max_length=10)
