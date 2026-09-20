"""Book records live in numbered directories; sequences never reuse IDs."""

import shutil
from collections.abc import Callable

from app.core.exceptions import AppError
from app.models.book import Book
from app.storage import FileStore, StorageError


def list_books(store: FileStore) -> list[Book]:
    if not store.books_dir.exists():
        return []
    books = []
    for directory in store.books_dir.iterdir():
        if directory.is_dir() and directory.name.isdecimal() and int(directory.name) > 0:
            record = store.read_json(directory / "book.json")
            if record is None:
                raise StorageError(f"Missing book.json: {directory}")
            book = Book.model_validate(record)
            if book.id != int(directory.name):
                raise StorageError(f"Book ID does not match directory: {directory}")
            books.append(book)
    return sorted(books, key=lambda book: (book.updated_at, book.id), reverse=True)


def get_book(store: FileStore, book_id: int) -> Book | None:
    path = store.book_path(book_id)
    raw = store.read_json(path)
    if raw is None:
        return None
    book = Book.model_validate(raw)
    if book.id != book_id:
        raise StorageError(f"Book ID does not match directory: {path}")
    return book


def require_book(store: FileStore, book_id: int) -> Book:
    book = get_book(store, book_id)
    if book is None:
        raise AppError("BOOK_NOT_FOUND", "账本不存在", status_code=404, field="bookId")
    return book


def _next_id(store: FileStore) -> int:
    state = store.read_json(store.sequences_path)
    if state is not None and "nextBookId" in state:
        return state["nextBookId"]
    return max((book.id for book in list_books(store)), default=0) + 1


def insert_book(store: FileStore, *, name: str, description: str | None = None) -> Book:
    """Allocate under the global lock, then publish a complete book directory."""
    with store.index_lock():
        book_id = _next_id(store)
        book = Book(id=book_id, name=name, description=description)
        state = store.read_json(store.sequences_path, default={})
        state["nextBookId"] = book_id + 1
        store.write_json(store.sequences_path, state)
        store.publish_book(book_id, book.model_dump(mode="json"))
        return book


def update_book(store: FileStore, book_id: int, change: Callable[[Book], Book]) -> Book:
    with store.book_lock(book_id):
        updated = change(require_book(store, book_id))
        store.write_json(store.book_path(book_id), updated.model_dump(mode="json"),
                         book_id=book_id)
        return updated


def touch_book(store: FileStore, book_id: int) -> None:
    update_book(store, book_id, lambda original: original.with_updates())


def delete_book(store: FileStore, book_id: int) -> None:
    require_book(store, book_id)
    with store.book_lock(book_id):
        require_book(store, book_id)
        stays = store.read_json(store.stays_path(book_id), default={"stays": []})
        bills = store.read_jsonl(store.bills_path(book_id))
        settlements = store.read_jsonl(store.settlements_path(book_id))
        attachments = store.attachments_dir(book_id)
        has_attachments = attachments.exists() and any(attachments.iterdir())
        if stays["stays"] or bills or settlements or has_attachments:
            raise AppError("BOOK_NOT_EMPTY", "账本含有成员或账单，不能删除", status_code=409)
        directory = store.book_dir(book_id)
        if directory.exists():
            if not directory.resolve().is_relative_to(store.books_dir.resolve()):
                raise ValueError("Book directory escapes data root")
            shutil.rmtree(directory)
