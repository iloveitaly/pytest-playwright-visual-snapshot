import os
import shutil
from pathlib import Path

import pytest
import requests

from tests.conftest import (
    assert_single_snapshot_dir,
    get_expected_filename,
    get_snapshots_dir,
)

ODIFF_BIN = os.environ.get("ODIFF_BIN") or shutil.which("odiff")
pytestmark = pytest.mark.skipif(
    ODIFF_BIN is None,
    reason="odiff binary not found — set ODIFF_BIN or install via brew/npm",
)

_ODIFF_FLAG = "--override-ini=playwright_visual_matcher=odiff"


@pytest.mark.parametrize(
    "browser_name",
    ["chromium", "firefox", "webkit"],
)
def test_element_masking(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that element masking works as expected."""
    testdir.makepyfile(
        """
        def test_masked_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            page.evaluate('''
                const timeElement = document.createElement('div');
                timeElement.className = 'timestamp';
                timeElement.textContent = new Date().toISOString();
                document.body.appendChild(timeElement);
            ''')
            assert_snapshot(page, mask_elements=[".timestamp", "h1"])
        """
    )

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=1, errors=1)
    assert "[playwright-visual-snapshot] New snapshot(s) created" in "".join(
        result.outlines
    )

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=1)

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_threshold_setting(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that threshold setting works for comparison tolerance."""
    testdir.makepyfile(
        """
        def test_threshold_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            assert_snapshot(page, threshold=0.8)
        """
    )

    result = testdir.runpytest(
        "--browser", browser_name, "--update-snapshots", _ODIFF_FLAG
    )
    result.assert_outcomes(passed=1, errors=1)

    testdir.makepyfile(
        """
        def test_threshold_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            page.evaluate("document.body.style.backgroundColor = 'rgb(254, 254, 254)'")
            assert_snapshot(page, threshold=0.8)
        """
    )

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=1)

    testdir.makepyfile(
        """
        def test_threshold_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            page.evaluate("document.body.style.backgroundColor = 'rgb(254, 254, 254)'")
            assert_snapshot(page, threshold=0.001)
        """
    )

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=1, failed=0, errors=1)


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_multiple_snapshots_in_test(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test taking multiple snapshots in a single test case."""
    testdir.makepyfile(
        """
        def test_multiple_snapshots(page, assert_snapshot):
            page.goto("https://example.com")
            assert_snapshot(page)
            page.evaluate("document.querySelector('h1').textContent = 'Modified Example'")
            assert_snapshot(page)
            page.evaluate("document.body.style.backgroundColor = '#f0f0f0'")
            assert_snapshot(page)
        """
    )

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=1, errors=1)

    snapshots_root = get_snapshots_dir(testdir)
    snapshot_dir = assert_single_snapshot_dir(snapshots_root)

    snapshot_files = list(snapshot_dir.glob("test_multiple_snapshots*.png"))
    assert len(snapshot_files) == 3, (
        f"Expected 3 snapshots, found {len(snapshot_files)}: {snapshot_files}"
    )

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_fail_fast_option(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test the fail_fast option for early termination on mismatch."""
    testdir.makepyfile(
        """
        def test_fail_fast(page, assert_snapshot):
            page.goto("https://placehold.co/250x250/FFFFFF/000000/png")
            element = page.query_selector('img')
            assert_snapshot(element.screenshot(), fail_fast=True)
        """
    )

    result = testdir.runpytest(
        "--browser", browser_name, "--update-snapshots", _ODIFF_FLAG
    )
    result.assert_outcomes(passed=1, errors=1)

    snapshots_root = Path(testdir.tmpdir) / "__snapshots__"
    assert snapshots_root.exists()
    snapshot_dirs = list(snapshots_root.iterdir())
    assert len(snapshot_dirs) == 1
    filepath = snapshot_dirs[0] / get_expected_filename("test_fail_fast", browser_name)

    img = requests.get("https://placehold.co/250x250/000000/FFFFFF/png").content
    filepath.write_bytes(img)

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=0, failed=1, errors=0)

    assert "[playwright-visual-snapshot] Snapshots DO NOT match!" in "".join(
        result.outlines
    )


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_parametrized_tests(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that parametrized tests generate correct snapshot names."""
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.parametrize("theme", ["light", "dark"])
        def test_themes(page, assert_snapshot, theme):
            page.goto("https://example.com")

            if theme == "dark":
                page.evaluate('''
                    document.body.style.backgroundColor = '#333';
                    document.body.style.color = '#fff';
                ''')

            assert_snapshot(page)
        """
    )

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=2, errors=2)

    snapshots_root = Path(testdir.tmpdir) / "__snapshots__"
    assert snapshots_root.exists()
    snapshot_dirs = list(snapshots_root.iterdir())
    assert len(snapshot_dirs) == 2

    for theme in ["light", "dark"]:
        found = False
        for snapshot_dir in snapshot_dirs:
            if list(snapshot_dir.glob(f"test_themes*{theme}*.png")):
                found = True
                break
        assert found, f"Snapshot for {theme} not found in any directory"

    result = testdir.runpytest("--browser", browser_name, _ODIFF_FLAG)
    result.assert_outcomes(passed=2)
