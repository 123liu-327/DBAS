"""账单附件业务服务：校验文件并维护账单元数据与账本内实际文件。"""

from pathlib import Path
from uuid import uuid4

from app.core.exceptions import AppError
from app.crud import bills as bill_crud
from app.crud.books import touch_book
from app.models.attachment import Attachment
from app.models.bill import BillStatus
from app.storage import FileStore

MAX_BYTES = 10 * 1024 * 1024
MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".pdf": "application/pdf",
}


def _valid_signature(extension: str, contents: bytes) -> bool:
    """根据文件头校验真实格式，防止只修改扩展名绕过限制。"""
    if extension == ".png":
        return contents.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return contents.startswith(b"\xff\xd8\xff")
    if extension == ".webp":
        return contents.startswith(b"RIFF") and contents[8:12] == b"WEBP"
    return contents.startswith(b"%PDF-")


def add_attachment(
    store: FileStore, book_id: int, bill_id: str, *, file_name: str,
    content_type: str, contents: bytes,
) -> Attachment:
    """校验并保存附件；任一元数据写入失败时回滚已写入文件。"""

    bill_crud.require_bill(store, book_id, bill_id)
    safe_name = Path(file_name.replace("\\", "/")).name
    extension = Path(safe_name).suffix.lower()
    if not safe_name or extension not in MEDIA_TYPES or MEDIA_TYPES[extension] != content_type:
        raise AppError("INVALID_ATTACHMENT", "仅支持 PNG、JPEG、WebP 和 PDF", status_code=422,
                       field="file")
    if not _valid_signature(extension, contents):
        raise AppError("INVALID_ATTACHMENT", "文件内容与格式不符", status_code=422,
                       field="file")
    if not contents or len(contents) > MAX_BYTES:
        raise AppError("INVALID_ATTACHMENT", "附件大小必须在 10 MiB 以内", status_code=422,
                       field="file")

    with store.book_lock(book_id):
        bill = bill_crud.require_bill(store, book_id, bill_id)
        if bill.status in {BillStatus.LOCKED, BillStatus.SETTLED}:
            raise AppError("BILL_LOCKED", "锁定或结清账单不能添加附件", status_code=409)
        if len(bill.attachments) >= 3:
            raise AppError("ATTACHMENT_LIMIT", "每笔账单最多 3 个附件", status_code=409)
        attachment_id = f"att_{uuid4().hex}"
        relative_path = f"attachments/{bill_id}/{attachment_id}{extension}"
        attachment = Attachment(
            id=attachment_id, bill_id=bill_id, file_name=safe_name,
            content_type=content_type, relative_path=relative_path, size_bytes=len(contents),
        )
        target = store.write_attachment(book_id, relative_path, contents)
        try:
            bill_crud.replace_bill(
                store, bill.with_updates(attachments=[*bill.attachments, attachment])
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        touch_book(store, book_id)
        return attachment


def list_attachments(store: FileStore, book_id: int, bill_id: str) -> list[Attachment]:
    """读取账单中保存的附件元数据列表。"""
    return bill_crud.require_bill(store, book_id, bill_id).attachments


def require_attachment(
    store: FileStore, book_id: int, bill_id: str, attachment_id: str
) -> Attachment:
    """按附件 ID 查找元数据，不存在时返回统一的 404 业务错误。"""
    for attachment in list_attachments(store, book_id, bill_id):
        if attachment.id == attachment_id:
            return attachment
    raise AppError("ATTACHMENT_NOT_FOUND", "附件不存在", status_code=404,
                   field="attachmentId")


def download_path(
    store: FileStore, book_id: int, bill_id: str, attachment_id: str
) -> tuple[Attachment, Path]:
    """同时校验附件元数据和实际文件，返回安全下载路径。"""
    attachment = require_attachment(store, book_id, bill_id, attachment_id)
    path = store.attachment_path(book_id, attachment.relative_path)
    if not path.is_file():
        raise AppError("ATTACHMENT_NOT_FOUND", "附件文件不存在", status_code=404,
                       field="attachmentId")
    return attachment, path


def delete_attachment(store: FileStore, book_id: int, bill_id: str, attachment_id: str) -> None:
    """先更新账单元数据，再删除对应文件；锁定和结清账单不可操作。"""
    with store.book_lock(book_id):
        bill = bill_crud.require_bill(store, book_id, bill_id)
        if bill.status in {BillStatus.LOCKED, BillStatus.SETTLED}:
            raise AppError("BILL_LOCKED", "锁定或结清账单不能删除附件", status_code=409)
        attachment = require_attachment(store, book_id, bill_id, attachment_id)
        remaining = [item for item in bill.attachments if item.id != attachment_id]
        bill_crud.replace_bill(store, bill.with_updates(attachments=remaining))
        store.attachment_path(book_id, attachment.relative_path).unlink(missing_ok=True)
        touch_book(store, book_id)
