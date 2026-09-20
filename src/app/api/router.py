from fastapi import APIRouter

from app.api import attachments, bills, books, members, reports, statistics, stays

api_router = APIRouter()
api_router.include_router(books.router)
api_router.include_router(members.router)
api_router.include_router(stays.router)
api_router.include_router(bills.router)
api_router.include_router(statistics.router)
api_router.include_router(reports.router)
api_router.include_router(attachments.router)
