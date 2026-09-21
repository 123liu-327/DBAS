"""启动初始化服务：准备全局成员文件，并为全新目录注入演示账本。"""

from app.crud.books import get_book, list_books
from app.models.book import Book
from app.storage import FileStore, StorageError

DEMO_BOOKS = (
    ("3栋402宿舍", "四人宿舍的水电费、网络费和公共用品账本。"),
    ("2栋315宿舍", "记录春季学期宿舍日常开支与轮流垫付的费用。"),
    ("研究生公寓A座608", "用于核对长租公寓的水电、保洁与日用品支出。"),
    ("东区学生公寓1203", "按入住日期分摊公共账单的演示账本。"),
    ("西区宿舍5栋214", "集中管理宿舍电费、桶装水和卫生用品。"),
    ("暑期留校宿舍", "适用于成员入住时间不同的暑期公共费用记录。"),
    ("实习合租公寓", "记录短期合租期间的房屋公共支出。"),
    ("毕业设计小组宿舍", "整理项目小组共同使用的生活用品账单。"),
    ("新生宿舍7栋506", "便于新生宿舍记录公共用品采购与费用分摊。"),
    ("交换生公寓B座301", "用于多成员短期入住场景的账单演示。"),
)


def prepare_member_storage(store: FileStore) -> None:
    """创建全局成员文件；检测到旧版账本内成员文件时要求先迁移。"""
    legacy_files = []
    if store.books_dir.exists():
        legacy_files = [
            directory / "members.json"
            for directory in store.books_dir.iterdir()
            if directory.is_dir() and directory.name.isdecimal()
            and (directory / "members.json").exists()
        ]
    if legacy_files:
        raise StorageError(
            "发现旧版账本级 members.json；请停止应用并运行 "
            "`python -m app.storage.migrate_members --data-dir data`"
        )
    with store.index_lock():
        if not store.members_path.exists():
            store.write_json(store.members_path, {"members": []})


def seed_demo_books(store: FileStore) -> None:
    """在空目录创建十个演示账本；中断后可续建，且不会覆盖用户数据。"""

    with store.index_lock():
        # 先清理未发布的暂存目录，再根据序列文件判断是否需要继续初始化。
        store.cleanup_pending_books()
        state = store.read_json(store.sequences_path)
        if state is not None and state.get("seedInProgress"):
            start_id = state["seedStartId"]
        else:
            if state is not None or list_books(store):
                return
            if (store.root / "books.json").exists():
                raise StorageError("发现旧版 books.json，请迁移数据后再启动应用")
            start_id = 1
            state = {"nextBookId": start_id + len(DEMO_BOOKS),
                     "seedInProgress": True, "seedStartId": start_id}
            store.write_json(store.sequences_path, state)

        for offset, (name, description) in enumerate(DEMO_BOOKS):
            book_id = start_id + offset
            existing = get_book(store, book_id)
            if existing is None:
                book = Book(id=book_id, name=name, description=description)
                store.publish_book(book_id, book.model_dump(mode="json"))
            elif existing.name != name or existing.description != description:
                raise StorageError(f"演示账本 ID {book_id} 已被其他数据占用")

        state["nextBookId"] = max(state["nextBookId"], start_id + len(DEMO_BOOKS))
        state.pop("seedInProgress", None)
        state.pop("seedStartId", None)
        state["seeded"] = True
        store.write_json(store.sequences_path, state)
