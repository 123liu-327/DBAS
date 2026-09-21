"""账单业务服务：校验跨资源规则、组织分摊并管理结算前的账单生命周期。"""

from uuid import uuid4

from pydantic import ValidationError

from app.core.exceptions import AppError, validation_error_message
from app.core.pagination import paginate
from app.crud import bills as bill_crud
from app.crud import members as member_crud
from app.crud.books import require_book, touch_book
from app.models.bill import Bill, BillStatus
from app.schemas.bill import (
    BillCreate,
    BillDetail,
    BillFields,
    BillItem,
    BillPage,
    BillParticipant,
    BillPatch,
    BillPreview,
    BillShareItem,
    MemberShare,
    MonthlyShares,
)
from app.services.splitting_service import calculate_shares, stay_map, validate_members
from app.storage import FileStore


def checked_bill(raw: dict) -> Bill:
    """构造完整 Bill，并将 Pydantic 错误转换为统一业务错误。"""
    try:
        return Bill.model_validate(raw)
    except ValidationError as exc:
        raise AppError(
            "INVALID_BILL", validation_error_message(exc.errors()[0]), status_code=422
        ) from exc


# 以下为待手写区域：list_bills（现有实现为参考，实际改写后再标记为手写）
def list_bills(store: FileStore, book_id: int, month: str | None = None) -> list[Bill]:
    """读取账本内账单；提供月份时只保留该月有记账日期的账单。"""
    # 先提取当前账本内的所有账单。
    bills = bill_crud.list_bills(store, book_id)
    if month is not None:
        bills = [bill for bill in bills if bill.date and bill.date.strftime("%Y-%m") == month]
    return bills
# 待手写区域结束：list_bills


def list_page(
    store: FileStore, book_id: int, month: str | None, page: int, page_size: int,
) -> BillPage:
    """分页构造账单摘要，避免列表接口返回完整分摊和入住详情。"""
    records = paginate(list_bills(store, book_id, month), page, page_size)
    stays = stay_map(store, book_id)
    items = [
        BillItem(
            id=bill.id, book_id=bill.book_id, title=bill.title,
            amount_cents=bill.amount_cents, date=bill.date, method=bill.method,
            status=bill.status, payer_id=bill.payer_id,
            payer_name=(
                member_crud.require_member(store, bill.payer_id).name
                if bill.payer_id in stays else None
            ),
            participant_count=len(bill.participants),
            attachment_count=len(bill.attachments),
            created_at=bill.created_at, updated_at=bill.updated_at,
        )
        for bill in records.list
    ]
    return BillPage(list=items, total=records.total, has_more=records.has_more)


def posted_bills(store: FileStore, book_id: int, start: str, end: str) -> list[Bill]:
    """取得月份闭区间内的 POSTED 账单，供报表和结算共用。"""
    return [
        bill for bill in list_bills(store, book_id)
        if bill.status == BillStatus.POSTED and bill.date is not None
        and start <= bill.date.strftime("%Y-%m") <= end
    ]


# 以下为待手写区域：detail（现有实现为参考，实际改写后再标记为手写）
def detail(store: FileStore, book_id: int, bill_id: str) -> BillDetail:
    """组合账单、垫付人、参与人的入住信息和即时分摊明细。"""
    bill = bill_crud.require_bill(store, book_id, bill_id)
    stays = stay_map(store, book_id)
    members = {
        member_id: member_crud.require_member(store, member_id) for member_id in stays
    }
    shares = []
    # 草稿字段可能不完整，因此详情不尝试计算草稿分摊。
    if bill.status != BillStatus.DRAFT:
        shares = [
            BillShareItem(**share.model_dump(), member=members[share.member_id],
                          stay=stays[share.member_id])
            for share in calculate_shares(bill, stays)
        ]
    return BillDetail(
        bill=bill, payer=members.get(bill.payer_id),
        participants=[
            BillParticipant(member=members[member_id], stay=stays[member_id])
            for member_id in bill.participants if member_id in members
        ],
        shares=shares,
    )
# 待手写区域结束：detail


