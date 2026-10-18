from fastapi import APIRouter

from app.config import Settings


def build_monitor_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["Monitor"])

    @router.get("/")
    def health_check() -> dict[str, str]:
        return {"name": settings.goapp_name, "version": settings.goapp_version}

    return router
