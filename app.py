import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import env_settings, BASE_DIR, logger
from database.database import init_db
from api import (
    jobs_router,
    applications_router,
    settings_router,
    browser_router,
    telegram_router
)
from telegram.notifier import telegram_notifier
from browser.linkedin_browser import browser_manager

FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle manager."""
    # Startup
    logger.info("Initializing LinkedIn Job Application Assistant...")
    init_db()

    # Start Telegram background command listener if configured
    if telegram_notifier.is_configured:
        telegram_notifier.start_polling()
    else:
        logger.info("Telegram notifications not configured. Running in local mode.")

    logger.info(f"Server ready at http://{env_settings.HOST}:{env_settings.PORT}")
    yield

    # Shutdown
    logger.info("Shutting down assistant...")
    telegram_notifier.stop_polling()
    if browser_manager.is_running:
        await browser_manager.stop()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=env_settings.APP_NAME,
    description="Human-in-the-loop LinkedIn job application assistant using Python, Playwright, and Telegram alerts.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(settings_router)
app.include_router(browser_router)
app.include_router(telegram_router)

# Mount Static Files (CSS, JS)
if FRONTEND_DIR.exists():
    css_dir = FRONTEND_DIR / "css"
    js_dir = FRONTEND_DIR / "js"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")


# SPA Route Handlers
@app.get("/", response_class=FileResponse)
async def serve_root():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(index_file)


@app.get("/dashboard", response_class=FileResponse)
@app.get("/jobs", response_class=FileResponse)
@app.get("/applications", response_class=FileResponse)
@app.get("/settings", response_class=FileResponse)
async def serve_spa_pages():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(index_file)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "browser_running": browser_manager.is_running,
        "telegram_configured": telegram_notifier.is_configured
    }


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=env_settings.HOST,
        port=env_settings.PORT,
        reload=False,
        log_level="info"
    )

