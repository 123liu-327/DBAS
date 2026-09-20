from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import StoreDep
from app.core.responses import ApiResponse, ok
from app.schemas.bill import MonthlyShares
from app.services import bill_service

router = APIRouter(prefix="/books/{bookId}/statistics", tags=["统计"])
BookId = Annotated[int, Path(alias="bookId", gt=0)]
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


@router.get("/member-shares", response_model=ApiResponse[MonthlyShares])
def month_shares(book_id: BookId, store: StoreDep, month: Month) -> ApiResponse[MonthlyShares]:
    return ok(bill_service.monthly_shares(store, book_id, month))
