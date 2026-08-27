import logging
from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel
from browser.linkedin_browser import browser_manager

logger = logging.getLogger("api.browser")
router = APIRouter(prefix="/api/browser", tags=["Browser"])


class BrowserStartRequest(BaseModel):
    headless: bool = False


@router.get("/status", response_model=Dict[str, Any])
async def get_browser_status():
    """Returns current headed browser status, active URL, and login detection."""
    if browser_manager.is_running:
        await browser_manager.check_login_status()
    return browser_manager.status


@router.post("/start", response_model=Dict[str, Any])
async def start_browser(req: BrowserStartRequest):
    """Starts the Playwright headed browser instance."""
    return await browser_manager.start(headless=req.headless)


@router.post("/stop", response_model=Dict[str, Any])
async def stop_browser():
    """Stops the Playwright browser instance."""
    return await browser_manager.stop()


@router.post("/resume", response_model=Dict[str, Any])
async def resume_browser_session():
    """Re-verifies login state and clears paused CAPTCHA status."""
    return await browser_manager.resume_session()


