"""Frontend response for a bill's receipt list."""

from app.models.attachment import Attachment
from app.schemas.common import PageData


class AttachmentPage(PageData[Attachment]):
    pass
