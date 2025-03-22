import sys
from pathlib import Path

import pytest
import requests


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
    filepath = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_filepath_exists"
        / "test_snapshot"
        / f"test_snapshot[{browser_name}][{sys.platform}].jpeg"
    ).resolve()
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(failed=1)
    assert filepath.exists(), f"Snapshot file does not exist: {filepath}"


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
    print(result.outlines)
    result.assert_outcomes(failed=1)

    assert (
        "[playwright-visual-snapshot] New snapshot(s) created. Please review images."
        in "".join(result.outlines)
    ), result.outlines
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)


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
            assert_snapshot(page.screenshot(), name="test.jpeg")
        """
    )
    filepath = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_custom_image_name_generated"
        / "test_snapshot"
        / "test.jpeg"
    ).resolve()
    result = testdir.runpytest("--browser", browser_name)

    result.assert_outcomes(failed=1)
    assert filepath.exists(), f"Custom snapshot file does not exist: {filepath}"
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(passed=1)


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
    filepath = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_compare_fail"
        / "test_snapshot"
        / f"test_snapshot[{browser_name}][{sys.platform}].jpeg"
    ).resolve()
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(failed=1)
    assert (
        "[playwright-visual-snapshot] New snapshot(s) created. Please review images"
        in "".join(result.outlines)
    )
    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")
    result.assert_outcomes(failed=1)
    assert (
        "[playwright-visual-snapshot] Snapshots updated. Please review images"
        in "".join(result.outlines)
    )

    assert filepath.exists()
    img = requests.get("https://placehold.co/250x250/000000/FFFFFF/png").content
    filepath.write_bytes(img)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(failed=1)
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
    filepath = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_compare_with_fail_fast"
        / "test_snapshot"
        / f"test_snapshot[{browser_name}][{sys.platform}].jpeg"
    ).resolve()
    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")
    result.assert_outcomes(failed=1)
    assert (
        "[playwright-visual-snapshot] Snapshots updated. Please review images"
        in "".join(result.outlines)
    )
    assert filepath.exists()
    img = requests.get("https://placehold.co/250x250/000000/FFFFFF/png").content
    filepath.write_bytes(img)
    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(failed=1)
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
    filepath = (
        Path(testdir.tmpdir)
        / "__snapshots__"
        / "test_actual_expected_diff_images_generated"
        / "test_snapshot"
        / f"test_snapshot[{browser_name}][{sys.platform}].jpeg"
    ).resolve()
    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")
    result.assert_outcomes(failed=1)
    assert (
        "[playwright-visual-snapshot] Snapshots updated. Please review images"
        in "".join(result.outlines)
    )

    assert filepath.exists()
    img = requests.get("https://placehold.co/250x250/FFFFFF/000000/png").content
    filepath.write_bytes(img)

    result = testdir.runpytest("--browser", browser_name)
    result.assert_outcomes(failed=1)
    results_dir_name = Path(testdir.tmpdir) / "snapshot_failures"
    test_results_dir = (
        results_dir_name
        / "test_actual_expected_diff_images_generated"
        / f"test_snapshot[{browser_name}][{sys.platform}]"
    )
    actual_img = (
        test_results_dir / f"actual_test_snapshot[{browser_name}][{sys.platform}].jpeg"
    )
    expected_img = (
        test_results_dir
        / f"expected_test_snapshot[{browser_name}][{sys.platform}].jpeg"
    )
    diff_img = (
        test_results_dir / f"diff_test_snapshot[{browser_name}][{sys.platform}].jpeg"
    )
    assert actual_img.exists(), f"Actual image does not exist: {actual_img}"
    assert expected_img.exists(), f"Expected image does not exist: {expected_img}"
    assert diff_img.exists(), f"Diff image does not exist: {diff_img}"
