from typing import Annotated

from fastapi import APIRouter, Path, Response

from app.api.deps import StoreDep
from app.api.pagination import PageDep
from app.core.responses import ApiResponse, ok
from app.crud import stays as stay_crud
from app.models.stay import Stay
from app.schemas.stay import StayCreate, StayDetail, StayPage, StayPatch
from app.services import stay_service

router = APIRouter(prefix="/books/{bookId}/stays", tags=["入住记录"])
BookId = Annotated[int, Path(alias="bookId", gt=0)]
MemberId = Annotated[int, Path(alias="memberId", gt=0)]


@router.get("", response_model=ApiResponse[StayPage])
def list_stays(
    book_id: BookId, store: StoreDep, params: PageDep,
) -> ApiResponse[StayPage]:
    return ok(stay_service.list_page(store, book_id, params.page, params.page_size))


@router.post("", response_model=ApiResponse[Stay], status_code=201)
def create_stay(book_id: BookId, data: StayCreate, store: StoreDep) -> ApiResponse[Stay]:
    return ok(stay_crud.create_stay(store, book_id, data), message="入住登记成功", code=201)


@router.get("/{memberId}", response_model=ApiResponse[StayDetail])
def get_stay(
    book_id: BookId, member_id: MemberId, store: StoreDep
) -> ApiResponse[StayDetail]:
    return ok(stay_service.detail(store, book_id, member_id))


@router.patch("/{memberId}", response_model=ApiResponse[Stay])
def update_stay(
    book_id: BookId, member_id: MemberId, data: StayPatch, store: StoreDep
) -> ApiResponse[Stay]:
    return ok(
        stay_service.update_stay(store, book_id, member_id, data),
        message="入住记录修改成功",
    )


@router.delete("/{memberId}", status_code=204)
def delete_stay(book_id: BookId, member_id: MemberId, store: StoreDep) -> Response:
    stay_crud.delete_stay(store, book_id, member_id)
    return Response(status_code=204)
