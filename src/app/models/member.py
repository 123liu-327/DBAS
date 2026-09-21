from pydantic import Field, StrictInt

from app.models.base import StoredModel


# 以下为待手写区域：Member（现有实现为参考，实际改写后再标记为手写）
class Member(StoredModel):
    """A global fee participant profile. Authentication is intentionally out of scope."""

    id: StrictInt = Field(gt=0)
    name: str = Field(min_length=1, max_length=10)
# 待手写区域结束：Member
