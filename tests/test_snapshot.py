"""
General tests for the snapshot system
"""

import pytest
import requests

from tests.conftest import (
    assert_file_exists_message,
    assert_single_snapshot_dir,
    get_expected_filename,
    get_failures_dir,
    get_snapshots_dir,
)


@pytest.mark.parametrize(
    "browser_name",
    ["chromium", "firefox", "webkit"],
)
def test_filepath_exists(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that a snapshot file is created when it doesn't exist initially."""
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            assert_snapshot(page.screenshot())
        """
    )
    snapshots_dir = get_snapshots_dir(testdir)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error

    snapshot_dir = assert_single_snapshot_dir(snapshots_dir)

    filepath = (
        snapshot_dir / get_expected_filename("test_snapshot", browser_name)
    ).resolve()

    assert filepath.exists(), assert_file_exists_message(filepath)


@pytest.mark.parametrize(
    "browser_name",
    ["chromium", "firefox", "webkit"],
)
def test_compare_pass(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that snapshot comparison passes after initial creation."""
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            assert_snapshot(page.screenshot())
        """
    )

    result = testdir.runpytest("--browser", browser_name)

    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error
    assert (
        "[playwright-visual-snapshot] New snapshot(s) created. Please review images."
        in "".join(result.outlines)
    ), "\n".join(result.outlines)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)  # Second run should pass with no errors


@pytest.mark.parametrize(
    "browser_name",
    ["chromium", "firefox", "webkit"],
)
def test_custom_image_name_generated(
    browser_name: str, testdir: pytest.Testdir
) -> None:
    """Test that a snapshot with a custom name is generated correctly."""
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.goto("https://example.com")
            assert_snapshot(page.screenshot(), name="test.png")
        """
    )
    snapshots_dir = get_snapshots_dir(testdir)

    result = testdir.runpytest("--browser", browser_name)

    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error

    snapshot_dir = assert_single_snapshot_dir(snapshots_dir)

    filepath = (snapshot_dir / "test.png").resolve()

    assert filepath.exists(), assert_file_exists_message(filepath)
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)  # Second run should pass with no errors


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_compare_fail(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that snapshot comparison fails when the image is modified."""
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.goto("https://placehold.co/250x250/FFFFFF/000000/png")
            element = page.query_selector('img')
            assert_snapshot(element.screenshot())
        """
    )
    snapshots_dir = get_snapshots_dir(testdir)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error
    assert (
        "[playwright-visual-snapshot] New snapshot(s) created. Please review images"
        in "".join(result.outlines)
    )
    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error
    assert (
        "[playwright-visual-snapshot] Snapshots updated. Please review images"
        in "".join(result.outlines)
    )

    snapshot_dir = assert_single_snapshot_dir(snapshots_dir)

    filepath = (
        snapshot_dir / get_expected_filename("test_snapshot", browser_name)
    ).resolve()

    assert filepath.exists()
    img = requests.get("https://placehold.co/250x250/000000/FFFFFF/png").content
    filepath.write_bytes(img)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(
        passed=1, failed=0, errors=1
    )  # Test passes but has error - modified from failed=1, errors=0
    assert "[playwright-visual-snapshot] Snapshots DO NOT match!" in "".join(
        result.outlines
    )


@pytest.mark.parametrize(
    "browser_name",
    ["firefox", "webkit"],
)
def test_compare_with_fail_fast(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test snapshot comparison with fail_fast enabled."""
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.goto("https://placehold.co/250x250/FFFFFF/000000/png")
            element = page.query_selector('img')
            assert_snapshot(element.screenshot(), fail_fast=True)
        """
    )
    snapshots_dir = get_snapshots_dir(testdir)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error
    assert (
        "[playwright-visual-snapshot] New snapshot(s) created. Please review images."
        in "".join(result.outlines)
    )
    snapshot_dir = assert_single_snapshot_dir(snapshots_dir)

    filepath = (
        snapshot_dir / get_expected_filename("test_snapshot", browser_name)
    ).resolve()

    assert filepath.exists()

    img = requests.get("https://placehold.co/250x250/000000/FFFFFF/png").content
    filepath.write_bytes(img)
    result = testdir.runpytest("--browser", browser_name)

    result.assert_outcomes(failed=1)  # Test should fail immediately with fail_fast=True
    assert "[playwright-visual-snapshot] Snapshots DO NOT match!" in "".join(
        result.outlines
    )


@pytest.mark.parametrize(
    "browser_name",
    ["chromium", "firefox", "webkit"],
)
def test_actual_expected_diff_images_generated(
    browser_name: str, testdir: pytest.Testdir
) -> None:
    """Test that actual, expected, and diff images are generated on snapshot mismatch."""
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.goto("https://placehold.co/250x250/000000/FFFFFF/png")
            element = page.query_selector('img')
            assert_snapshot(element.screenshot())
        """
    )
    snapshots_dir = get_snapshots_dir(testdir)

    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")
    result.assert_outcomes(passed=1, errors=1)  # Test passes but has teardown error
    assert (
        "[playwright-visual-snapshot] Snapshots updated. Please review images"
        in "".join(result.outlines)
    )

    snapshot_dir = assert_single_snapshot_dir(snapshots_dir)

    filepath = (
        snapshot_dir / get_expected_filename("test_snapshot", browser_name)
    ).resolve()

    assert filepath.exists(), assert_file_exists_message(filepath)
    img = requests.get("https://placehold.co/250x250/FFFFFF/000000/png").content
    filepath.write_bytes(img)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(
        passed=1, failed=0, errors=1
    )  # Modified from failed=1, errors=0
    results_dir_name = get_failures_dir(testdir)
    test_results_dir = assert_single_snapshot_dir(results_dir_name)

    expected_filename = get_expected_filename("test_snapshot", browser_name)
    actual_img = test_results_dir / f"actual_{expected_filename}"
    expected_img = test_results_dir / f"expected_{expected_filename}"
    diff_img = test_results_dir / f"diff_{expected_filename}"

    assert actual_img.exists(), assert_file_exists_message(actual_img)
    assert expected_img.exists(), assert_file_exists_message(expected_img)
    assert diff_img.exists(), assert_file_exists_message(diff_img)
