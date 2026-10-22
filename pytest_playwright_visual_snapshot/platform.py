"""Choose the platform key stored in a snapshot filename.

Baselines are named `test[browser][platform].png`.

The selection order is:

1. A configured platform key.
2. `websocket` when pytest-playwright is configured to connect over a WebSocket.
3. `sys.platform` on the pytest host.

For a browser launched by the pytest process, the host key keeps the behavior and baseline names that existed before remote-browser support was considered.

For a WebSocket connection, the pixels may be rendered by another machine. Playwright's public `Browser` object reports the browser name and version, but not the operating system of the WebSocket server. Instead of resolving or probing the browser to recover that OS, the automatic key is `websocket`.

That is a deliberate grouping decision, not a claim that every WebSocket browser runs the same OS. All WebSocket connections share one baseline key unless the user supplies a more specific key. Different rendering environments behind WebSocket connections should use different configured keys when their snapshots must be kept separate.

A configured key lets a project name the actual rendering environment, such as `linux`, `docker-linux`, or another stable environment name, without depending on how pytest connected to the browser.

Platform selection never resolves the Playwright `browser` fixture. Resolving it from `assert_snapshot` could launch a browser only to choose a filename, including for byte-only snapshots that otherwise need no browser. The WebSocket case is therefore read from pytest-playwright's `connect_options` fixture: a non-empty value means its browser factory will use `BrowserType.connect()`. A custom `browser` fixture that calls `BrowserType.connect()` itself is not visible to this selection, so those projects should configure the platform key explicitly.

No browser page, CDP session, or other probe is used. This removes the temporary-page cost and the `PWDEBUG` special case from platform selection. `PWDEBUG` remains a host-browser debugging workflow, but it no longer changes how the platform key is chosen.
"""

import sys

WEBSOCKET_PLATFORM_KEY = "websocket"


def snapshot_platform_key(
    configured_platform: str | None, *, is_websocket_connection: bool
) -> str:
    """Configured key, then `websocket`, then the pytest host platform."""
    if configured_platform:
        return configured_platform

    if is_websocket_connection:
        return WEBSOCKET_PLATFORM_KEY

    return sys.platform
