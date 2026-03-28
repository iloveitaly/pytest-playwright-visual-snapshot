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
from pytest_plugin_utils import (
    get_artifact_dir,
    get_pytest_option,
    register_pytest_options,
    set_pytest_option,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
)

logger = logging.getLogger(__name__)

SNAPSHOT_MESSAGE_PREFIX = "[playwright-visual-snapshot]"
NAMESPACE = "pytest_playwright_visual_snapshot"

T = TypeVar("T")


def is_ci_environment() -> bool:
    return "GITHUB_ACTIONS" in os.environ


def pytest_addoption(parser: Parser) -> None:
    """Register CLI flags and INI options for this plugin."""

    # We use pytest-plugin-utils to consistently register options across CLI and INI.
    # It handles parsing and typing for us.
    set_pytest_option(
        NAMESPACE,
        "playwright_visual_snapshot_threshold",
        default="0.1",
        help="Threshold for visual comparison of snapshots",
        available="ini",
        type_hint=str,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_snapshots_path",
        default="__snapshots__",
        help="Path where snapshots will be stored",
        available="ini",
        type_hint=Path,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_snapshot_failures_path",
        default="snapshot_failures",
        help="Path where snapshot failures will be stored",
        available="ini",
        type_hint=Path,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_snapshot_masks",
        default=[],
        help="List of CSS selectors to mask during visual comparison",
        available="ini",
        type_hint=list[str],
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_ignore_size_diff",
        default=False,
        help="Allow snapshots with different dimensions to generate visual diffs instead of failing",
        available="ini",
        type_hint=bool,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_disable_snapshots",
        default=False,
        help="Disable visual snapshot comparisons",
        available="ini",
        type_hint=bool,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_kwargs",
        default={},
        help="Dictionary of kwargs to pass to Playwright's screenshot method",
        available=None,  # Runtime only
        type_hint=dict,
    )

    set_pytest_option(
        NAMESPACE,
        "update_snapshots",
        default=False,
        help="Update snapshots",
        available=None,  # Handled manually below
        type_hint=bool,
    )

    register_pytest_options(NAMESPACE, parser)

    # Manual CLI registration for specific flag names
    group = parser.getgroup("playwright-snapshot", "Playwright Snapshot")
    group.addoption(
        "--update-snapshots",
        action="store_true",
        default=None,
        dest="update_snapshots",
        help="Update snapshots.",
    )

    group.addoption(
        "--ignore-size-diff",
        action="store_true",
        default=None,
        dest="playwright_visual_ignore_size_diff",
        help="Allow snapshots with different dimensions to generate visual diffs instead of failing (overrides ini setting).",
    )

    group.addoption(
        "--disable-visual-snapshots",
        action="store_true",
        default=None,
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


@pytest.fixture(scope="session", autouse=True)
def cleanup_snapshot_failures(pytestconfig: Config):
    """
    Clean up snapshot failures directory once at the beginning of test session.

    The snapshot storage path is relative to each test folder, modeling after the React snapshot locations
    """

    root_dir = Path(pytestconfig.rootdir)  # type: ignore

    # Fetch the configured failures path using pytest-plugin-utils logic, falling back to a default
    failures_base_dir = get_pytest_option(
        NAMESPACE,
        pytestconfig,
        "playwright_visual_snapshot_failures_path",
        type_hint=Path,
    ) or Path("snapshot_failures")

    if not failures_base_dir.is_absolute():
        failures_base_dir = root_dir / failures_base_dir

    # Clean up the entire failures directory at session start so past failures don't clutter the result
    # ignore_errors=True to gracefully fail in the case of multiple pytest processes (xdist)
    shutil.rmtree(failures_base_dir, ignore_errors=True)

    # Create the directory to ensure it exists
    failures_base_dir.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Snapshot failures path: {failures_base_dir.resolve()}")

    # Also log the root snapshots path for debugging purposes
    snapshots_base_dir = get_pytest_option(
        NAMESPACE,
        pytestconfig,
        "playwright_visual_snapshots_path",
        type_hint=Path,
    ) or Path("__snapshots__")

    if not snapshots_base_dir.is_absolute():
        snapshots_base_dir = root_dir / snapshots_base_dir
    logger.debug(f"Snapshots path: {snapshots_base_dir.resolve()}")

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
        pytestconfig: Config,
        request: FixtureRequest,
        failures: List[str],
    ) -> None:
        self._pytestconfig = pytestconfig
        self._request = request

        test_function_name = request.node.name
        self._test_name_without_params = test_name_without_parameters(
            test_function_name
        )
        self._test_name = f"{test_function_name}[{str(sys.platform)}]"

        # Resolve base directories for artifacts
        root_dir = Path(pytestconfig.rootdir)  # type: ignore

        snapshots_base_dir = get_pytest_option(
            NAMESPACE,
            pytestconfig,
            "playwright_visual_snapshots_path",
            type_hint=Path,
        ) or Path("__snapshots__")
        if not snapshots_base_dir.is_absolute():
            snapshots_base_dir = root_dir / snapshots_base_dir
        self._snapshots_base_dir = snapshots_base_dir

        failures_base_dir = get_pytest_option(
            NAMESPACE,
            pytestconfig,
            "playwright_visual_snapshot_failures_path",
            type_hint=Path,
        ) or Path("snapshot_failures")
        if not failures_base_dir.is_absolute():
            failures_base_dir = root_dir / failures_base_dir
        self._failures_base_dir = failures_base_dir

        # Retrieve and cast configuration options from pytest-plugin-utils
        # These can come from pytest.ini, pyproject.toml, or CLI flags
        self._global_snapshot_threshold = float(
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_snapshot_threshold",
                type_hint=str,
            )
            or "0.1"
        )

        self._mask_selectors = (
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_snapshot_masks",
                type_hint=list[str],
            )
            or []
        )
        self._playwright_kwargs = (
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_kwargs",
                type_hint=dict,
            )
            or {}
        )
        self._update_snapshot = bool(
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "update_snapshots",
                type_hint=bool,
            )
        )
        self._ignore_size_diff = bool(
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_ignore_size_diff",
                type_hint=bool,
            )
        )
        self._disable_snapshots = bool(
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_disable_snapshots",
                type_hint=bool,
            )
        )

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
        if self._disable_snapshots:
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
            threshold = self._global_snapshot_threshold

        # If page reference is passed, use screenshot
        if isinstance(img_or_page, (Locator, SyncPage)):
            # Combine configured mask elements with any provided in the function call
            all_mask_selectors = list(self._mask_selectors)
            if mask_elements:
                all_mask_selectors.extend(mask_elements)

            # Convert selectors to locators
            masks = (
                _create_locators_from_selectors(img_or_page, all_mask_selectors)
                if all_mask_selectors
                else []
            )

            screenshot_kwargs: dict[str, Any] = {
                "animations": "disabled",
                # "css" scale makes tests reproducable on high-DPI devices
                "scale": "css",
                "type": "png",
                "mask": masks,
                **self._playwright_kwargs,
            }

            img = img_or_page.screenshot(**screenshot_kwargs)
        else:
            img = img_or_page

        # Use get_artifact_dir to automatically create a collision-free path for the current test
        # e.g., <snapshots_dir>/<sanitized-test-node-id>
        # Creation is deferred until here to avoid creating directories when snapshots are disabled
        snapshot_dir = get_artifact_dir(
            self._request.node, self._snapshots_base_dir, create=True
        )
        screenshot_file = snapshot_dir / name

        # increment counter before any failures are recorded
        self._counter += 1

        if self._update_snapshot:
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
            if not self._ignore_size_diff:
                # Re-raise the exception if size differences should not be ignored
                raise
            # Otherwise, continue generating failure results
            logger.debug(
                f"Image size mismatch detected: {e}. Continuing with failure generation."
            )

        # Create new failure results folder if needed
        # We set create=True to ensure the directory is created before we try to write to it
        failure_dir = get_artifact_dir(
            self._request.node, self._failures_base_dir, create=True
        )

        img_diff.save(f"{failure_dir}/diff_{name}")
        img_a.save(f"{failure_dir}/actual_{name}")
        img_b.save(f"{failure_dir}/expected_{name}")

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
    pytestconfig: Config, request: FixtureRequest, browser_name: str
) -> AssertSnapshot:
    # Collection to store failures
    failures = []

    # Register finalizer to report all failures at the end of the test
    def finalize():
        if failures:
            pytest.fail("\n".join(failures))

    request.addfinalizer(finalize)

    return AssertSnapshot(
        pytestconfig=pytestconfig,
        request=request,
        failures=failures,
    )
