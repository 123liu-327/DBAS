from typing import Annotated

from fastapi import APIRouter, File, Path, Response, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import StoreDep
from app.api.pagination import PageDep
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.core.responses import ApiResponse, ok
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentPage
from app.services import attachment_service

router = APIRouter(prefix="/books/{bookId}/bills/{billId}/attachments", tags=["附件"])
BookId = Annotated[int, Path(alias="bookId", gt=0)]
BillId = Annotated[str, Path(alias="billId")]
AttachmentId = Annotated[str, Path(alias="attachmentId")]


@router.post("", response_model=ApiResponse[Attachment], status_code=201)
async def upload_attachment(
    book_id: BookId, bill_id: BillId, store: StoreDep,
    file: Annotated[UploadFile, File()],
) -> ApiResponse[Attachment]:
    contents = await file.read(attachment_service.MAX_BYTES + 1)
    if len(contents) > attachment_service.MAX_BYTES:
        raise AppError("INVALID_ATTACHMENT", "附件大小必须在 10 MiB 以内", status_code=422,
                       field="file")
    attachment = await run_in_threadpool(
        attachment_service.add_attachment,
        store, book_id, bill_id, file_name=file.filename or "",
        content_type=file.content_type or "", contents=contents,
    )
    return ok(attachment, message="附件上传成功", code=201)


@router.get("", response_model=ApiResponse[AttachmentPage])
def list_attachments(
    book_id: BookId, bill_id: BillId, store: StoreDep,
    params: PageDep,
) -> ApiResponse[AttachmentPage]:
    page = paginate(attachment_service.list_attachments(store, book_id, bill_id),
                    params.page, params.page_size)
    return ok(AttachmentPage.model_validate(page.model_dump()))


@router.get("/{attachmentId}")
def download_attachment(
    book_id: BookId, bill_id: BillId, attachment_id: AttachmentId, store: StoreDep
) -> FileResponse:
    attachment, path = attachment_service.download_path(store, book_id, bill_id, attachment_id)
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.file_name)


@router.delete("/{attachmentId}", status_code=204)
def delete_attachment(
    book_id: BookId, bill_id: BillId, attachment_id: AttachmentId, store: StoreDep
) -> Response:
    attachment_service.delete_attachment(store, book_id, bill_id, attachment_id)
    return Response(status_code=204)
