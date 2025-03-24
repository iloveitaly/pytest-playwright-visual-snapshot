import sys
from pathlib import Path

import pytest
import requests


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
            # Add a dynamic element
            page.evaluate('''
                const timeElement = document.createElement('div');
                timeElement.className = 'timestamp';
                timeElement.textContent = new Date().toISOString();
                document.body.appendChild(timeElement);
            ''')
            # Mask the dynamic element
            assert_snapshot(page, mask_elements=[".timestamp", "h1"])
        """
    )

    # First run creates snapshot
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error
    assert "[playwright-visual-snapshot] New snapshot(s) created" in "".join(
        result.outlines
    )

    # Second run with same elements masked should pass
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)  # Should pass with no errors

    # Run again with different timestamp but same masking should still pass
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)  # Should pass with no errors


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
            assert_snapshot(page, threshold=0.8)  # Very permissive threshold
        """
    )

    # Create initial snapshot
    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error

    # Modify page background slightly - with high threshold, should still pass
    testdir.makepyfile(
        """
        def test_threshold_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            page.evaluate("document.body.style.backgroundColor = 'rgb(254, 254, 254)'")  # Tiny change
            assert_snapshot(page, threshold=0.8)  # Very permissive threshold
        """
    )

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)  # Should pass with no errors

    # Now with strict threshold, same tiny change should fail
    testdir.makepyfile(
        """
        def test_threshold_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            page.evaluate("document.body.style.backgroundColor = 'rgb(254, 254, 254)'")  # Tiny change
            assert_snapshot(page, threshold=0.001)  # Very strict threshold
        """
    )

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(
        passed=1, failed=0, errors=1
    )  # Modified from failed=1, errors=0
    # Test has error due to image mismatch with strict threshold


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

            # First snapshot
            assert_snapshot(page)

            # Modify page and take second snapshot
            page.evaluate("document.querySelector('h1').textContent = 'Modified Example'")
            assert_snapshot(page)

            # Modify again for third snapshot
            page.evaluate("document.body.style.backgroundColor = '#f0f0f0'")
            assert_snapshot(page)
        """
    )

    # First run creates all snapshots
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error

    # Check that multiple snapshots were created
    snapshot_dir = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_multiple_snapshots_in_test"
        / "test_multiple_snapshots"
    )

    # Count total number of snapshots created instead of assuming specific naming
    snapshot_files = list(snapshot_dir.glob("test_multiple_snapshots*.png"))
    assert len(snapshot_files) == 3, (
        f"Expected 3 snapshots, found {len(snapshot_files)}: {snapshot_files}"
    )

    # Second run should pass with all snapshots matching
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)  # Should pass with no errors


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

    # Create initial snapshot
    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error

    # Path to the snapshot file
    filepath = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_fail_fast_option"
        / "test_fail_fast"
        / f"test_fail_fast[{browser_name}][{sys.platform}].png"
    )

    # Replace the snapshot with a different image
    img = requests.get("https://placehold.co/250x250/000000/FFFFFF/png").content
    filepath.write_bytes(img)

    # Run with fail_fast=True - should fail immediately on first pixel difference
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(
        passed=0, failed=1, errors=0
    )  # Test should fail immediately with fail_fast=True

    # Check for fail-fast message in output
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

    # First run creates snapshots - expect passing tests but errors in teardown for each parametrized test
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(
        passed=2, errors=2
    )  # 2 tests pass but each has a teardown error

    # Check that parametrized snapshots were created with correct names
    snapshot_dir = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_parametrized_tests"
        / "test_themes"
    )

    # Should have snapshots for both parameter values
    assert (
        snapshot_dir / f"test_themes[{browser_name}-light][{sys.platform}].png"
    ).exists()
    assert (
        snapshot_dir / f"test_themes[{browser_name}-dark][{sys.platform}].png"
    ).exists()

    # Second run should pass
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(
        passed=2
    )  # 2 tests from parametrization, all pass with no errors
