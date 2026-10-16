import os
import select
import signal
import subprocess
import sys
from pathlib import Path

import playwright
import pytest
from playwright.sync_api import sync_playwright

from pytest_playwright_visual_snapshot.plugin import (
    browser_snapshot_platform,
    platform_suffix_from_chromium_user_agent,
    platform_suffix_from_navigator_platform,
)

from tests.conftest import get_snapshots_dir


@pytest.mark.parametrize(
    ("user_agent", "suffix"),
    [
        (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/156.0.8078.4 Safari/537.36",
            "linux",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
            "darwin",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
            "win32",
        ),
        (
            "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
            "linux",
        ),
    ],
)
def test_platform_suffix_from_chromium_user_agent(user_agent: str, suffix: str) -> None:
    assert platform_suffix_from_chromium_user_agent(user_agent) == suffix


def test_unknown_chromium_user_agent_fails() -> None:
    with pytest.raises(AssertionError, match="unknown chromium user agent"):
        platform_suffix_from_chromium_user_agent("Mozilla/5.0")


@pytest.mark.parametrize(
    ("navigator_platform", "suffix"),
    [
        ("Linux x86_64", "linux"),
        ("Linux aarch64", "linux"),
        ("MacIntel", "darwin"),
        ("Win32", "win32"),
    ],
)
def test_platform_suffix_from_navigator_platform(
    navigator_platform: str, suffix: str
) -> None:
    assert platform_suffix_from_navigator_platform(navigator_platform) == suffix


def test_unknown_navigator_platform_fails() -> None:
    with pytest.raises(AssertionError, match="unknown browser platform"):
        platform_suffix_from_navigator_platform("FreeBSD")


class _BrowserType:
    def __init__(self, name: str) -> None:
        self.name = name


class _Browser:
    def __init__(self, name: str) -> None:
        self.browser_type = _BrowserType(name)


@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
def test_inspector_uses_host_platform(
    browser_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PWDEBUG", "1")
    monkeypatch.setattr(sys, "platform", "darwin")

    def fail_if_probed(browser: _Browser) -> str:
        raise AssertionError(browser)

    monkeypatch.setattr(
        "pytest_playwright_visual_snapshot.plugin._navigator_snapshot_platform",
        fail_if_probed,
    )
    monkeypatch.setattr(
        "pytest_playwright_visual_snapshot.plugin._chromium_snapshot_platform",
        fail_if_probed,
    )

    assert browser_snapshot_platform(_Browser(browser_name)) == "darwin"


@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
def test_live_browser_platform_ignores_host_platform(
    browser_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "not-a-host-platform")

    with sync_playwright() as playwright_sync:
        browser = getattr(playwright_sync, browser_name).launch()
        try:
            if browser_name == "chromium":
                session = browser.new_browser_cdp_session()
                user_agent = session.send("Browser.getVersion")["userAgent"]
                session.detach()
                assert isinstance(user_agent, str)
                expected = platform_suffix_from_chromium_user_agent(user_agent)
            else:
                page = browser.new_page()
                navigator_platform = page.evaluate("() => navigator.platform")
                user_agent = page.evaluate("() => navigator.userAgent")
                page.close()
                assert isinstance(navigator_platform, str)
                assert isinstance(user_agent, str)
                expected = platform_suffix_from_navigator_platform(navigator_platform)

                # WebKit's user agent says Macintosh on Linux. The suffix follows the page.
                if "Macintosh" in user_agent and navigator_platform.startswith("Linux"):
                    assert expected == "linux"

            suffix = browser_snapshot_platform(browser)
            assert browser_snapshot_platform(browser) == suffix
        finally:
            browser.close()

    assert suffix == expected
    assert suffix != "not-a-host-platform"


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


def test_connected_chromium_platform_ignores_host_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "not-a-host-platform")
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
                session = browser.new_browser_cdp_session()
                user_agent = session.send("Browser.getVersion")["userAgent"]
                session.detach()
                assert isinstance(user_agent, str)
                expected = platform_suffix_from_chromium_user_agent(user_agent)
                suffix = browser_snapshot_platform(browser)
            finally:
                browser.close()
    finally:
        _stop_process_group(process)

    assert suffix == expected
    assert suffix != "not-a-host-platform"


@pytest.mark.parametrize("browser_name", ["chromium", "firefox"])
def test_snapshot_filename_uses_browser_os(
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
    assert f"[{sys.platform}]" in snapshots[0].name
    assert f"[{fake_platform}]" not in snapshots[0].name
