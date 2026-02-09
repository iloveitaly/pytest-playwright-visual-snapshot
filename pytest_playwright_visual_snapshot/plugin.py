import logging
import os
import shutil
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, List, TypeVar, Union

import pytest
from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch
from playwright.sync_api import Locator
from playwright.sync_api import Page as SyncPage
from pytest import Config, FixtureRequest, Parser

from pytest_playwright_visual_snapshot.config import VisualSnapshotConfig

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
)

logger = logging.getLogger(__name__)

SNAPSHOT_MESSAGE_PREFIX = "[playwright-visual-snapshot]"

T = TypeVar("T")


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

    parser.addini(
        "playwright_visual_ignore_size_diff",
        "Allow snapshots with different dimensions to generate visual diffs instead of failing",
        type="bool",
        default=False,
    )

    parser.addini(
        "playwright_visual_disable_snapshots",
        "Disable visual snapshot comparisons",
        type="bool",
        default=False,
    )

    group = parser.getgroup("playwright-snapshot", "Playwright Snapshot")
    group.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update snapshots.",
    )

    group.addoption(
        "--ignore-size-diff",
        action="store_true",
        default=False,
        dest="playwright_visual_ignore_size_diff",
        help="Allow snapshots with different dimensions to generate visual diffs instead of failing (overrides ini setting).",
    )

    group.addoption(
        "--disable-visual-snapshots",
        action="store_true",
        default=False,
        dest="playwright_visual_disable_snapshots",
        help="Disable visual snapshot assertions (overrides ini setting).",
    )


def test_name_without_parameters(test_name: str) -> str:
    return test_name.split("[", 1)[0]


def _create_locators_from_selectors(page: SyncPage | Locator, selectors: List[str]):
    """
    Convert a list of CSS selector strings to locator objects
    """
    return [page.locator(selector) for selector in selectors]


@pytest.fixture(scope="session")
def visual_snapshot_config(pytestconfig: Config) -> VisualSnapshotConfig:
    pytestconfig.option.playwright_rootdir = Path(pytestconfig.rootdir)  # type: ignore
    return VisualSnapshotConfig.model_validate(pytestconfig.option)


@pytest.fixture(scope="session", autouse=True)
def cleanup_snapshot_failures(visual_snapshot_config: VisualSnapshotConfig):
    """
    Clean up snapshot failures directory once at the beginning of test session.

    The snapshot storage path is relative to each test folder, modeling after the React snapshot locations
    """

    # Clean up the entire failures directory at session start so past failures don't clutter the result
    # ignore_errors=True to gracefully fail in the case of multiple pytest processes (xdist)
    shutil.rmtree(
        visual_snapshot_config.playwright_visual_snapshot_failures_path,
        ignore_errors=True,
    )

    # Create the directory to ensure it exists
    visual_snapshot_config.playwright_visual_snapshot_failures_path.mkdir(
        parents=True, exist_ok=True
    )

    logger.debug(
        f"Snapshot failures path: {visual_snapshot_config.playwright_visual_snapshot_failures_path.resolve()}"
    )
    logger.debug(
        f"Snapshots path: {visual_snapshot_config.playwright_visual_snapshots_path.resolve()}"
    )

    yield


class AssertSnapshot:
    """Assert that a snapshot matches the stored baseline.

    Example:
        ```
        def test_myapp(page, assert_snapshot: AssertSnapshot):
            page.goto("https://example.com")
            assert_snapshot(page)
        ```
    """

    def __init__(
        self,
        visual_snapshot_config: VisualSnapshotConfig,
        request: FixtureRequest,
        failures: List[str],
    ) -> None:
        self.config = visual_snapshot_config
        test_function_name = request.node.name
        self._test_name_without_params = test_name_without_parameters(
            test_function_name
        )
        self._test_name = f"{test_function_name}[{str(sys.platform)}]"
        self._current_test_file_path = Path(request.node.fspath)
        self._failures = failures
        self._warned_disabled = False
        self._counter = 0

    def __call__(
        self,
        img_or_page: Union[bytes, Any],
        *,
        threshold: float | None = None,
        name: str | None = None,
        fail_fast: bool = False,
        mask_elements: List[str] | None = None,
    ) -> None:
        if self.config.playwright_visual_disable_snapshots:
            if not self._warned_disabled:
                logger.warning(
                    "%s Visual snapshots disabled; skipping assertions.",
                    SNAPSHOT_MESSAGE_PREFIX,
                )
                self._warned_disabled = True
            return

        if not name:
            if self._counter > 0:
                name = f"{self._test_name}_{self._counter}.png"
            else:
                name = f"{self._test_name}.png"

        # Use global threshold if no local threshold provided
        if not threshold:
            threshold = self.config.playwright_visual_snapshot_threshold

        # If page reference is passed, use screenshot
        if isinstance(img_or_page, (Locator, SyncPage)):
            # Combine configured mask elements with any provided in the function call
            all_mask_selectors = self.config.playwright_visual_snapshot_masks
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
        test_file_name_without_extension = self._current_test_file_path.stem

        # Created a nested folder to store screenshots: snapshot/test_file_name/test_name/
        test_file_snapshot_dir = (
            self.config.playwright_visual_snapshots_path
            / test_file_name_without_extension
            / self._test_name_without_params
        )
        test_file_snapshot_dir.mkdir(parents=True, exist_ok=True)

        screenshot_file = test_file_snapshot_dir / name

        # Create a dir where all snapshot test failures will go
        # ex: snapshot_failures/test_file_name/test_name
        failure_results_dir = (
            self.config.playwright_visual_snapshot_failures_path
            / test_file_name_without_extension
            / self._test_name
        )

        # increment counter before any failures are recorded
        self._counter += 1

        if self.config.update_snapshots:
            screenshot_file.write_bytes(img)
            self._failures.append(
                f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots updated. Please review images. {screenshot_file}"
            )
            return

        if not screenshot_file.exists():
            screenshot_file.write_bytes(img)
            self._failures.append(
                f"{SNAPSHOT_MESSAGE_PREFIX} New snapshot(s) created. Please review images. {screenshot_file}"
            )
            return

        img_a = Image.open(BytesIO(img))
        img_b = Image.open(screenshot_file)
        img_diff = Image.new("RGBA", img_a.size)

        mismatch = 0
        try:
            mismatch = pixelmatch(
                img_a, img_b, img_diff, threshold=threshold, fail_fast=fail_fast
            )
            if mismatch == 0:
                return
        except ValueError as e:
            # Raised when image sizes differ
            if not self.config.playwright_visual_ignore_size_diff:
                # Re-raise the exception if size differences should not be ignored
                raise
            # Otherwise, continue generating failure results
            logger.debug(
                f"Image size mismatch detected: {e}. Continuing with failure generation."
            )

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

        self._failures.append(
            f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots DO NOT match! {name}"
        )


@pytest.fixture
def assert_snapshot(
    visual_snapshot_config: VisualSnapshotConfig,
    request: FixtureRequest,
    browser_name: str,
) -> AssertSnapshot:
    # Collection to store failures
    failures = []

    # Register finalizer to report all failures at the end of the test
    def finalize():
        if failures:
            pytest.fail("\n".join(failures))

    request.addfinalizer(finalize)

    return AssertSnapshot(
        visual_snapshot_config=visual_snapshot_config,
        request=request,
        failures=failures,
    )
