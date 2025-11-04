import logging
import os
import shutil
import sys
import typing as t
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, List, TypeVar, Union

import pytest
from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch
from playwright.sync_api import Locator, Page as SyncPage
from pytest import Config, FixtureRequest, Parser

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
)

logger = logging.getLogger(__name__)

SNAPSHOT_MESSAGE_PREFIX = "[playwright-visual-snapshot]"

T = TypeVar("T")


def _get_option(
    config: Config, key: str, *, cast: t.Callable[[t.Any], T] | None = str
) -> T | None:
    try:
        val = config.getoption(key)
    except ValueError:
        val = None

    if val is None:
        val = config.getini(key)

    if val is not None:
        if cast:
            return cast(val)

        return val

    return None


def is_ci_environment() -> bool:
    return "GITHUB_ACTIONS" in os.environ


def pytest_addoption(parser: Parser) -> None:
    parser.addini(
        "playwright_visual_snapshot_threshold",
        "Threshold for visual comparison of snapshots",
        type="string",
        default="0.1",
    )

    parser.addini(
        "playwright_visual_snapshots_path",
        "Path where snapshots will be stored",
        type="string",
    )

    parser.addini(
        "playwright_visual_snapshot_failures_path",
        "Path where snapshot failures will be stored",
        type="string",
    )

    parser.addini(
        "playwright_visual_snapshot_masks",
        "List of CSS selectors to mask during visual comparison",
        type="linelist",
        default=[],
    )

    group = parser.getgroup("playwright-snapshot", "Playwright Snapshot")
    group.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update snapshots.",
    )


def test_name_without_parameters(test_name: str) -> str:
    return test_name.split("[", 1)[0]


def _create_locators_from_selectors(page: SyncPage, selectors: List[str]):
    """
    Convert a list of CSS selector strings to locator objects
    """
    return [page.locator(selector) for selector in selectors]


# Add a data store for computed paths
class SnapshotPaths:
    snapshots_path: Path = None
    failures_path: Path = None


@pytest.fixture(scope="session", autouse=True)
def cleanup_snapshot_failures(pytestconfig: Config):
    """
    Clean up snapshot failures directory once at the beginning of test session.

    The snapshot storage path is relative to each test folder, modeling after the React snapshot locations
    """

    root_dir = Path(pytestconfig.rootdir)

    # Compute paths once
    SnapshotPaths.snapshots_path = Path(
        _get_option(pytestconfig, "playwright_visual_snapshots_path", cast=str)
        or (root_dir / "__snapshots__")
    )

    SnapshotPaths.failures_path = Path(
        _get_option(pytestconfig, "playwright_visual_snapshot_failures_path", cast=str)
        or (root_dir / "snapshot_failures")
    )

    # Clean up the entire failures directory at session start so past failures don't clutter the result
    # ignore_errors=True to gracefully fail in the case of multiple pytest processes (xdist)
    shutil.rmtree(SnapshotPaths.failures_path, ignore_errors=True)

    # Create the directory to ensure it exists
    SnapshotPaths.failures_path.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Snapshot failures path: {SnapshotPaths.failures_path.resolve()}")
    logger.debug(f"Snapshots path: {SnapshotPaths.snapshots_path.resolve()}")

    yield


@pytest.fixture
def assert_snapshot(
    pytestconfig: Config, request: FixtureRequest, browser_name: str
) -> Callable:
    test_function_name = request.node.name
    test_name_without_params = test_name_without_parameters(test_function_name)
    test_name = f"{test_function_name}[{str(sys.platform)}]"

    current_test_file_path = Path(request.node.fspath)
    test_files_directory = current_test_file_path.parent.resolve()

    # Use global paths if available, otherwise calculate per test
    snapshots_path = SnapshotPaths.snapshots_path
    assert snapshots_path

    snapshot_failures_path = SnapshotPaths.failures_path
    assert snapshot_failures_path

    # we know this exists because of the default value on ini
    global_snapshot_threshold = _get_option(
        pytestconfig, "playwright_visual_snapshot_threshold", cast=str
    )
    assert global_snapshot_threshold
    global_snapshot_threshold = float(global_snapshot_threshold)

    mask_selectors = (
        _get_option(pytestconfig, "playwright_visual_snapshot_masks", cast=None) or []
    )
    update_snapshot = _get_option(pytestconfig, "update_snapshots", cast=bool)

    # for automatically naming multiple assertions
    counter = 0
    # Collection to store failures
    failures = []

    def compare(
        img_or_page: Union[bytes, Any],
        *,
        threshold: float | None = None,
        name=None,
        fail_fast=False,
        mask_elements: List[str] | None = None,
    ) -> None:
        nonlocal counter

        if not name:
            if counter > 0:
                name = f"{test_name}_{counter}.png"
            else:
                name = f"{test_name}.png"

        # Use global threshold if no local threshold provided
        if not threshold:
            threshold = global_snapshot_threshold

        # If page reference is passed, use screenshot
        if isinstance(img_or_page, (Locator, SyncPage)):
            # Combine configured mask elements with any provided in the function call
            all_mask_selectors = list(mask_selectors)
            if mask_elements:
                all_mask_selectors.extend(mask_elements)

            # Convert selectors to locators
            masks = (
                _create_locators_from_selectors(img_or_page, all_mask_selectors)
                if all_mask_selectors
                else []
            )

            img = img_or_page.screenshot(
                animations="disabled",
                type="png",
                mask=masks,
                # TODO only for jpeg
                # quality=100,
            )
        else:
            img = img_or_page

        # test file without the extension
        test_file_name_without_extension = current_test_file_path.stem

        # Created a nested folder to store screenshots: snapshot/test_file_name/test_name/
        test_file_snapshot_dir = (
            snapshots_path / test_file_name_without_extension / test_name_without_params
        )
        test_file_snapshot_dir.mkdir(parents=True, exist_ok=True)

        screenshot_file = test_file_snapshot_dir / name

        # Create a dir where all snapshot test failures will go
        # ex: snapshot_failures/test_file_name/test_name
        failure_results_dir = (
            snapshot_failures_path / test_file_name_without_extension / test_name
        )

        # increment counter before any failures are recorded
        counter += 1

        if update_snapshot:
            screenshot_file.write_bytes(img)
            failures.append(
                f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots updated. Please review images. {screenshot_file}"
            )
            return

        if not screenshot_file.exists():
            screenshot_file.write_bytes(img)
            failures.append(
                f"{SNAPSHOT_MESSAGE_PREFIX} New snapshot(s) created. Please review images. {screenshot_file}"
            )
            return

        img_a = Image.open(BytesIO(img))
        img_b = Image.open(screenshot_file)
        img_diff = Image.new("RGBA", img_a.size)
        mismatch = pixelmatch(
            img_a, img_b, img_diff, threshold=threshold, fail_fast=fail_fast
        )

        if mismatch == 0:
            return

        # Create new test_results folder
        failure_results_dir.mkdir(parents=True, exist_ok=True)
        img_diff.save(f"{failure_results_dir}/diff_{name}")
        img_a.save(f"{failure_results_dir}/actual_{name}")
        img_b.save(f"{failure_results_dir}/expected_{name}")

        # on ci, update the existing screenshots in place so we can download them
        if is_ci_environment():
            screenshot_file.write_bytes(img)

        # Still honor fail_fast if specifically requested
        if fail_fast:
            pytest.fail(f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots DO NOT match! {name}")

        failures.append(f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots DO NOT match! {name}")

    # Register finalizer to report all failures at the end of the test
    def finalize():
        if failures:
            pytest.fail("\n".join(failures))

    request.addfinalizer(finalize)

    return compare
