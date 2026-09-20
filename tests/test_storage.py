from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from app.storage import FileStore, StorageError


def increment_in_process(root: str) -> None:
    store = FileStore(Path(root))
    store.update_json(
        store.stays_path(1),
        lambda data: {"count": data["count"] + 1},
        default={"count": 0},
        book_id=1,
    )


def test_books_use_separate_paths(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    store.write_json(store.stays_path(1), {"stays": [1]}, book_id=1)
    store.write_json(store.stays_path(2), {"stays": [2]}, book_id=2)
    assert store.read_json(store.stays_path(1)) == {"stays": [1]}
    assert store.read_json(store.stays_path(2)) == {"stays": [2]}
    with pytest.raises(ValueError):
        store.book_dir("../escape")
    with pytest.raises(ValueError):
        store.read_json(tmp_path.parent / "outside.json")
    with pytest.raises(ValueError):
        store.write_json(store.stays_path(1), {}, book_id=2)


def test_jsonl_round_trip(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    path = store.bills_path(1)
    store.write_jsonl(path, [{"id": "b1"}, {"id": "b2"}], book_id=1)
    assert store.read_jsonl(path) == [{"id": "b1"}, {"id": "b2"}]


def test_five_processes_update_without_lost_writes(tmp_path: Path) -> None:
    with ProcessPoolExecutor(max_workers=5) as executor:
        list(executor.map(increment_in_process, [str(tmp_path)] * 5))
    store = FileStore(tmp_path)
    assert store.read_json(store.stays_path(1)) == {"count": 5}


def test_failed_replace_keeps_old_file(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    path = store.bills_path(1)
    store.write_jsonl(path, [{"id": "original"}], book_id=1)
    with patch("app.storage.files.os.replace", side_effect=OSError("interrupted")):
        with pytest.raises(StorageError):
            store.write_jsonl(path, [{"id": "new"}], book_id=1)
    assert store.read_jsonl(path) == [{"id": "original"}]
    assert not list(path.parent.glob("*.tmp"))
