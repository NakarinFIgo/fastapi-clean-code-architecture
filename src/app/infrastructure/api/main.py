from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.infrastructure.api.errors import install_error_handlers
from app.infrastructure.db.mongo import build_mongo_database
from app.infrastructure.db.postgres import build_session_factory
from app.interface.handlers.crud import build_crud_router
from app.interface.handlers.monitor import build_monitor_router
from app.interface.handlers.user import build_user_router

REPO_ROOT = Path(__file__).resolve().parents[4]


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title=settings.goapp_name, version=settings.goapp_version)
    app.state.settings = settings
    app.state.session_factory = session_factory or build_session_factory(settings.postgres_url)
    app.state.mongo_db = build_mongo_database(
        settings.goapp_mongodb_db_atlas_uri, settings.goapp_mongodb_db_name
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "HEAD", "PUT", "DELETE", "PATCH"],
        allow_headers=[],
        allow_credentials=False,
    )
    install_error_handlers(app)

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(build_monitor_router(settings))
    api_v1.include_router(build_user_router())
    api_v1.include_router(build_crud_router())
    app.include_router(api_v1)

    dist = (
        Path(settings.goapp_frontend_dist)
        if settings.goapp_frontend_dist
        else (REPO_ROOT / "frontend" / "dist")
    )
    if dist.is_dir():  # the API keeps working when the frontend has not been built
        app.mount("/ui", StaticFiles(directory=dist, html=True), name="ui")
    return app
