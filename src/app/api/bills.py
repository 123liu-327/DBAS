from typing import Annotated

from fastapi import APIRouter, Path, Query, Response

from app.api.deps import StoreDep
from app.api.pagination import PageDep
from app.core.responses import ApiResponse, ok
from app.models.bill import Bill
from app.schemas.bill import BillCreate, BillDetail, BillFields, BillPage, BillPatch, BillPreview
from app.services import bill_service

router = APIRouter(prefix="/books/{bookId}", tags=["账单"])
BookId = Annotated[int, Path(alias="bookId", gt=0)]
BillId = Annotated[str, Path(alias="billId")]
Month = Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


@router.get("/bills", response_model=ApiResponse[BillPage])
def list_bills(
    book_id: BookId, store: StoreDep, params: PageDep, month: Month = None,
) -> ApiResponse[BillPage]:
    return ok(bill_service.list_page(store, book_id, month, params.page, params.page_size))


@router.post("/bills", response_model=ApiResponse[Bill], status_code=201)
def create_bill(book_id: BookId, data: BillCreate, store: StoreDep) -> ApiResponse[Bill]:
    return ok(bill_service.create_bill(store, book_id, data), message="账单创建成功", code=201)


@router.get("/bills/{billId}", response_model=ApiResponse[BillDetail])
def get_bill(book_id: BookId, bill_id: BillId, store: StoreDep) -> ApiResponse[BillDetail]:
    return ok(bill_service.detail(store, book_id, bill_id))


@router.patch("/bills/{billId}", response_model=ApiResponse[Bill])
def update_bill(
    book_id: BookId, bill_id: BillId, data: BillPatch, store: StoreDep
) -> ApiResponse[Bill]:
    return ok(bill_service.update_bill(store, book_id, bill_id, data), message="账单修改成功")


@router.delete("/bills/{billId}", status_code=204)
def delete_bill(book_id: BookId, bill_id: BillId, store: StoreDep) -> Response:
    bill_service.delete_bill(store, book_id, bill_id)
    return Response(status_code=204)


@router.post("/bill-previews", response_model=ApiResponse[BillPreview])
def preview_bill(book_id: BookId, data: BillFields, store: StoreDep) -> ApiResponse[BillPreview]:
    return ok(bill_service.preview(store, book_id, data))
