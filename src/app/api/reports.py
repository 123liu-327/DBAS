from typing import Annotated

from fastapi import APIRouter, Path, Query
from fastapi.responses import Response

from app.api.deps import StoreDep
from app.core.responses import ApiResponse, ok
from app.schemas.report import MONTH_PATTERN, MonthlyTrend, SettlementPlan, SettlementRange
from app.services import report_service, settlement_service

router = APIRouter(prefix="/books/{bookId}", tags=["结算与导出"])
BookId = Annotated[int, Path(alias="bookId", gt=0)]
Month = Annotated[str, Query(pattern=MONTH_PATTERN)]
OptionalMonth = Annotated[str | None, Query(alias="endMonth", pattern=MONTH_PATTERN)]


@router.post("/settlement-plans", response_model=ApiResponse[SettlementPlan])
def settlement_plan(
    book_id: BookId, period: SettlementRange, store: StoreDep
) -> ApiResponse[SettlementPlan]:
    return ok(settlement_service.settlement_plan(store, book_id, period))


@router.get("/statistics/monthly", response_model=ApiResponse[list[MonthlyTrend]])
def monthly_trend(
    book_id: BookId, store: StoreDep, end_month: OptionalMonth = None
) -> ApiResponse[list[MonthlyTrend]]:
    return ok(report_service.monthly_trend(store, book_id, end_month))


@router.get("/exports/bills.csv")
def export_bills(book_id: BookId, store: StoreDep, month: Month) -> Response:
    contents = report_service.export_csv(store, book_id, month)
    return Response(
        content=contents.encode("utf-8"), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="export_{month}.csv"'},
    )
