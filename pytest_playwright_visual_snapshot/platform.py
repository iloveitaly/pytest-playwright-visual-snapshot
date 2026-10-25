"""Platform key for `test[browser][platform].png` snapshot names.

A locally launched browser uses `sys.platform` on the pytest host, so the
filename stays tied to the machine that rendered the pixels.

A WebSocket browser uses `websocket`. Playwright's `Browser` reports the
browser name and version, not the operating system of the WebSocket server.
Every WebSocket connection shares that key. Set
`playwright_visual_snapshot_platform` when two WebSocket environments must
keep separate baselines. That setting overrides both automatic keys.

The WebSocket signal is pytest-playwright's `connect_options` fixture. A
non-empty value means `BrowserType.connect()` will be used, and reading the
fixture does not start a browser. `assert_snapshot` does not resolve the
`browser` fixture, because that can launch a browser only to choose a
filename.

A custom `browser` fixture that calls `BrowserType.connect()` itself does
not set `connect_options`. Configure the platform key for that setup.
"""

import sys

WEBSOCKET_PLATFORM_KEY = "websocket"


def snapshot_platform_key(
    configured_platform: str | None, *, is_websocket_connection: bool
) -> str:
    "configured key, then websocket, then the pytest host platform"

    if configured_platform:
        return configured_platform

    if is_websocket_connection:
        return WEBSOCKET_PLATFORM_KEY

    return sys.platform
