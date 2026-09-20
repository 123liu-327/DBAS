from typing import Annotated

from fastapi import APIRouter, Path, Response

from app.api.deps import StoreDep
from app.api.pagination import PageDep
from app.core.responses import ApiResponse, ok
from app.crud import members as member_crud
from app.models.member import Member
from app.schemas.member import MemberCreate, MemberDetail, MemberPage, MemberPatch
from app.services import member_service

router = APIRouter(prefix="/members", tags=["成员档案"])
MemberId = Annotated[int, Path(alias="memberId", gt=0)]


@router.get("", response_model=ApiResponse[MemberPage])
def list_members(store: StoreDep, params: PageDep) -> ApiResponse[MemberPage]:
    return ok(member_service.list_page(store, params.page, params.page_size))


@router.post("", response_model=ApiResponse[Member], status_code=201)
def create_member(data: MemberCreate, store: StoreDep) -> ApiResponse[Member]:
    return ok(member_crud.create_member(store, data), message="成员创建成功", code=201)


@router.get("/{memberId}", response_model=ApiResponse[MemberDetail])
def get_member(member_id: MemberId, store: StoreDep) -> ApiResponse[MemberDetail]:
    return ok(member_service.detail(store, member_id))


@router.patch("/{memberId}", response_model=ApiResponse[Member])
def update_member(
    member_id: MemberId, data: MemberPatch, store: StoreDep
) -> ApiResponse[Member]:
    return ok(member_crud.update_member(store, member_id, data), message="成员修改成功")


@router.delete("/{memberId}", status_code=204)
def delete_member(member_id: MemberId, store: StoreDep) -> Response:
    member_crud.delete_member(store, member_id)
    return Response(status_code=204)
