"""Split per-book members.json into global members.json and per-book stays.json."""

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from filelock import FileLock

from app.algorithms.splitting import split_bill
from app.models.bill import Bill, BillStatus
from app.models.member import Member
from app.models.stay import Stay
from app.storage.files import FileStore, StorageError


def _rewrite_bill(raw: dict, mapping: dict[str, int], book_id: int) -> dict:
    rewritten = dict(raw)
    if rewritten.get("bookId") != book_id:
        raise ValueError(f"账单 {rewritten.get('id')} 引用了其他账本")
    try:
        rewritten["participants"] = [mapping[str(value)] for value in raw.get("participants", [])]
        if raw.get("payerId") is not None:
            rewritten["payerId"] = mapping[str(raw["payerId"])]
        if raw.get("weights") is not None:
            rewritten["weights"] = {
                str(mapping[str(member_id)]): weight
                for member_id, weight in raw["weights"].items()
            }
    except KeyError as exc:
        raise ValueError(f"账单 {rewritten.get('id')} 引用了不存在的成员") from exc
    return rewritten


def migrate_member_storage(data_dir: Path) -> dict:
    root = data_dir.resolve()
    if not root.is_dir():
        raise ValueError("数据目录不存在")
    legacy_files = sorted((root / "books").glob("[0-9]*/members.json"))
    if not legacy_files:
        if (root / "members.json").is_file():
            return {"migrated": False, "members": 0, "books": 0, "backup": None}
        raise ValueError("未找到旧版 members.json 文件")

    parent = root.parent
    lock_path = parent / f".{root.name}.member-migration.lock"
    with FileLock(str(lock_path), timeout=10):
        stage = parent / f".{root.name}.members-{uuid4().hex}"
        backup = parent / (
            f"{root.name}.backup-members-"
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        )
        try:
            shutil.copytree(root, stage, ignore=shutil.ignore_patterns(".locks"))
            store = FileStore(stage)
            members: list[Member] = []
            next_member_id = 1
            migrated_books = 0

            for member_file in sorted(
                stage.glob("books/[0-9]*/members.json"),
                key=lambda path: int(path.parent.name),
            ):
                book_id = int(member_file.parent.name)
                raw_members = store.read_json(member_file, default={"members": []})["members"]
                mapping: dict[str, int] = {}
                stays: list[Stay] = []
                for raw in raw_members:
                    old_id = str(raw["id"])
                    if old_id in mapping:
                        raise ValueError(f"账本 {book_id} 中存在重复成员 ID：{old_id}")
                    member_id = next_member_id
                    next_member_id += 1
                    mapping[old_id] = member_id
                    member = Member.model_validate(
                        {
                            "id": member_id,
                            "name": raw["name"],
                            "createdAt": raw.get("createdAt"),
                            "updatedAt": raw.get("updatedAt"),
                        }
                    )
                    stay = Stay.model_validate(
                        {
                            "bookId": book_id,
                            "memberId": member_id,
                            "joinDate": raw["joinDate"],
                            "leaveDate": raw.get("leaveDate"),
                            "createdAt": raw.get("createdAt"),
                            "updatedAt": raw.get("updatedAt"),
                        }
                    )
                    members.append(member)
                    stays.append(stay)

                bills = []
                stay_lookup = {stay.member_id: stay for stay in stays}
                for raw_bill in store.read_jsonl(store.bills_path(book_id)):
                    bill = Bill.model_validate(_rewrite_bill(raw_bill, mapping, book_id))
                    if bill.status != BillStatus.DRAFT:
                        shares = split_bill(bill, stay_lookup)
                        if sum(share.share_cents for share in shares) != bill.amount_cents:
                            raise ValueError(f"账单分摊金额不守恒：{bill.id}")
                    bills.append(bill)

                store.write_json(
                    store.stays_path(book_id),
                    {"stays": [stay.model_dump(mode="json") for stay in stays]},
                    book_id=book_id,
                )
                store.write_jsonl(
                    store.bills_path(book_id),
                    [bill.model_dump(mode="json") for bill in bills],
                    book_id=book_id,
                )
                member_file.unlink()
                migrated_books += 1

            store.write_json(
                store.members_path,
                {"members": [member.model_dump(mode="json") for member in members]},
            )
            sequences = store.read_json(store.sequences_path, default={})
            sequences["nextMemberId"] = next_member_id
            store.write_json(store.sequences_path, sequences)

            if any(stage.glob("books/[0-9]*/members.json")):
                raise StorageError("Legacy member files remain in migration stage")
            if len(store.read_json(store.members_path)["members"]) != len(members):
                raise StorageError("Migrated member count does not match")

            os.replace(root, backup)
            try:
                os.replace(stage, root)
            except OSError:
                os.replace(backup, root)
                raise
            return {
                "migrated": True, "members": len(members), "books": migrated_books,
                "backup": str(backup),
            }
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    print(json.dumps(migrate_member_storage(args.data_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
