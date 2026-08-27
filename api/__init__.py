from api.jobs import router as jobs_router
from api.applications import router as applications_router
from api.settings import router as settings_router
from api.browser_routes import router as browser_router
from api.telegram_routes import router as telegram_router

__all__ = [
    "jobs_router",
    "applications_router",
    "settings_router",
    "browser_router",
    "telegram_router",
]

