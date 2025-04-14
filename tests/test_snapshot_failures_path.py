import sys
from pathlib import Path

import pytest


def list_directory_contents(path: Path) -> str:
    """List contents of a directory for debugging purposes."""
    if not path.exists():
        return f"Directory {path} does not exist"
    files = list(path.iterdir()) if path.is_dir() else []
    return f"Directory {path} contains: {[f.name for f in files]}"


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_failures_are_written(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that failure images are written to the failures directory when a test fails."""
    # Create test file that will generate a snapshot and then fail
    testdir.makepyfile(
        """
        import pytest

        def test_snapshot(page, assert_snapshot):
            # First create a baseline snapshot
            page.goto("https://example.com")
            assert_snapshot(page.screenshot(), name="failure_test.png")

            # Modify content to cause mismatch
            page.set_content("<html><body><h1>Modified Content</h1></body></html>")

            # This should fail and create files in the failures directory
            with pytest.raises(AssertionError):
                assert_snapshot(page.screenshot(), name="failure_test.png")
        """
    )

    # Run once to create the snapshot
    result = testdir.runpytest("--browser", browser_name)

    # Run again to create the failure
    result = testdir.runpytest("--browser", browser_name)

    # Get path to failures directory
    test_name = f"test_snapshot[{browser_name}][{sys.platform}]"
    failures_dir = (
        Path(testdir.tmpdir)
        / "snapshot_failures"
        / "test_failures_are_written"
        / test_name
    )

    # Verify failure artifacts exist
    assert failures_dir.exists(), f"Failures directory not created: {failures_dir}"
    assert (failures_dir / "actual_failure_test.png").exists(), (
        "Actual image not created"
    )
    assert (failures_dir / "expected_failure_test.png").exists(), (
        "Expected image not created"
    )
    assert (failures_dir / "diff_failure_test.png").exists(), "Diff image not created"


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_failures_are_cleaned_on_update(
    browser_name: str, testdir: pytest.Testdir
) -> None:
    """Test that failures directory is cleaned when snapshots are updated."""
    # Create test file
    testdir.makepyfile(
        """
        import pytest

        def test_snapshot(page, assert_snapshot):
            # Create initial snapshot
            page.goto("https://example.com")
            assert_snapshot(page.screenshot(), name="cleanup_test.png")

            # Modify content to cause mismatch
            page.set_content("<html><body><h1>Different Content</h1></body></html>")

            # This should fail and create failure artifacts
            with pytest.raises(AssertionError):
                assert_snapshot(page.screenshot(), name="cleanup_test.png")
        """
    )

    # Run once to create snapshot
    result = testdir.runpytest("--browser", browser_name)

    # Run again to generate failure
    result = testdir.runpytest("--browser", browser_name)

    # Get path to failures directory
    test_name = f"test_snapshot[{browser_name}][{sys.platform}]"
    failures_dir = (
        Path(testdir.tmpdir)
        / "snapshot_failures"
        / "test_failures_are_cleaned_on_update"
        / test_name
    )

    # Verify failure directory exists with artifacts
    assert failures_dir.exists(), "Failures directory not created"
    assert (failures_dir / "actual_cleanup_test.png").exists(), (
        "Actual image not created"
    )

    # Run with update flag to update snapshots
    result = testdir.runpytest("--browser", browser_name, "--update-snapshots")

    # Directory should be cleaned/removed after update
    assert not failures_dir.exists(), (
        f"Failures directory should be removed after update: {list_directory_contents(failures_dir.parent)}"
    )


@pytest.mark.parametrize(
    "browser_name",
    ["chromium"],
)
def test_multiple_failures_in_test(browser_name: str, testdir: pytest.Testdir) -> None:
    """Test that multiple failures in a single test create multiple failure artifacts."""
    # Create test file with multiple assertions
    testdir.makepyfile(
        """
        import pytest

        def test_multiple_snapshots(page, assert_snapshot):
            # Create initial snapshots
            page.goto("https://example.com")
            assert_snapshot(page.screenshot(), name="multiple_test_1.png")
            assert_snapshot(page.screenshot(), name="multiple_test_2.png")
            assert_snapshot(page.screenshot(), name="multiple_test_3.png")

            # Modify content to cause mismatches
            page.set_content("<html><body><h1>Modified Content</h1></body></html>")

            # These should fail and create multiple failure artifacts
            with pytest.raises(AssertionError):
                # Non-fail-fast mode will collect all failures
                assert_snapshot(page.screenshot(), name="multiple_test_1.png")
                assert_snapshot(page.screenshot(), name="multiple_test_2.png")
                assert_snapshot(page.screenshot(), name="multiple_test_3.png")
        """
    )

    # Run once to create snapshots
    result = testdir.runpytest("--browser", browser_name)

    # Run again to generate failures
    result = testdir.runpytest("--browser", browser_name)

    # Get path to failures directory
    test_name = f"test_multiple_snapshots[{browser_name}][{sys.platform}]"
    failures_dir = (
        Path(testdir.tmpdir)
        / "snapshot_failures"
        / "test_multiple_failures_in_test"
        / test_name
    )

    # Verify multiple failure artifacts exist
    assert failures_dir.exists(), "Failures directory not created"

    # Check for all three sets of failure artifacts
    for i in range(1, 4):
        assert (failures_dir / f"actual_multiple_test_{i}.png").exists(), (
            f"Actual image {i} not created"
        )
        assert (failures_dir / f"expected_multiple_test_{i}.png").exists(), (
            f"Expected image {i} not created"
        )
        assert (failures_dir / f"diff_multiple_test_{i}.png").exists(), (
            f"Diff image {i} not created"
        )

    # Count total number of files (should be 9 - 3 sets of 3 files)
    failure_files = list(failures_dir.glob("*.png"))
    assert len(failure_files) == 9, (
        f"Expected 9 failure files, found {len(failure_files)}: {[f.name for f in failure_files]}"
    )
