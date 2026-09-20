from typing import Annotated

from fastapi import APIRouter, Path, Response

from app.api.deps import StoreDep
from app.api.pagination import PageDep
from app.core.responses import ApiResponse, ok
from app.crud import books as book_crud
from app.models.book import Book
from app.schemas.book import BookCreate, BookDetail, BookPage, BookPatch
from app.services import book_service

router = APIRouter(prefix="/books", tags=["账本"])
BookId = Annotated[int, Path(alias="bookId", gt=0)]


@router.get("", response_model=ApiResponse[BookPage])
def list_books(
    store: StoreDep, params: PageDep,
) -> ApiResponse[BookPage]:
    return ok(book_service.list_page(store, params.page, params.page_size),
              message="账本列表获取成功")


@router.post("", response_model=ApiResponse[Book], status_code=201)
def create_book(data: BookCreate, store: StoreDep) -> ApiResponse[Book]:
    return ok(book_service.create_book(store, data), message="账本创建成功", code=201)


@router.get("/{bookId}", response_model=ApiResponse[BookDetail])
def get_book(book_id: BookId, store: StoreDep) -> ApiResponse[BookDetail]:
    return ok(book_service.detail(store, book_id))


@router.patch("/{bookId}", response_model=ApiResponse[Book])
def update_book(book_id: BookId, data: BookPatch, store: StoreDep) -> ApiResponse[Book]:
    return ok(book_service.update_book(store, book_id, data), message="账本修改成功")


@router.delete("/{bookId}", status_code=204)
def delete_book(book_id: BookId, store: StoreDep) -> Response:
    book_crud.delete_book(store, book_id)
    return Response(status_code=204)
