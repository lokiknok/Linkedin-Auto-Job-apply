import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from config import DATA_DIR
from telegram.notifier import telegram_notifier

logger = logging.getLogger("browser")

USER_DATA_DIR = DATA_DIR / "browser_profile"


class LinkedInBrowser:
    """Manages the headed Playwright browser instance, authentication state, and safety checks."""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_running = False
        self._is_logged_in = False
        self._status_message = "Browser not started"
        self._active_task = "Idle"
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running and self._context is not None

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "is_logged_in": self._is_logged_in,
            "status_message": self._status_message,
            "active_task": self._active_task,
            "current_url": self._page.url if self._page and not self._page.is_closed() else None,
        }

    def set_status(self, message: str, task: Optional[str] = None):
        self._status_message = message
        if task is not None:
            self._active_task = task
        logger.info(f"[Browser Status] {message} (Task: {self._active_task})")

    async def start(self, headless: bool = False) -> Dict[str, Any]:
        """Launches a headed Chromium browser with persistent profile storage."""
        async with self._lock:
            if self.is_running:
                return {"success": True, "message": "Browser is already running.", "status": self.status}

            try:
                self.set_status("Starting browser...", "Initializing")
                USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

                self._playwright = await async_playwright().start()
                
                # Launch persistent context to preserve cookies and login state
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(USER_DATA_DIR),
                    headless=headless,
                    viewport={"width": 1280, "height": 800},
                    args=[
                        "--start-maximized",
                        "--disable-blink-features=AutomationControlled",
                    ],
                    ignore_default_args=["--enable-automation"]
                )

                if self._context.pages:
                    self._page = self._context.pages[0]
                else:
                    self._page = await self._context.new_page()

                self._is_running = True
                self.set_status("Browser started", "Navigating to LinkedIn")

                # Navigate to LinkedIn
                await self._page.goto("https://www.linkedin.com/", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                # Check initial login state
                await self.check_login_status()

                return {"success": True, "message": "Browser started successfully.", "status": self.status}

            except Exception as e:
                logger.error(f"Failed to start browser: {e}")
                self._status_message = f"Failed to start: {str(e)}"
                await self._cleanup()
                return {"success": False, "message": str(e), "status": self.status}

    async def check_login_status(self) -> bool:
        """Checks whether the user is logged in to LinkedIn."""
        if not self._page or self._page.is_closed():
            self._is_logged_in = False
            return False

        try:
            url = self._page.url.lower()

            # If user is on feed or jobs or user profile, user IS logged in!
            if (
                "linkedin.com/feed" in url
                or "linkedin.com/jobs" in url
                or "linkedin.com/in/" in url
                or "linkedin.com/mynetwork" in url
            ):
                self._is_logged_in = True
                self.set_status("LinkedIn Logged In & Ready", "Ready")
                return True

            # Check for global navigation bar or profile icon selector in DOM
            nav_bar = await self._page.query_selector("header.global-nav, .global-nav__me-photo, nav.global-nav, #global-nav")
            if nav_bar:
                self._is_logged_in = True
                self.set_status("LinkedIn Logged In & Ready", "Ready")
                return True

            # Check for true security challenge (CAPTCHA / PIN challenge)
            if await self.check_security_checkpoint():
                self._is_logged_in = False
                return False

            # If on login / signup page
            if "login" in url or "signup" in url or "uas/login" in url or "authwall" in url:
                self._is_logged_in = False
                self.set_status("Please log into LinkedIn in the browser window", "Awaiting Manual Login")
                return False

            # Check sign-in button presence
            signin_btn = await self._page.query_selector("a[href*='login'], a.nav__button-secondary")
            if signin_btn:
                self._is_logged_in = False
                self.set_status("Please log into LinkedIn in the browser window", "Awaiting Manual Login")
                return False

            # Default: check for feed containers
            feed_elem = await self._page.query_selector(".share-box-feed-entry__wrapper, div[data-view-name='profile-card']")
            if feed_elem:
                self._is_logged_in = True
                self.set_status("LinkedIn Logged In & Ready", "Ready")
                return True

            self._is_logged_in = False
            self.set_status("Awaiting user login in browser", "Awaiting Manual Login")
            return False

        except Exception as e:
            logger.debug(f"Login check error: {e}")
            self._is_logged_in = False
            return False

    async def check_security_checkpoint(self) -> bool:
        """Detects if a real CAPTCHA, verification pin, or security challenge is actively displayed."""
        if not self._page or self._page.is_closed():
            return False

        try:
            url = self._page.url.lower()

            # Ignore normal login / redirect paths
            if "checkpoint/lg/login" in url or "uas/login" in url:
                return False

            # Specific challenge checkpoint patterns
            challenge_patterns = ["/checkpoint/challenge/", "/security-check", "arkoselabs", "recaptcha"]
            if any(p in url for p in challenge_patterns):
                logger.warning(f"Security challenge detected on URL: {url}")
                self.set_status("Security verification / CAPTCHA detected. Please complete it in browser.", "PAUSED - Security Check")
                telegram_notifier.notify_captcha_detected()
                return True

            # Check for captcha frame or modal in DOM
            captcha_elem = await self._page.query_selector(
                "iframe[src*='captcha'], iframe[src*='arkoselabs'], #captcha-internal, div[data-test-challenge-dialog]"
            )
            if captcha_elem:
                logger.warning("Security verification element detected in DOM.")
                self.set_status("Security verification / CAPTCHA detected. Complete it in browser.", "PAUSED - Security Check")
                telegram_notifier.notify_captcha_detected()
                return True

            return False
        except Exception as e:
            logger.debug(f"Error checking security checkpoint: {e}")
            return False

    async def resume_session(self) -> Dict[str, Any]:
        """Manually re-verifies login status and resumes automation."""
        if not self.is_running:
            return await self.start()

        is_logged = await self.check_login_status()
        if is_logged:
            self.set_status("Session verified and active!", "Ready")
            return {"success": True, "message": "Login verified! Ready to search and prepare jobs.", "status": self.status}
        else:
            page = await self.get_page()
            curr_url = page.url if page else ""
            return {
                "success": False,
                "message": "Login not detected yet. Please complete login or CAPTCHA in the browser window.",
                "current_url": curr_url,
                "status": self.status
            }

    async def get_page(self) -> Optional[Page]:
        """Returns the active page, opening a new one if closed."""
        if not self.is_running:
            start_res = await self.start()
            if not start_res["success"]:
                return None

        if self._page is None or self._page.is_closed():
            if self._context:
                self._page = await self._context.new_page()
            else:
                return None

        return self._page

    async def navigate_to(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000) -> bool:
        """Safely navigates to a URL with error handling and security detection."""
        page = await self.get_page()
        if not page:
            return False

        try:
            self.set_status(f"Navigating to {url}", "Navigating")
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            await asyncio.sleep(1.5)

            if await self.check_security_checkpoint():
                return False

            await self.check_login_status()
            return True
        except PlaywrightTimeoutError:
            logger.warning(f"Timeout navigating to {url}")
            self.set_status(f"Timeout loading {url}", "Error")
            return False
        except Exception as e:
            logger.error(f"Navigation error for {url}: {e}")
            self.set_status(f"Error navigating: {str(e)}", "Error")
            return False

    async def stop(self) -> Dict[str, Any]:
        """Stops the browser and cleans up resources."""
        async with self._lock:
            await self._cleanup()
            self.set_status("Browser closed", "Idle")
            return {"success": True, "message": "Browser stopped.", "status": self.status}

    async def _cleanup(self):
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
        except Exception:
            pass

        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._playwright = None
        self._is_running = False
        self._is_logged_in = False


# Global singleton browser manager
browser_manager = LinkedInBrowser()

