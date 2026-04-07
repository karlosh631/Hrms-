"""
hrms_bot.py – Playwright-based automation for https://hrms.technimus.com/

Performs login and clock-in / clock-out actions with retry logic and
proper error handling for slow loads, session expiry, and element failures.
"""

import logging
import os
import time
from typing import Literal

from dotenv import load_dotenv  # type: ignore

load_dotenv()

logger = logging.getLogger(__name__)

HRMS_URL: str = "https://hrms.technimus.com/"
LOGIN_TIMEOUT: int = 30_000   # ms
ACTION_TIMEOUT: int = 20_000  # ms
MAX_LOGIN_RETRIES: int = 3


ActionType = Literal["clock_in", "clock_out"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def perform_action(action: ActionType) -> bool:
    """
    Open the HRMS portal, log in, and execute *action*.

    Returns True on success, raises on unrecoverable failure.
    """
    username = os.getenv("HRMS_USERNAME", "")
    password = os.getenv("HRMS_PASSWORD", "")

    if not username or not password:
        raise EnvironmentError(
            "HRMS_USERNAME and HRMS_PASSWORD must be set in the environment / .env file."
        )

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # type: ignore

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)

        try:
            _login(page, username, password)
            if action == "clock_in":
                _clock_in(page)
            else:
                _clock_out(page)
            logger.info("Action '%s' completed successfully.", action)
            return True
        except PWTimeout as exc:
            logger.error("Timeout during '%s': %s", action, exc)
            raise
        except Exception as exc:
            logger.error("Error during '%s': %s", action, exc)
            raise
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _login(page, username: str, password: str) -> None:
    """Navigate to HRMS and log in.  Retries up to MAX_LOGIN_RETRIES times."""
    from playwright.sync_api import TimeoutError as PWTimeout  # type: ignore

    for attempt in range(1, MAX_LOGIN_RETRIES + 1):
        try:
            logger.info("Login attempt %d/%d …", attempt, MAX_LOGIN_RETRIES)
            page.goto(HRMS_URL, wait_until="domcontentloaded", timeout=LOGIN_TIMEOUT)

            # If already logged in (dashboard visible), skip login form
            if _is_dashboard(page):
                logger.info("Session still active – skipping login form.")
                return

            # Fill credentials
            page.wait_for_selector("input[type='text'], input[name='username'], input[id*='user']",
                                   timeout=LOGIN_TIMEOUT)
            _fill_login_form(page, username, password)

            # Wait for redirect to dashboard / home
            page.wait_for_url(lambda url: url != HRMS_URL and "login" not in url.lower(),
                               timeout=LOGIN_TIMEOUT)
            if _is_dashboard(page):
                logger.info("Login successful.")
                return

        except PWTimeout:
            if attempt == MAX_LOGIN_RETRIES:
                raise
            logger.warning("Login timeout – retrying in 5 s …")
            time.sleep(5)


def _fill_login_form(page, username: str, password: str) -> None:
    """Locate and fill the login form inputs."""
    # Username field – try several selectors in priority order
    for sel in [
        "input[name='username']",
        "input[id*='user']",
        "input[type='text']:first-of-type",
        "input[placeholder*='user' i]",
        "input[placeholder*='email' i]",
    ]:
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.fill(username)
            break

    # Password field
    for sel in [
        "input[type='password']",
        "input[name='password']",
        "input[id*='pass']",
    ]:
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.fill(password)
            break

    # Submit
    for sel in [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Sign in')",
        "button:has-text('Log in')",
    ]:
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.click()
            return

    # Last resort – press Enter in the password field
    page.keyboard.press("Enter")


def _is_dashboard(page) -> bool:
    """Return True if the current page looks like the HRMS dashboard."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(page.url)
        host = parsed.netloc.lower()
        # Ensure the host is exactly hrms.technimus.com (not a subdomain trick)
        return (
            parsed.scheme in ("http", "https")
            and (host == "hrms.technimus.com" or host == "www.hrms.technimus.com")
            and "login" not in parsed.path.lower()
            and page.url.rstrip("/").lower() != HRMS_URL.rstrip("/").lower()
        )
    except Exception:
        return False


def _navigate_to_attendance(page) -> None:
    """Ensure the attendance / dashboard page is visible."""
    url = page.url.lower()
    attendance_keywords = ["attendance", "dashboard", "home"]
    if not any(kw in url for kw in attendance_keywords):
        # Try clicking an attendance menu item
        for sel in [
            "a:has-text('Attendance')",
            "a:has-text('Dashboard')",
            "[href*='attendance']",
            "[href*='dashboard']",
        ]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.wait_for_load_state("domcontentloaded", timeout=ACTION_TIMEOUT)
                break


def _clock_in(page) -> None:
    """Click the clock-in button."""
    _navigate_to_attendance(page)
    logger.info("Performing clock-in …")

    selectors = [
        "button:has-text('Clock In')",
        "button:has-text('Check In')",
        "a:has-text('Clock In')",
        "[class*='clock-in']",
        "[id*='clock_in']",
        "[class*='checkin']",
        "button:has-text('In')",
    ]
    _click_action_button(page, selectors, "clock-in")


def _clock_out(page) -> None:
    """Click the clock-out button."""
    _navigate_to_attendance(page)
    logger.info("Performing clock-out …")

    selectors = [
        "button:has-text('Clock Out')",
        "button:has-text('Check Out')",
        "a:has-text('Clock Out')",
        "[class*='clock-out']",
        "[id*='clock_out']",
        "[class*='checkout']",
        "button:has-text('Out')",
    ]
    _click_action_button(page, selectors, "clock-out")


def _click_action_button(page, selectors: list, label: str) -> None:
    """Try each selector in turn; raise if none matches."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                # Brief wait for any confirmation dialog / toast
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except Exception:
                    pass
                logger.info("Clicked '%s' via selector: %s", label, sel)
                return
        except Exception:
            continue

    raise RuntimeError(
        f"Could not find a clickable '{label}' button on the page. "
        f"Tried selectors: {selectors}"
    )
