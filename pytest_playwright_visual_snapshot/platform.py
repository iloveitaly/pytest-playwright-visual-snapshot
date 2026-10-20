"""Choose the OS suffix stored in a snapshot filename.

Baselines are named `test[browser][os].png`. The suffix uses `linux`, `darwin`, and `win32`, the same values existing baselines already have from `sys.platform`. Changing that vocabulary would rename every baseline.

The requirement is the OS of the machine that rendered the pixels, not the OS running pytest. A Mac running pytest against Chromium in a Linux container must write `[linux]`, matching CI. Reading `sys.platform` on the pytest process would write `[darwin]` and miss those files.

Every browser is asked the same way: a temporary page reads `navigator.platform` in that browser. This deliberately trades one blank page per browser for a single detection path. The result is cached, and visual tests already create pages. In headed mode, that page can be briefly visible.

Chromium's browser-process user agent was not used for every browser because WebKit reports Macintosh in its user agent on Linux. It would store Linux WebKit snapshots under `[darwin]`.

Reading Chromium through CDP `Browser.getVersion` was also set aside. It avoids the temporary page and follows a remote Chromium connection, but it only works for Chromium and needs a second transport and a second user-agent mapping. One page probe covers local and remote Chromium, Firefox, and WebKit.

An unknown reported platform raises instead of falling back to the pytest host. A guessed suffix would silently create or miss baselines under the wrong OS name.

`PWDEBUG` is a host-browser workflow. Its inspector pauses the first page call, so this module returns the pytest host OS before opening a probe page. Docker browsers are used without `PWDEBUG`.
"""

import logging
import os
import sys
from weakref import WeakKeyDictionary

from playwright.sync_api import Browser

logger = logging.getLogger(__name__)

_PLATFORM_SUFFIXES = (
    ("Win", "win32"),
    ("Mac", "darwin"),
    ("Linux", "linux"),
    ("CrOS", "linux"),
)
_snapshot_platform_by_browser: WeakKeyDictionary[Browser, str] = WeakKeyDictionary()


def _playwright_inspector_enabled() -> bool:
    # PWDEBUG=1 pauses the first page call. console logging does not.
    mode = os.environ.get("PWDEBUG", "")
    return mode not in ("", "0", "false", "console")


def platform_suffix_from_navigator_platform(navigator_platform: str) -> str:
    """Map `navigator.platform` onto the snapshot OS suffix."""
    for marker, suffix in _PLATFORM_SUFFIXES:
        if marker in navigator_platform:
            return suffix

    raise AssertionError(f"unknown browser platform {navigator_platform}")


def _navigator_snapshot_platform(browser: Browser) -> str:
    page = browser.new_page()
    try:
        navigator_platform = page.evaluate("() => navigator.platform")
    finally:
        page.close()

    assert isinstance(navigator_platform, str)

    return platform_suffix_from_navigator_platform(navigator_platform)


def browser_snapshot_platform(browser: Browser) -> str:
    """OS suffix for the browser that renders snapshots."""
    # PWDEBUG is supported for a browser on the pytest host. The inspector
    # pauses the first page call, so the suffix is the host OS.
    if _playwright_inspector_enabled():
        return sys.platform

    cached = _snapshot_platform_by_browser.get(browser)
    if cached is not None:
        return cached

    platform = _navigator_snapshot_platform(browser)

    _snapshot_platform_by_browser[browser] = platform
    logger.debug(f"Snapshot browser platform: {platform}")

    return platform
