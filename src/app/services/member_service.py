"""Global member response composition and deletion protection."""

from app.core.pagination import paginate
from app.crud import bills as bill_crud
from app.crud import books as book_crud
from app.crud import members as member_crud
from app.crud import stays as stay_crud
from app.schemas.member import MemberDetail, MemberItem, MemberPage
from app.storage import FileStore


def _usage(store: FileStore, member_id: int) -> tuple[list, int, int]:
    stays = []
    bill_count = 0
    paid_bill_count = 0
    for book in book_crud.list_books(store):
        stay = stay_crud.get_stay(store, book.id, member_id)
        if stay is None:
            continue
        stays.append(stay)
        bills = bill_crud.list_bills(store, book.id)
        bill_count += sum(member_id in bill.participants for bill in bills)
        paid_bill_count += sum(member_id == bill.payer_id for bill in bills)
    return stays, bill_count, paid_bill_count


def list_page(store: FileStore, page: int, page_size: int) -> MemberPage:
    records = paginate(member_crud.list_members(store), page, page_size)
    items = []
    for member in records.list:
        stays, bill_count, _ = _usage(store, member.id)
        items.append(
            MemberItem(
                **member.model_dump(), stay_count=len(stays), bill_count=bill_count
            )
        )
    return MemberPage(list=items, total=records.total, has_more=records.has_more)


def detail(store: FileStore, member_id: int) -> MemberDetail:
    member = member_crud.require_member(store, member_id)
    stays, bill_count, paid_bill_count = _usage(store, member_id)
    return MemberDetail(
        member=member, stays=stays, stay_count=len(stays), bill_count=bill_count,
        paid_bill_count=paid_bill_count,
    )
