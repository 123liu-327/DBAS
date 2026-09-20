"""File-based persistence primitives. No business CRUD rules belong here."""

import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from threading import Lock
from typing import Any, TypeVar
from uuid import uuid4

from filelock import FileLock

T = TypeVar("T")


class StorageError(Exception):
    """A data file is invalid or a read/write operation failed."""


class FileStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir.resolve()
        self._lock_cache: dict[str, FileLock] = {}
        self._lock_cache_guard = Lock()

    @property
    def sequences_path(self) -> Path:
        return self.root / "sequences.json"

    @property
    def members_path(self) -> Path:
        return self.root / "members.json"

    @property
    def books_dir(self) -> Path:
        return self.root / "books"

    def book_dir(self, book_id: int) -> Path:
        self._validate_book_id(book_id)
        return self.books_dir / str(book_id)

    def book_path(self, book_id: int) -> Path:
        return self.book_dir(book_id) / "book.json"

    def stays_path(self, book_id: int) -> Path:
        return self.book_dir(book_id) / "stays.json"

    def bills_path(self, book_id: int) -> Path:
        return self.book_dir(book_id) / "bills.jsonl"

    def settlements_path(self, book_id: int) -> Path:
        return self.book_dir(book_id) / "settlements.jsonl"

    def attachments_dir(self, book_id: int) -> Path:
        return self.book_dir(book_id) / "attachments"

    def attachment_path(self, book_id: int, relative_path: str) -> Path:
        target = self._checked_path(self.book_dir(book_id) / relative_path)
        if not target.is_relative_to(self.attachments_dir(book_id).resolve()):
            raise ValueError("附件路径必须位于当前账本的附件目录内")
        return target

    def book_lock(self, book_id: int) -> FileLock:
        """Serialize a multi-file operation within one book."""
        return self._lock(book_id)

    def index_lock(self) -> FileLock:
        return self._lock(None)

    def read_json(self, path: Path, *, default: T | None = None) -> Any | T:
        target = self._checked_path(path)
        if not target.exists():
            return default
        try:
            with target.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StorageError(f"Cannot read JSON file: {target}") from exc

    def read_jsonl(self, path: Path) -> list[Any]:
        target = self._checked_path(path)
        if not target.exists():
            return []
        try:
            with target.open("r", encoding="utf-8") as stream:
                return [json.loads(line) for line in stream if line.strip()]
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StorageError(f"Cannot read JSONL file: {target}") from exc

    def write_json(self, path: Path, value: Any, *, book_id: int | None = None) -> None:
        target = self._checked_path(path)
        self._check_lock_scope(target, book_id)
        with self._lock(book_id):
            self._atomic_write(target, self._serialize_json(value))

    def write_jsonl(
        self, path: Path, records: Iterable[Any], *, book_id: int | None = None
    ) -> None:
        target = self._checked_path(path)
        self._check_lock_scope(target, book_id)
        with self._lock(book_id):
            self._atomic_write(target, self._serialize_jsonl(records))

    def write_attachment(self, book_id: int, relative_path: str, contents: bytes) -> Path:
        target = self.attachment_path(book_id, relative_path)
        with self.book_lock(book_id):
            self._atomic_write_bytes(target, contents)
        return target

    def update_json(
        self, path: Path, transform: Callable[[Any], T], *, default: Any, book_id: int | None = None
    ) -> T:
        target = self._checked_path(path)
        self._check_lock_scope(target, book_id)
        with self._lock(book_id):
            updated = transform(self.read_json(target, default=default))
            self._atomic_write(target, self._serialize_json(updated))
            return updated

    def update_jsonl(
        self, path: Path, transform: Callable[[list[Any]], list[T]], *, book_id: int | None = None
    ) -> list[T]:
        target = self._checked_path(path)
        self._check_lock_scope(target, book_id)
        with self._lock(book_id):
            updated = transform(self.read_jsonl(target))
            self._atomic_write(target, self._serialize_jsonl(updated))
            return updated

    def _lock(self, book_id: int | None) -> FileLock:
        if book_id is not None:
            self._validate_book_id(book_id)
        lock_name = "books-index.lock" if book_id is None else f"book-{book_id}.lock"
        lock_path = self.root / ".locks" / lock_name
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_cache_guard:
            if lock_name not in self._lock_cache:
                self._lock_cache[lock_name] = FileLock(str(lock_path), timeout=10)
            return self._lock_cache[lock_name]

    def _checked_path(self, path: Path) -> Path:
        target = path.resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("数据路径必须位于配置的数据目录内")
        return target

    def _check_lock_scope(self, target: Path, book_id: int | None) -> None:
        if book_id is None:
            if target not in {self.sequences_path, self.members_path}:
                raise ValueError("写入账本数据文件时必须提供账本 ID")
        elif target.parent != self.book_dir(book_id):
            raise ValueError("账本 ID 必须与正在写入的数据文件一致")

    @staticmethod
    def _validate_book_id(book_id: int) -> None:
        if isinstance(book_id, bool) or not isinstance(book_id, int) or book_id <= 0:
            raise ValueError("账本 ID 无效")

    def publish_book(self, book_id: int, record: dict[str, Any]) -> None:
        """Make a complete empty book visible with one directory rename."""
        directory = self.book_dir(book_id)
        self.books_dir.mkdir(parents=True, exist_ok=True)
        pending = self.books_dir / f".pending-{book_id}-{uuid4().hex}"
        if not pending.resolve().is_relative_to(self.books_dir.resolve()):
            raise ValueError("暂存目录超出数据根目录")
        try:
            pending.mkdir()
            self._atomic_write(pending / "book.json", self._serialize_json(record))
            self._atomic_write(pending / "stays.json", self._serialize_json({"stays": []}))
            self._atomic_write(pending / "bills.jsonl", "")
            (pending / "attachments").mkdir()
            if directory.exists():
                raise FileExistsError(f"Book directory already exists: {directory}")
            os.replace(pending, directory)
        finally:
            if pending.exists():
                if not pending.resolve().is_relative_to(self.books_dir.resolve()):
                    raise ValueError("暂存目录超出数据根目录")
                shutil.rmtree(pending)

    def cleanup_pending_books(self) -> None:
        if not self.books_dir.exists():
            return
        for pending in self.books_dir.glob(".pending-*"):
            if pending.is_dir():
                if not pending.resolve().is_relative_to(self.books_dir.resolve()):
                    raise ValueError("暂存目录超出数据根目录")
                shutil.rmtree(pending)

    @staticmethod
    def _serialize_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"

    @classmethod
    def _serialize_jsonl(cls, records: Iterable[Any]) -> str:
        return "".join(cls._serialize_json(record) for record in records)

    @staticmethod
    def _atomic_write(target: Path, contents: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=target.parent,
                prefix=f".{target.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            raise StorageError(f"Cannot write data file: {target}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _atomic_write_bytes(target: Path, contents: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=f".{target.name}.",
                suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            raise StorageError(f"Cannot write attachment: {target}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
