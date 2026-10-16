import logging
import os
import sys
from weakref import WeakKeyDictionary

from playwright.sync_api import Browser
from pytest import FixtureRequest

logger = logging.getLogger(__name__)

_BROWSER_FIXTURE_NAMES = ("browser", "context", "page", "new_context")
_snapshot_platform_by_browser: WeakKeyDictionary[Browser, str] = WeakKeyDictionary()


def _playwright_inspector_enabled() -> bool:
    # PWDEBUG=1 pauses the first page call. console logging does not.
    mode = os.environ.get("PWDEBUG", "")
    return mode not in ("", "0", "false", "console")


def platform_suffix_from_chromium_user_agent(user_agent: str) -> str:
    """Map a Chromium user agent onto the snapshot OS suffix.

    `linux`, `darwin`, and `win32` are the `sys.platform` values existing
    baselines already use. Chrome OS reports `CrOS` and uses `linux`.
    """
    if "Windows" in user_agent:
        return "win32"

    if "Macintosh" in user_agent or "Mac OS" in user_agent:
        return "darwin"

    if "Linux" in user_agent or "CrOS" in user_agent:
        return "linux"

    raise AssertionError(f"unknown chromium user agent {user_agent}")


def platform_suffix_from_navigator_platform(navigator_platform: str) -> str:
    """Map `navigator.platform` onto the snapshot OS suffix."""
    if navigator_platform.startswith("Linux"):
        return "linux"

    if navigator_platform.startswith("Mac"):
        return "darwin"

    if navigator_platform.startswith("Win"):
        return "win32"

    raise AssertionError(f"unknown browser platform {navigator_platform}")


def _chromium_snapshot_platform(browser: Browser) -> str:
    # Browser.getVersion is the browser process, so connect() and connect_over_cdp
    # report the machine running Chrome rather than the pytest host.
    session = browser.new_browser_cdp_session()
    try:
        version = session.send("Browser.getVersion")
    finally:
        session.detach()

    user_agent = version["userAgent"]
    assert isinstance(user_agent, str)

    return platform_suffix_from_chromium_user_agent(user_agent)


def _navigator_snapshot_platform(browser: Browser) -> str:
    # WebKit's user agent says Macintosh on Linux. The page platform does not.
    page = browser.new_page()
    try:
        navigator_platform = page.evaluate("() => navigator.platform")
    finally:
        page.close()

    assert isinstance(navigator_platform, str)

    return platform_suffix_from_navigator_platform(navigator_platform)


def browser_snapshot_platform(browser: Browser) -> str:
    """OS suffix for the browser that renders snapshots.

    Chromium is read over CDP, including a remote Playwright or DevTools
    connection. Firefox and WebKit read `navigator.platform` in that browser.
    `PWDEBUG` uses the pytest host OS. That mode is for a browser on the host.
    """
    cached = _snapshot_platform_by_browser.get(browser)
    if cached is not None:
        return cached

    # PWDEBUG is supported for a browser on the pytest host. The inspector
    # pauses the first page call, so the suffix is the host OS.
    if _playwright_inspector_enabled():
        platform = sys.platform
    elif browser.browser_type.name == "chromium":
        platform = _chromium_snapshot_platform(browser)
    else:
        platform = _navigator_snapshot_platform(browser)

    _snapshot_platform_by_browser[browser] = platform
    logger.debug(f"Snapshot browser platform: {platform}")

    return platform


def _test_requests_browser(request: FixtureRequest) -> bool:
    return any(name in request.fixturenames for name in _BROWSER_FIXTURE_NAMES)


def snapshot_platform_for_test(
    request: FixtureRequest, *, snapshots_disabled: bool
) -> str:
    """Browser OS when this test drives a browser, otherwise the pytest host.

    Byte-only snapshots never open a browser, so there is no remote OS to read.
    Disabled snapshots skip the probe.
    """
    if snapshots_disabled or not _test_requests_browser(request):
        return sys.platform

    browser = request.getfixturevalue("browser")
    assert isinstance(browser, Browser)

    return browser_snapshot_platform(browser)
