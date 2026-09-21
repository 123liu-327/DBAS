"""账本业务服务：组合页面数据并协调账本 CRUD，文件读写仍由 CRUD 负责。"""

from app.core.pagination import paginate
from app.crud import bills as bill_crud
from app.crud import books as book_crud
from app.crud import stays as stay_crud
from app.models.book import Book
from app.schemas.book import BookBillCounts, BookCreate, BookDetail, BookItem, BookPage, BookPatch
from app.services.stay_service import item as stay_item
from app.storage import FileStore


def _item(book: Book, *, member_count: int, bill_count: int) -> BookItem:
    """将持久化账本与实时统计数量组合为列表项。"""
    return BookItem(
        **book.model_dump(), last_active_at=book.updated_at,
        member_count=member_count, bill_count=bill_count,
    )


def list_page(store: FileStore, page: int, page_size: int) -> BookPage:
    """分页读取账本，并为当前页逐项补充入住人数和账单数量。"""
    records = paginate(book_crud.list_books(store), page, page_size)
    items = [
        _item(book, member_count=len(stay_crud.list_stays(store, book.id)),
              bill_count=len(bill_crud.list_bills(store, book.id)))
        for book in records.list
    ]
    return BookPage(list=items, total=records.total, has_more=records.has_more)


def detail(store: FileStore, book_id: int) -> BookDetail:
    """返回账本、入住信息和各状态账单数量组成的详情数据。"""
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


# 以下为待手写区域：create_book（现有实现为参考，实际改写后再标记为手写）
def create_book(store: FileStore, data: BookCreate) -> Book:
    """把已通过 Schema 校验的创建参数交给 CRUD 持久化。"""
    return book_crud.insert_book(store, name=data.name, description=data.description)
# 待手写区域结束：create_book


# 以下为待手写区域：update_book（现有实现为参考，实际改写后再标记为手写）
def update_book(store: FileStore, book_id: int, data: BookPatch) -> Book:
    """仅更新请求明确提交的字段，并由模型刷新 updatedAt。"""
    return book_crud.update_book(
        store, book_id,
        lambda original: original.with_updates(**data.model_dump(exclude_unset=True)),
    )
# 待手写区域结束：update_book
