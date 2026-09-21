"""入住业务服务：组合成员信息，并检查日期修改对按天账单的影响。"""

from pydantic import ValidationError

from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.crud import bills as bill_crud
from app.crud import members as member_crud
from app.crud import stays as stay_crud
from app.models.bill import BillStatus, SplitMethod
from app.models.stay import Stay
from app.schemas.stay import StayDetail, StayItem, StayPage, StayPatch
from app.services.splitting_service import calculate_shares, stay_map
from app.storage import FileStore


def item(store: FileStore, stay: Stay) -> StayItem:
    """将入住记录、成员档案和账单使用数量组合为前端列表项。"""
    member = member_crud.require_member(store, stay.member_id)
    bills = bill_crud.list_bills(store, stay.book_id)
    return StayItem(
        **stay.model_dump(), member=member,
        bill_count=sum(stay.member_id in bill.participants for bill in bills),
        paid_bill_count=sum(stay.member_id == bill.payer_id for bill in bills),
    )


def list_page(store: FileStore, book_id: int, page: int, page_size: int) -> StayPage:
    """分页返回指定账本的入住记录。"""
    records = paginate(stay_crud.list_stays(store, book_id), page, page_size)
    return StayPage(
        list=[item(store, stay) for stay in records.list],
        total=records.total, has_more=records.has_more,
    )


def detail(store: FileStore, book_id: int, member_id: int) -> StayDetail:
    """返回一条入住记录及对应成员、参与和垫付次数。"""
    stay_item = item(store, stay_crud.require_stay(store, book_id, member_id))
    return StayDetail(
        stay=Stay.model_validate(
            stay_item.model_dump(exclude={"member", "bill_count", "paid_bill_count"})
        ), member=stay_item.member,
        bill_count=stay_item.bill_count, paid_bill_count=stay_item.paid_bill_count,
    )


def update_stay(
    store: FileStore, book_id: int, member_id: int, data: StayPatch
) -> Stay:
    """修改入住日期，并阻止破坏既有账单分摊的变更。"""

    # 修改和影响检查处于同一个账本锁内，避免检查后数据被并发改写。
    with store.book_lock(book_id):
        original = stay_crud.require_stay(store, book_id, member_id)
        try:
            proposed = original.with_updates(
                **data.model_dump(exclude_unset=True, by_alias=False)
            )
        except ValidationError as exc:
            raise AppError(
                "INVALID_STAY", "退宿日期不能早于入住日期",
                status_code=422, field="leaveDate",
            ) from exc
        stays = stay_map(store, book_id)
        stays[member_id] = proposed
        # 只有包含该成员的按天账单会受到入住日期变化影响。
        for bill in bill_crud.list_bills(store, book_id):
            if bill.method != SplitMethod.BY_DAYS or member_id not in bill.participants:
                continue
            if bill.status in {BillStatus.LOCKED, BillStatus.SETTLED}:
                # 锁定或结清账单的历史分摊不能改变，因此比较修改前后的结果。
                before = calculate_shares(bill, stay_map(store, book_id))
                after = calculate_shares(bill, stays)
                if before != after:
                    raise AppError(
                        "STAY_LOCKED", "修改入住日期会改变已锁定或结清账单的分摊",
                        status_code=409, field="joinDate",
                    )
            elif bill.status == BillStatus.POSTED:
                # 普通已入账账单允许动态重算，但修改后仍须能够有效分摊。
                try:
                    calculate_shares(bill, stays)
                except AppError as exc:
                    if exc.code != "INVALID_SPLIT":
                        raise
                    raise AppError(
                        "INVALID_STAY", "修改后相关按天账单没有有效在住天数",
                        status_code=422, field="joinDate",
                    ) from exc
        return stay_crud.update_stay(store, book_id, member_id, data)
