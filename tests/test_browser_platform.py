import os
import select
import signal
import subprocess
import sys
from pathlib import Path

import playwright
import pytest

from pytest_playwright_visual_snapshot.platform import snapshot_platform_key

from tests.conftest import get_snapshots_dir


def test_snapshot_platform_key_uses_host_without_websocket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert snapshot_platform_key(None, is_websocket_connection=False) == "darwin"


def test_snapshot_platform_key_uses_websocket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert snapshot_platform_key(None, is_websocket_connection=True) == "websocket"


def test_snapshot_platform_key_configured_value_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert (
        snapshot_platform_key("docker-linux", is_websocket_connection=False)
        == "docker-linux"
    )
    assert (
        snapshot_platform_key("docker-linux", is_websocket_connection=True)
        == "docker-linux"
    )


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


def test_byte_snapshot_does_not_resolve_browser(testdir: pytest.Testdir) -> None:
    testdir.makeconftest(
        """
        import pytest

        @pytest.fixture(scope="session")
        def browser():
            raise AssertionError("browser must not be resolved for a filename")
        """
    )
    testdir.makepyfile(
        """
        from io import BytesIO

        from PIL import Image

        def test_snapshot(assert_snapshot):
            image = Image.new("RGB", (10, 10), color="red")
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            assert_snapshot(buffer.getvalue())
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1, errors=1)

    snapshots = list(get_snapshots_dir(testdir).rglob("*.png"))
    assert len(snapshots) == 1, snapshots
    assert f"[{sys.platform}]" in snapshots[0].name


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
            def connect_options():
                return {{"endpoint": {endpoint!r}}}
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
