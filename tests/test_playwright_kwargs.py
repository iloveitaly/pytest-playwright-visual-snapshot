import pytest
from PIL import Image
from tests.conftest import (
    assert_single_snapshot_dir,
    get_expected_filename,
    get_snapshots_dir,
)


def test_playwright_kwargs_clip(testdir: pytest.Testdir) -> None:
    testdir.makeconftest(
        """
        def pytest_configure(config):
            config.option.playwright_kwargs = {
                "clip": {"x": 0, "y": 0, "width": 50, "height": 50}
            }
        """
    )
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.goto("data:text/html,<html><body style='width: 500px; height: 500px; background: red;'></body></html>")
            assert_snapshot(page)
        """
    )
    snapshots_dir = get_snapshots_dir(testdir)

    result = testdir.runpytest("--browser", "chromium")
    result.assert_outcomes(passed=1, errors=1)

    snapshot_dir = assert_single_snapshot_dir(snapshots_dir)
    filepath = (
        snapshot_dir / get_expected_filename("test_snapshot", "chromium")
    ).resolve()

    assert filepath.exists()

    with Image.open(filepath) as img:
        assert img.size == (50, 50)
