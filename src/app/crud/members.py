"""Global member profile records."""

from app.core.exceptions import AppError
from app.models.member import Member
from app.schemas.member import MemberCreate, MemberPatch
from app.storage import FileStore


def list_members(store: FileStore) -> list[Member]:
    data = store.read_json(store.members_path, default={"members": []})
    return [Member.model_validate(item) for item in data["members"]]


def get_member(store: FileStore, member_id: int) -> Member | None:
    return next((item for item in list_members(store) if item.id == member_id), None)


def require_member(store: FileStore, member_id: int) -> Member:
    member = get_member(store, member_id)
    if member is None:
        raise AppError("MEMBER_NOT_FOUND", "成员不存在", status_code=404, field="memberId")
    return member


def _next_id(store: FileStore) -> int:
    state = store.read_json(store.sequences_path, default={})
    if "nextMemberId" in state:
        return state["nextMemberId"]
    return max((member.id for member in list_members(store)), default=0) + 1


def create_member(store: FileStore, data: MemberCreate) -> Member:
    with store.index_lock():
        member_id = _next_id(store)
        member = Member(id=member_id, **data.model_dump(by_alias=False))
        state = store.read_json(store.sequences_path, default={})
        state["nextMemberId"] = member_id + 1
        store.write_json(store.sequences_path, state)

        def append(records: dict) -> dict:
            records["members"].append(member.model_dump(mode="json"))
            return records

        store.update_json(store.members_path, append, default={"members": []})
        return member


def update_member(store: FileStore, member_id: int, data: MemberPatch) -> Member:
    with store.index_lock():
        updated: Member | None = None

        def replace(records: dict) -> dict:
            nonlocal updated
            for position, raw in enumerate(records["members"]):
                if raw["id"] == member_id:
                    updated = Member.model_validate(raw).with_updates(
                        **data.model_dump(exclude_unset=True, by_alias=False)
                    )
                    records["members"][position] = updated.model_dump(mode="json")
                    return records
            raise AppError(
                "MEMBER_NOT_FOUND", "成员不存在", status_code=404, field="memberId"
            )

        store.update_json(store.members_path, replace, default={"members": []})
        assert updated is not None
        return updated


def delete_member(store: FileStore, member_id: int) -> None:
    with store.index_lock():
        require_member(store, member_id)
        if store.books_dir.exists():
            for directory in store.books_dir.iterdir():
                if not directory.is_dir() or not directory.name.isdecimal():
                    continue
                stays = store.read_json(
                    store.stays_path(int(directory.name)), default={"stays": []}
                )
                if any(item["memberId"] == member_id for item in stays["stays"]):
                    raise AppError(
                        "MEMBER_IN_USE", "该成员仍有账本入住记录，不能删除",
                        status_code=409, field="memberId",
                    )

        def remove(records: dict) -> dict:
            records["members"] = [
                item for item in records["members"] if item["id"] != member_id
            ]
            return records

        store.update_json(store.members_path, remove, default={"members": []})
