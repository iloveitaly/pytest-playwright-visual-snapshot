import os
import select
import signal
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import playwright
import pytest

from pytest_playwright_visual_snapshot.platform import (
    WEBSOCKET_PLATFORM_KEY,
    snapshot_platform_key,
)

from tests.conftest import get_snapshots_dir


@pytest.mark.parametrize(
    ("configured_platform", "is_websocket_connection", "expected"),
    [
        (None, False, "host-platform"),
        (None, True, WEBSOCKET_PLATFORM_KEY),
        ("docker-linux", False, "docker-linux"),
        ("docker-linux", True, "docker-linux"),
    ],
)
def test_snapshot_platform_key(
    configured_platform: str | None,
    is_websocket_connection: bool,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "host-platform")

    assert (
        snapshot_platform_key(
            configured_platform,
            is_websocket_connection=is_websocket_connection,
        )
        == expected
    )


def _create_page_snapshot(testdir: pytest.Testdir, *pytest_args: str) -> Path:
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.set_content("<h1>Hello</h1>")
            assert_snapshot(page.screenshot())
        """
    )

    result = testdir.runpytest(*pytest_args)
    result.assert_outcomes(passed=1, errors=1)

    snapshots = list(get_snapshots_dir(testdir).rglob("*.png"))
    assert len(snapshots) == 1, snapshots

    return snapshots[0]


def test_snapshot_filename_uses_host_platform(testdir: pytest.Testdir) -> None:
    testdir.makeconftest(
        """
        import sys
        sys.platform = "patched-host-platform"
        """
    )

    snapshot = _create_page_snapshot(testdir)

    assert "[patched-host-platform]" in snapshot.name


def test_snapshot_filename_uses_configured_platform(testdir: pytest.Testdir) -> None:
    snapshot = _create_page_snapshot(
        testdir, "--playwright-visual-snapshot-platform=docker-linux"
    )

    assert "[docker-linux]" in snapshot.name


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
        def test_snapshot(assert_snapshot):
            assert_snapshot(b"unused")
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1, errors=1)

    snapshots = list(get_snapshots_dir(testdir).rglob("*.png"))
    assert len(snapshots) == 1, snapshots
    assert f"[{sys.platform}]" in snapshots[0].name


@contextmanager
def _chromium_websocket_endpoint() -> Iterator[str]:
    driver = Path(playwright.__file__).parent / "driver"
    script = """
const { chromium } = require(process.argv[1]);
chromium.launchServer().then((server) => {
  process.stdout.write(server.wsEndpoint() + "\\n");
});
"""
    process = subprocess.Popen(
        [str(driver / "node"), "-e", script, str(driver / "package" / "index.js")],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )

    try:
        assert process.stdout is not None
        ready, _, _ = select.select([process.stdout], [], [], 30)
        assert ready, "playwright server did not print an endpoint"

        endpoint = process.stdout.readline().strip()
        assert endpoint.startswith("ws://"), endpoint

        yield endpoint
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)

        process.wait()


def test_snapshot_filename_uses_websocket_platform(testdir: pytest.Testdir) -> None:
    with _chromium_websocket_endpoint() as endpoint:
        testdir.makeconftest(
            f"""
            import pytest

            @pytest.fixture(scope="session")
            def connect_options():
                return {{"endpoint": {endpoint!r}}}
            """
        )

        snapshot = _create_page_snapshot(testdir, "--browser", "chromium")

    assert f"[{WEBSOCKET_PLATFORM_KEY}]" in snapshot.name
