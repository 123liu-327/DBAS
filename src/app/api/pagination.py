"""Validated HTTP pagination parameters."""

from typing import Annotated

from fastapi import Depends, Query

from app.schemas.common import PageParams

PageQuery = Annotated[int, Query(ge=1)]
PageSizeQuery = Annotated[int, Query(alias="pageSize", ge=1, le=100)]


def page_params(page: PageQuery = 1, page_size: PageSizeQuery = 10) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PageDep = Annotated[PageParams, Depends(page_params)]
