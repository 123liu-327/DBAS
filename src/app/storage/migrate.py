"""One-time conversion of legacy string book IDs into numbered book directories."""

import argparse
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from app.algorithms.splitting import split_bill
from app.crud.books import list_books
from app.models.bill import Bill, BillStatus
from app.models.book import Book
from app.models.member import Member
from app.models.stay import Stay
from app.storage.files import FileStore, StorageError


def migrate_legacy(source: Path, target: Path) -> dict[str, int]:
    source = source.resolve()
    target = target.resolve()
    if not source.is_dir() or not (source / "books.json").is_file():
        raise ValueError("源目录必须包含旧版 books.json")
    if target.exists() or target == source or target.is_relative_to(source):
        raise ValueError("目标必须是源目录之外的新目录")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.parent / f".{target.name}.migrating-{uuid4().hex}"
    if not stage.resolve().is_relative_to(target.parent.resolve()):
        raise ValueError("迁移暂存路径超出目标父目录")

    mapping: dict[str, int] = {}
    migrated_members: list[Member] = []
    next_member_id = 1
    try:
        store = FileStore(stage)
        legacy = FileStore(source)
        index = legacy.read_json(source / "books.json")
        records = index["books"]
        for book_id, old_book in enumerate(records, start=1):
            old_id = old_book["id"]
            if not isinstance(old_id, str) or old_id in mapping:
                raise ValueError("旧版账本 ID 必须是互不相同的字符串")
            mapping[old_id] = book_id
            book = Book.model_validate({**old_book, "id": book_id,
                                        "description": old_book.get("description")})
            store.publish_book(book_id, book.model_dump(mode="json"))

            old_dir = source / "books" / old_id
            if not old_dir.resolve().is_relative_to((source / "books").resolve()):
                raise ValueError("旧版账本路径超出源目录")
            members_raw = legacy.read_json(old_dir / "members.json", default={"members": []})
            member_ids: dict[str, int] = {}
            stays: list[Stay] = []
            for raw_member in members_raw["members"]:
                old_member_id = str(raw_member["id"])
                if old_member_id in member_ids:
                    raise ValueError(f"账本 {old_id} 中存在重复成员 ID")
                member_id = next_member_id
                next_member_id += 1
                member_ids[old_member_id] = member_id
                migrated_members.append(Member.model_validate({
                    "id": member_id, "name": raw_member["name"],
                    "createdAt": raw_member.get("createdAt"),
                    "updatedAt": raw_member.get("updatedAt"),
                }))
                stays.append(Stay.model_validate({
                    "bookId": book_id, "memberId": member_id,
                    "joinDate": raw_member["joinDate"],
                    "leaveDate": raw_member.get("leaveDate"),
                    "createdAt": raw_member.get("createdAt"),
                    "updatedAt": raw_member.get("updatedAt"),
                }))
            if len(member_ids) != len(members_raw["members"]):
                raise ValueError(f"账本 {old_id} 中存在重复成员 ID")
            stay_map = {stay.member_id: stay for stay in stays}
            store.write_json(store.stays_path(book_id),
                             {"stays": [item.model_dump(mode="json") for item in stays]},
                             book_id=book_id)

            bills = []
            for raw in legacy.read_jsonl(old_dir / "bills.jsonl"):
                if raw.get("bookId") != old_id:
                    raise ValueError(f"账单引用了其他账本：{old_id}")
                try:
                    participants = [member_ids[str(value)] for value in raw.get("participants", [])]
                    payer_id = (
                        member_ids[str(raw["payerId"])]
                        if raw.get("payerId") is not None else None
                    )
                    weights = (
                        {str(member_ids[str(key)]): value for key, value in raw["weights"].items()}
                        if raw.get("weights") is not None else None
                    )
                except KeyError as exc:
                    raise ValueError(f"账单引用了不存在的成员：{raw.get('id')}") from exc
                bill = Bill.model_validate({
                    **raw, "bookId": book_id, "participants": participants,
                    "payerId": payer_id, "weights": weights,
                })
                if bill.status != BillStatus.DRAFT:
                    shares = split_bill(bill, stay_map)
                    if sum(item.share_cents for item in shares) != bill.amount_cents:
                        raise ValueError(f"账单分摊金额不守恒：{bill.id}")
                bills.append(bill)
            store.write_jsonl(store.bills_path(book_id),
                              [bill.model_dump(mode="json") for bill in bills],
                              book_id=book_id)

            old_attachments = old_dir / "attachments"
            if old_attachments.exists():
                if any(path.is_symlink() for path in old_attachments.rglob("*")):
                    raise ValueError("旧版附件目录不能包含符号链接")
                shutil.copytree(old_attachments, store.attachments_dir(book_id),
                                dirs_exist_ok=True)
            for bill in bills:
                for attachment in bill.attachments:
                    if not store.attachment_path(book_id, attachment.relative_path).is_file():
                        raise ValueError(f"附件不存在：{attachment.id}")

        store.write_json(store.members_path, {
            "members": [member.model_dump(mode="json") for member in migrated_members]
        })
        store.write_json(store.sequences_path, {
            "nextBookId": len(records) + 1, "nextMemberId": next_member_id,
        })
        if len(list_books(store)) != len(records):
            raise StorageError("Migrated book count does not match source")
        if target.exists():
            raise FileExistsError(f"Target appeared during migration: {target}")
        os.replace(stage, target)
        return mapping
    finally:
        if stage.exists():
            if not stage.resolve().is_relative_to(target.parent.resolve()):
                raise ValueError("迁移暂存路径超出目标父目录")
            shutil.rmtree(stage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(migrate_legacy(args.source, args.target), ensure_ascii=False))


if __name__ == "__main__":
    main()
