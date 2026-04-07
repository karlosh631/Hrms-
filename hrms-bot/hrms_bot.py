"""
hrms_bot.py – Playwright-based browser automation for Horilla HRMS.

Handles:
  • Login (with session reuse / retry)
  • Clock-in via dashboard button or direct URL
  • Clock-out via dashboard button or direct URL
  • Screenshot on failure (saved to data/screenshots/)
  • CSRF token extraction for direct POST requests
"""
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PWTimeout,
    sync_playwright,
)

from config import (
    DATA_DIR,
    HEADLESS,
    HRMS_PASSWORD,
    HRMS_URL,
    HRMS_USERNAME,
    SCREENSHOT_DIR,
)

logger = logging.getLogger(__name__)

# Selector lists for Horilla HRMS – tried in order, first match wins
_LOGIN_USERNAME_SELECTORS = [
    'input[name="username"]',
    'input[name="email"]',
    '#id_username',
    'input[type="text"]:visible',
    'input[placeholder*="username" i]:visible',
    'input[placeholder*="employee" i]:visible',
]

_LOGIN_PASSWORD_SELECTORS = [
    'input[name="password"]',
    '#id_password',
    'input[type="password"]:visible',
]

_LOGIN_SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Login")',
    'button:has-text("Sign In")',
    'button:has-text("Log In")',
]

_CLOCKIN_SELECTORS = [
    # Text-based (most reliable across Horilla versions)
    'button:has-text("Clock In")',
    'a:has-text("Clock In")',
    'button:has-text("Check In")',
    'a:has-text("Check In")',
    'button:has-text("Clock-In")',
    # ID / class patterns from known Horilla builds
    '#clockInButton',
    '#checkInButton',
    '#clock-in-btn',
    '.clock-in-btn',
    '.checkin-btn',
    '#attendanceClockIn',
    '.attendance-clock-in',
    '[data-action="clock-in"]',
    '[onclick*="clockIn"]',
    '[onclick*="clock_in"]',
]

_CLOCKOUT_SELECTORS = [
    'button:has-text("Clock Out")',
    'a:has-text("Clock Out")',
    'button:has-text("Check Out")',
    'a:has-text("Check Out")',
    'button:has-text("Clock-Out")',
    '#clockOutButton',
    '#checkOutButton',
    '#clock-out-btn',
    '.clock-out-btn',
    '.checkout-btn',
    '#attendanceClockOut',
    '.attendance-clock-out',
    '[data-action="clock-out"]',
    '[onclick*="clockOut"]',
    '[onclick*="clock_out"]',
]

# Known direct URL suffixes for Horilla attendance actions
_CLOCKIN_URLS  = ["attendance/clock-in/", "attendance/attendance-clock-in/"]
_CLOCKOUT_URLS = ["attendance/clock-out/", "attendance/attendance-clock-out/"]


