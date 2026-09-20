"""Book creation and updates; CRUD owns the file operations."""

from app.core.pagination import paginate
from app.crud import bills as bill_crud
from app.crud import books as book_crud
from app.crud import stays as stay_crud
from app.models.book import Book
from app.schemas.book import BookBillCounts, BookCreate, BookDetail, BookItem, BookPage, BookPatch
from app.services.stay_service import item as stay_item
from app.storage import FileStore


def _item(book: Book, *, member_count: int, bill_count: int) -> BookItem:
    return BookItem(
        **book.model_dump(), last_active_at=book.updated_at,
        member_count=member_count, bill_count=bill_count,
    )


def list_page(store: FileStore, page: int, page_size: int) -> BookPage:
    records = paginate(book_crud.list_books(store), page, page_size)
    items = [
        _item(book, member_count=len(stay_crud.list_stays(store, book.id)),
              bill_count=len(bill_crud.list_bills(store, book.id)))
        for book in records.list
    ]
    return BookPage(list=items, total=records.total, has_more=records.has_more)


def detail(store: FileStore, book_id: int) -> BookDetail:
    book = book_crud.require_book(store, book_id)
    stays = stay_crud.list_stays(store, book_id)
    bills = bill_crud.list_bills(store, book_id)
    counts = BookBillCounts(
        draft=sum(bill.status == "DRAFT" for bill in bills),
        posted=sum(bill.status == "POSTED" for bill in bills),
        locked=sum(bill.status == "LOCKED" for bill in bills),
        settled=sum(bill.status == "SETTLED" for bill in bills),
    )
    return BookDetail(
        book=_item(book, member_count=len(stays), bill_count=len(bills)),
        stays=[stay_item(store, stay) for stay in stays], bill_status_counts=counts,
    )


def create_book(store: FileStore, data: BookCreate) -> Book:
    return book_crud.insert_book(store, name=data.name, description=data.description)


def update_book(store: FileStore, book_id: int, data: BookPatch) -> Book:
    return book_crud.update_book(
        store, book_id,
        lambda original: original.with_updates(**data.model_dump(exclude_unset=True)),
    )