# 以下为待手写区域：preview（现有实现为参考，实际改写后再标记为手写）
def preview(store: FileStore, book_id: int, data: BillFields) -> BillPreview:
    """按正式账单规则计算预览，但不分配真实 ID，也不写入文件。"""
    require_book(store, book_id)
    bill = checked_bill({"id": "preview", "bookId": book_id, **data.model_dump(by_alias=True),
                         "status": "POSTED"})
    stays = stay_map(store, book_id)
    validate_members(bill, stays)
    members = {
        member_id: member_crud.require_member(store, member_id) for member_id in stays
    }
    shares = calculate_shares(bill, stays)
    return BillPreview(
        total_cents=bill.amount_cents,
        payer=members[bill.payer_id],
        participants=[
            BillParticipant(member=members[member_id], stay=stays[member_id])
            for member_id in bill.participants
        ],
        shares=[BillShareItem(**share.model_dump(), member=members[share.member_id],
                              stay=stays[share.member_id])
                for share in shares],
    )
# 待手写区域结束：preview


# 以下为待手写区域：create_bill（现有实现为参考，实际改写后再标记为手写）
def create_bill(store: FileStore, book_id: int, data: BillCreate) -> Bill:
    """在账本锁内校验、试算并持久化账单。"""

    require_book(store, book_id)
    with store.book_lock(book_id):
        # 加锁后再次确认账本存在，防止并发删除造成悬空账单。
        require_book(store, book_id)
        bill = checked_bill({"id": f"b_{uuid4().hex}", "bookId": book_id,
                             **data.model_dump(mode="json", by_alias=True)})
        stays = stay_map(store, book_id)
        validate_members(bill, stays)
        if bill.status == BillStatus.POSTED:
            # 写入前先完整计算一次，保证不会保存无法分摊的正式账单。
            calculate_shares(bill, stays)
        bill_crud.insert_bill(store, bill)
        touch_book(store, book_id)
        return bill
# 待手写区域结束：create_bill


# 以下为待手写区域：update_bill（现有实现为参考，实际改写后再标记为手写）
def update_bill(store: FileStore, book_id: int, bill_id: str, data: BillPatch) -> Bill:
    """合并局部修改，执行状态与分摊校验后原子替换原账单。"""

    require_book(store, book_id)
    with store.book_lock(book_id):
        original = bill_crud.require_bill(store, book_id, bill_id)
        if original.status in {BillStatus.LOCKED, BillStatus.SETTLED}:
            raise AppError("BILL_LOCKED", "锁定或结清账单不能修改", status_code=409)
        changes = data.model_dump(exclude_unset=True, by_alias=False)
        if original.status == BillStatus.POSTED and changes.get("status") == BillStatus.DRAFT:
            raise AppError("INVALID_STATUS", "已入账账单不能退回草稿", status_code=409,
                           field="status")
        try:
            bill = original.with_updates(**changes)
        except ValidationError as exc:
            raise AppError(
                "INVALID_BILL", validation_error_message(exc.errors()[0]), status_code=422
            ) from exc
        stays = stay_map(store, book_id)
        validate_members(bill, stays)
        if bill.status == BillStatus.POSTED:
            calculate_shares(bill, stays)
        bill_crud.replace_bill(store, bill)
        touch_book(store, book_id)
        return bill
# 待手写区域结束：update_bill


def delete_bill(store: FileStore, book_id: int, bill_id: str) -> None:
    """删除可修改账单及其附件文件，并更新账本活跃时间。"""
    require_book(store, book_id)
    with store.book_lock(book_id):
        bill = bill_crud.require_bill(store, book_id, bill_id)
        if bill.status in {BillStatus.LOCKED, BillStatus.SETTLED}:
            raise AppError("BILL_LOCKED", "锁定或结清账单不能删除", status_code=409)
        bill_crud.remove_bill(store, book_id, bill_id)
        for attachment in bill.attachments:
            store.attachment_path(book_id, attachment.relative_path).unlink(missing_ok=True)
        touch_book(store, book_id)


# 以下为待手写区域：monthly_shares（现有实现为参考，实际改写后再标记为手写）
def monthly_shares(store: FileStore, book_id: int, month: str) -> MonthlyShares:
    """即时汇总指定月份每位入住成员的分摊金额，排除草稿。"""
    stays = stay_map(store, book_id)
    totals = dict.fromkeys(stays, 0)
    for bill in list_bills(store, book_id, month):
        if bill.status == BillStatus.DRAFT:
            continue
        for share in calculate_shares(bill, stays):
            totals[share.member_id] += share.share_cents
    return MonthlyShares(
        month=month,
        shares=[MemberShare(member_id=member_id, share_cents=cents)
                for member_id, cents in totals.items()],
    )
# 待手写区域结束：monthly_shares