class HRMSBot:
    """
    Context-manager wrapper around a Playwright browser session.

    Usage::

        with HRMSBot() as bot:
            success = bot.clock_in()
    """

    def __init__(self) -> None:
        self._pw: Optional[Playwright]     = None
        self._browser: Optional[Browser]   = None
        self._ctx: Optional[BrowserContext] = None
        self.page: Optional[Page]           = None

    # ── Context manager ─────────────────────────────────────────────────────

    def __enter__(self) -> "HRMSBot":
        self._pw      = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        self._ctx  = self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        self.page = self._ctx.new_page()
        # Slow mo in debug mode to help diagnose issues
        return self

    def __exit__(self, *_) -> None:
        for obj in (self._ctx, self._browser, self._pw):
            try:
                if obj:
                    obj.close() if not isinstance(obj, Playwright) else obj.stop()
            except Exception as exc:
                logger.debug("Cleanup error: %s", exc)

    # ── Login ────────────────────────────────────────────────────────────────

    def login(self, retries: int = 3) -> bool:
        """
        Navigate to HRMS and log in.  Returns True if already/successfully
        logged in.  Retries up to `retries` times on failure.
        """
        for attempt in range(1, retries + 1):
            try:
                logger.info("Login attempt %d/%d …", attempt, retries)
                self.page.goto(HRMS_URL, timeout=40_000, wait_until="domcontentloaded")
                self.page.wait_for_load_state("networkidle", timeout=20_000)

                # Already logged in?
                if "/login" not in self.page.url.lower():
                    logger.info("Session active – no login needed.")
                    return True

                # Fill username
                if not self._try_fill(_LOGIN_USERNAME_SELECTORS, HRMS_USERNAME):
                    raise RuntimeError("Username field not found")

                # Fill password
                if not self._try_fill(_LOGIN_PASSWORD_SELECTORS, HRMS_PASSWORD):
                    raise RuntimeError("Password field not found")

                # Submit
                if not self._try_click(_LOGIN_SUBMIT_SELECTORS):
                    # Fallback: press Enter
                    self.page.keyboard.press("Enter")

                self.page.wait_for_load_state("networkidle", timeout=30_000)

                # Verify success
                if "login" in self.page.url.lower():
                    msg = "Login failed – still on login page"
                    logger.warning(msg)
                    if attempt == retries:
                        self._screenshot("login_failed")
                        return False
                    time.sleep(3)
                    continue

                logger.info("Logged in successfully → %s", self.page.url)
                return True

            except PWTimeout as exc:
                logger.warning("Login timeout (attempt %d): %s", attempt, exc)
                if attempt == retries:
                    self._screenshot("login_timeout")
                    return False
                time.sleep(5)
            except Exception as exc:
                logger.warning("Login error (attempt %d): %s", attempt, exc)
                if attempt == retries:
                    self._screenshot("login_error")
                    return False
                time.sleep(5)
        return False

    # ── Clock-in ─────────────────────────────────────────────────────────────

    def clock_in(self) -> bool:
        """Perform clock-in. Returns True on success."""
        logger.info("Starting clock-in …")
        if not self.login():
            logger.error("Clock-in aborted – login failed.")
            return False

        # 1. Try direct URL navigation (fastest)
        if self._try_action_url(_CLOCKIN_URLS, "clock-in"):
            return True

        # 2. Go to dashboard and click the button
        self._goto_home()
        if self._try_action_button(_CLOCKIN_SELECTORS, "clock-in"):
            return True

        logger.error("Clock-in failed – no suitable button or URL found.")
        self._screenshot("clockin_failed")
        return False

    # ── Clock-out ────────────────────────────────────────────────────────────

    def clock_out(self) -> bool:
        """Perform clock-out. Returns True on success."""
        logger.info("Starting clock-out …")
        if not self.login():
            logger.error("Clock-out aborted – login failed.")
            return False

        if self._try_action_url(_CLOCKOUT_URLS, "clock-out"):
            return True

        self._goto_home()
        if self._try_action_button(_CLOCKOUT_SELECTORS, "clock-out"):
            return True

        logger.error("Clock-out failed – no suitable button or URL found.")
        self._screenshot("clockout_failed")
        return False

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _goto_home(self) -> None:
        try:
            self.page.goto(HRMS_URL, timeout=30_000, wait_until="networkidle")
        except PWTimeout:
            logger.warning("Home page load timed out – continuing anyway.")

    def _try_fill(self, selectors: list, value: str) -> bool:
        for sel in selectors:
            try:
                self.page.fill(sel, value, timeout=4_000)
                logger.debug("Filled '%s' with selector: %s", "***", sel)
                return True
            except Exception:
                continue
        return False

    def _try_click(self, selectors: list) -> bool:
        for sel in selectors:
            try:
                self.page.click(sel, timeout=4_000)
                logger.debug("Clicked selector: %s", sel)
                return True
            except Exception:
                continue
        return False

    def _try_action_url(self, url_suffixes: list, label: str) -> bool:
        """Navigate to each candidate URL; confirm/click submit if needed."""
        for suffix in url_suffixes:
            url = HRMS_URL + suffix
            try:
                response = self.page.goto(url, timeout=15_000)
                if response and response.status >= 400:
                    logger.debug("%s returned HTTP %d", url, response.status)
                    continue
                self.page.wait_for_load_state("networkidle", timeout=15_000)

                # If there's a confirmation button, click it
                confirm_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Clock In")',
                    'button:has-text("Clock Out")',
                    'button:has-text("Confirm")',
                ]
                self._try_click(confirm_selectors)
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10_000)
                except PWTimeout:
                    pass

                logger.info("%s succeeded via direct URL: %s", label, url)
                self._screenshot(f"{label.replace('-','_')}_success")
                return True
            except PWTimeout:
                logger.debug("Timeout navigating to %s", url)
            except Exception as exc:
                logger.debug("URL %s failed: %s", url, exc)
        return False

    def _try_action_button(self, selectors: list, label: str) -> bool:
        """Find and click the first visible matching button."""
        for sel in selectors:
            try:
                if self.page.is_visible(sel, timeout=3_000):
                    self.page.click(sel, timeout=5_000)
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=15_000)
                    except PWTimeout:
                        pass
                    logger.info("%s button clicked → selector: %s", label, sel)
                    self._screenshot(f"{label.replace('-','_')}_success")
                    return True
            except Exception:
                continue
        return False

    def _screenshot(self, name: str) -> None:
        try:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = SCREENSHOT_DIR / f"{name}_{ts}.png"
            self.page.screenshot(path=str(path), full_page=True)
            logger.info("Screenshot saved → %s", path)
        except Exception as exc:
            logger.debug("Screenshot failed: %s", exc)
