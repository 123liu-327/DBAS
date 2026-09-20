from typing import Annotated

from fastapi import Depends, Request

from app.storage import FileStore


def get_store(request: Request) -> FileStore:
    return request.app.state.store


StoreDep = Annotated[FileStore, Depends(get_store)]
