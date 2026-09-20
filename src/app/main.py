"""FastAPI app factory and development entry point."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

if __name__ == "__main__" and not __package__:
    # Direct script execution must prefer this project's app over an installed namesake.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ruff: noqa: E402
from app.api.router import api_router
from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.core.responses import ApiResponse, ok
from app.schemas.health import HealthData
from app.services.bootstrap import prepare_member_storage, seed_demo_books
from app.storage import FileStore


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        prepare_member_storage(application.state.store)
        if config.seed_demo_books:
            seed_demo_books(application.state.store)
        yield

    application = FastAPI(title=config.app_name, version="0.1.0", lifespan=lifespan)
    application.state.settings = config
    application.state.store = FileStore(config.data_dir)
    register_exception_handlers(application)
    application.include_router(api_router, prefix=config.api_prefix)

    @application.get("/health", response_model=ApiResponse[HealthData], tags=["系统"])
    def health() -> ApiResponse[HealthData]:
        return ok(HealthData(status="ok"))

    return application


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
