"""Six-month trends and CSV export derived from posted bills."""

import calendar
import csv
from datetime import date
from io import StringIO

from app.algorithms.splitting import overlap_days
from app.crud import members as member_crud
from app.schemas.report import MonthlyTrend
from app.services.bill_service import posted_bills
from app.services.splitting_service import calculate_shares, stay_map
from app.storage import FileStore

CSV_HEADER = [
    "bill_id", "title", "bill_date", "payer_name", "amount_cents", "method",
    "participant_name", "share_cents",
]


def _shift_month(month: str, delta: int) -> str:
    year, number = map(int, month.split("-"))
    absolute = year * 12 + number - 1 + delta
    return f"{absolute // 12:04d}-{absolute % 12 + 1:02d}"


def monthly_trend(store: FileStore, book_id: int, end_month: str | None) -> list[MonthlyTrend]:
    end_month = end_month or date.today().strftime("%Y-%m")
    stays = stay_map(store, book_id)
    totals = {_shift_month(end_month, offset): 0 for offset in range(-5, 1)}
    for bill in posted_bills(store, book_id, min(totals), end_month):
        totals[bill.date.strftime("%Y-%m")] += bill.amount_cents
    result = []
    for month, total in sorted(totals.items()):
        year, number = map(int, month.split("-"))
        start = date(year, number, 1)
        end = date(year, number, calendar.monthrange(year, number)[1])
        residents = sum(overlap_days(start, end, stay) > 0 for stay in stays.values())
        per_capita = (total * 2 + residents) // (2 * residents) if residents else 0
        result.append(MonthlyTrend(month=month, total_cents=total,
                                   per_capita_cents=per_capita))
    return result


def export_csv(store: FileStore, book_id: int, month: str) -> str:
    stays = stay_map(store, book_id)
    members = {
        member_id: member_crud.require_member(store, member_id) for member_id in stays
    }
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(CSV_HEADER)
    for bill in posted_bills(store, book_id, month, month):
        for item in calculate_shares(bill, stays):
            writer.writerow([
                bill.id, bill.title, bill.date.isoformat(), members[bill.payer_id].name,
                bill.amount_cents, bill.method.value, members[item.member_id].name,
                item.share_cents,
            ])
    return output.getvalue()
