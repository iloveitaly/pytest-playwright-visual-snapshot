"""Choose the platform key stored in a snapshot filename.

Baselines are named `test[browser][platform].png`.

For a browser launched by the pytest process, the automatic key is `sys.platform` on the pytest host. This keeps the behavior and baseline names that existed before remote-browser support was considered.

For a browser obtained through Playwright's WebSocket connection, the pixels may be rendered by another machine. Playwright's public `Browser` object reports the browser name and version, but not the operating system of the WebSocket server. Instead of probing the browser to recover that OS, the automatic key is `websocket`.

That is a deliberate grouping decision, not a claim that every WebSocket browser runs the same OS. All WebSocket connections share one baseline key unless the user supplies a more specific key. Different rendering environments behind WebSocket connections should use different configured keys when their snapshots must be kept separate.

A configured key overrides both automatic cases. This lets a project name the actual rendering environment, such as `linux`, `docker-linux`, or another stable environment name, without depending on how pytest connected to the browser.

No browser page, CDP session, or other probe is used. This removes the temporary-page cost and the `PWDEBUG` special case from platform selection. `PWDEBUG` remains a host-browser debugging workflow, but it no longer changes how the platform key is chosen.

Detection uses Playwright's remote-connection marker. `BrowserType.connect()` creates a child connection and marks it remote, while a locally launched browser uses the local connection. Playwright's public sync `Browser` API does not expose that transport distinction.
"""

import sys

from playwright.sync_api import Browser

WEBSOCKET_PLATFORM_KEY = "websocket"


def is_websocket_browser(browser: Browser) -> bool:
    """Whether this browser came from `BrowserType.connect()`."""
    return browser._impl_obj._connection.is_remote


def snapshot_platform_key(
    browser: Browser | None, configured_platform: str | None
) -> str:
    """Configured key, then `websocket`, then the pytest host platform."""
    if configured_platform:
        return configured_platform

    if browser is not None and is_websocket_browser(browser):
        return WEBSOCKET_PLATFORM_KEY

    return sys.platform
