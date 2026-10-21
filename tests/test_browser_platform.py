import os
import select
import signal
import subprocess
import sys
from pathlib import Path

import playwright
import pytest
from playwright.sync_api import sync_playwright

from pytest_playwright_visual_snapshot.platform import (
    is_websocket_browser,
    snapshot_platform_key,
)

from tests.conftest import get_snapshots_dir


class _Connection:
    def __init__(self, is_remote: bool) -> None:
        self.is_remote = is_remote


class _BrowserImpl:
    def __init__(self, is_remote: bool) -> None:
        self._connection = _Connection(is_remote)


class _Browser:
    def __init__(self, is_remote: bool = False) -> None:
        self._impl_obj = _BrowserImpl(is_remote)


def test_snapshot_platform_key_uses_host_for_local_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert snapshot_platform_key(_Browser(), None) == "darwin"
    assert snapshot_platform_key(None, None) == "darwin"


def test_snapshot_platform_key_uses_websocket_for_remote_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert snapshot_platform_key(_Browser(is_remote=True), None) == "websocket"


def test_snapshot_platform_key_configured_value_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert snapshot_platform_key(_Browser(), "docker-linux") == "docker-linux"
    assert (
        snapshot_platform_key(_Browser(is_remote=True), "docker-linux")
        == "docker-linux"
    )
    assert snapshot_platform_key(None, "docker-linux") == "docker-linux"


@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
def test_live_browser_is_not_websocket(
    browser_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "host-platform")

    with sync_playwright() as playwright_sync:
        browser = getattr(playwright_sync, browser_name).launch()
        try:
            assert not is_websocket_browser(browser)
            assert snapshot_platform_key(browser, None) == "host-platform"
        finally:
            browser.close()


def _start_chromium_server() -> subprocess.Popen[str]:
    driver = Path(playwright.__file__).parent / "driver"
    node = driver / "node"
    package = driver / "package" / "index.js"
    script = """
const { chromium } = require(process.argv[1]);
chromium.launchServer().then((server) => {
  process.stdout.write(server.wsEndpoint() + "\\n");
});
"""
    return subprocess.Popen(
        [str(node), "-e", script, str(package)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _stop_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)

    process.wait()


def test_connected_chromium_uses_websocket_platform_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "host-platform")
    process = _start_chromium_server()
    assert process.stdout is not None
    ready, _, _ = select.select([process.stdout], [], [], 30)
    assert ready, "playwright server did not print an endpoint"
    endpoint = process.stdout.readline().strip()

    try:
        assert endpoint.startswith("ws://"), endpoint

        with sync_playwright() as playwright_sync:
            browser = playwright_sync.chromium.connect(endpoint)
            try:
                assert is_websocket_browser(browser)
                suffix = snapshot_platform_key(browser, None)
            finally:
                browser.close()
    finally:
        _stop_process_group(process)

    assert suffix == "websocket"


@pytest.mark.parametrize("browser_name", ["chromium", "firefox"])
def test_snapshot_filename_uses_host_platform(
    browser_name: str, testdir: pytest.Testdir
) -> None:
    fake_platform = "linux" if sys.platform == "darwin" else "darwin"
    testdir.makeconftest(
        f"""
        import sys
        sys.platform = {fake_platform!r}
        """
    )
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.set_content("<h1>Hello</h1>")
            assert_snapshot(page.screenshot())
        """
    )

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1, errors=1)

    snapshots = list(get_snapshots_dir(testdir).rglob("*.png"))
    assert len(snapshots) == 1, snapshots
    assert f"[{fake_platform}]" in snapshots[0].name
    assert f"[{sys.platform}]" not in snapshots[0].name


def test_snapshot_filename_uses_configured_platform(testdir: pytest.Testdir) -> None:
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.set_content("<h1>Hello</h1>")
            assert_snapshot(page.screenshot())
        """
    )

    result = testdir.runpytest("--playwright-visual-snapshot-platform=docker-linux")
    result.assert_outcomes(passed=1, errors=1)

    result = testdir.runpytest(
        "--override-ini=playwright_visual_snapshot_platform=docker-linux"
    )
    result.assert_outcomes(passed=1)

    snapshots = list(get_snapshots_dir(testdir).rglob("*.png"))
    assert len(snapshots) == 1, snapshots
    assert "[docker-linux]" in snapshots[0].name


def test_snapshot_filename_uses_websocket_platform(testdir: pytest.Testdir) -> None:
    process = _start_chromium_server()
    assert process.stdout is not None
    ready, _, _ = select.select([process.stdout], [], [], 30)
    assert ready, "playwright server did not print an endpoint"
    endpoint = process.stdout.readline().strip()

    try:
        assert endpoint.startswith("ws://"), endpoint
        testdir.makeconftest(
            f"""
            import pytest

            @pytest.fixture(scope="session")
            def browser(browser_type):
                browser = browser_type.connect({endpoint!r})
                yield browser
                browser.close()
            """
        )
        testdir.makepyfile(
            """
            def test_snapshot(page, assert_snapshot):
                page.set_content("<h1>Hello</h1>")
                assert_snapshot(page.screenshot())
            """
        )

        result = testdir.runpytest("--browser", "chromium")
        result.assert_outcomes(passed=1, errors=1)
    finally:
        _stop_process_group(process)

    snapshots = list(get_snapshots_dir(testdir).rglob("*.png"))
    assert len(snapshots) == 1, snapshots
    assert "[websocket]" in snapshots[0].name
