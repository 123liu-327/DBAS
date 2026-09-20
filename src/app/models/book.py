from pydantic import Field, StrictInt

from app.models.base import StoredModel


class Book(StoredModel):
    """A book is a collection of bills and members."""
    id: StrictInt = Field(gt=0)
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)

    @property
    def last_active_at(self):
        return self.updated_at
