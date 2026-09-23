import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, TypeVar

import pytest
from PIL import Image
from playwright.sync_api import Locator
from playwright.sync_api import Page as SyncPage
from pytest import Config, FixtureRequest, Parser
from pytest_plugin_utils import (
    get_artifact_dir,
    get_pytest_option,
    register_pytest_options,
    set_pytest_option,
)

from .matchers import MatchResult, get_matcher
from .matchers.odiff_matcher import ODiffMatcher

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
)

logger = logging.getLogger(__name__)

SNAPSHOT_MESSAGE_PREFIX = "[playwright-visual-snapshot]"
NAMESPACE = "pytest_playwright_visual_snapshot"
_ASSERTION_KWARGS = frozenset(
    {
        "threshold",
        "name",
        "fail_fast",
        "mask_elements",
        "reset_scroll",
        "pixel_percentage_threshold",
        "pixel_threshold",
        "antialiasing",
    }
)

T = TypeVar("T")


class _Missing:
    """Marks an assert_snapshot argument the caller did not pass."""


_MISSING = _Missing()


def _resolve_assertion_kwarg_precedence[T](
    assertion_kwargs: dict[str, Any],
    name: str,
    explicit: T | _Missing,
    default: T,
) -> T:
    """Passed keyword, then configured kwarg default, then built-in default.

    `_Missing` means the caller omitted the keyword, so an explicit False or
    None still wins. The configured default is
    `playwright_visual_assertion_kwargs`.
    """
    if isinstance(explicit, _Missing):
        if name in assertion_kwargs:
            return assertion_kwargs[name]

        return default

    return explicit


def is_ci_environment() -> bool:
    return "GITHUB_ACTIONS" in os.environ


def diff_is_within_allowance(
    result: MatchResult,
    *,
    pixel_percentage_threshold: float | None,
    pixel_threshold: int | None,
) -> bool:
    if result.matched or result.size_mismatch:
        return False

    if pixel_percentage_threshold is None and pixel_threshold is None:
        return False

    if pixel_percentage_threshold is not None and (
        result.diff_percentage is None
        or result.diff_percentage >= pixel_percentage_threshold
    ):
        return False

    return pixel_threshold is None or (
        result.score is not None and result.score <= pixel_threshold
    )


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
        "playwright_visual_matcher",
        default="pixelmatch",
        help="Image matcher to use for visual comparison (e.g. 'pixelmatch')",
        available="ini",
        type_hint=str,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_screenshot_kwargs",
        default={},
        help="Dictionary of kwargs to pass to Playwright's screenshot method",
        available=None,  # Runtime only
        type_hint=dict,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_assertion_kwargs",
        default={},
        help="Default keyword arguments for assert_snapshot",
        available=None,  # Runtime only
        type_hint=dict,
    )

    set_pytest_option(
        NAMESPACE,
        "playwright_visual_update_snapshots",
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
        dest="playwright_visual_update_snapshots",
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


def _create_locators_from_selectors(page: SyncPage | Locator, selectors: list[str]):
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
        failures: list[str],
    ) -> None:
        self._pytestconfig = pytestconfig
        self._request = request

        test_function_name = request.node.name
        self._test_name_without_params = test_name_without_parameters(
            test_function_name
        )
        self._test_name = f"{test_function_name}[{sys.platform!s}]"

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
        self._screenshot_kwargs = (
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_screenshot_kwargs",
                type_hint=dict,
            )
            or {}
        )
        self._assertion_kwargs = (
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_assertion_kwargs",
                type_hint=dict,
            )
            or {}
        )
        unknown_assertion_kwargs = set(self._assertion_kwargs) - _ASSERTION_KWARGS
        assert not unknown_assertion_kwargs, (
            f"unknown assert_snapshot defaults: {sorted(unknown_assertion_kwargs)}"
        )
        self._update_snapshot = bool(
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_update_snapshots",
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

        matcher_name = (
            get_pytest_option(
                NAMESPACE,
                pytestconfig,
                "playwright_visual_matcher",
                type_hint=str,
            )
            or "pixelmatch"
        )
        self._matcher = get_matcher(matcher_name)

        self._failures = failures
        self._warned_disabled = False
        self._counter = 0

    def __call__(
        self,
        img_or_page: bytes | Any,
        *,
        # TODO: rename threshold to color_threshold, including
        # playwright_visual_snapshot_threshold
        threshold: float | None | _Missing = _MISSING,
        name: str | None | _Missing = _MISSING,
        fail_fast: bool | _Missing = _MISSING,
        mask_elements: list[str] | None | _Missing = _MISSING,
        reset_scroll: bool | _Missing = _MISSING,
        pixel_percentage_threshold: float | None | _Missing = _MISSING,
        pixel_threshold: int | None | _Missing = _MISSING,
        antialiasing: bool | _Missing = _MISSING,
    ) -> None:
        threshold_value: float | None = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs, "threshold", threshold, None
        )
        snapshot_name: str | None = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs, "name", name, None
        )
        fail_fast_enabled: bool = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs, "fail_fast", fail_fast, False
        )
        mask_selectors: list[str] | None = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs, "mask_elements", mask_elements, None
        )
        reset_scroll_enabled: bool = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs, "reset_scroll", reset_scroll, False
        )
        pixel_percentage_limit: float | None = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs,
            "pixel_percentage_threshold",
            pixel_percentage_threshold,
            None,
        )
        pixel_limit: int | None = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs, "pixel_threshold", pixel_threshold, None
        )
        ignore_antialiasing: bool = _resolve_assertion_kwarg_precedence(
            self._assertion_kwargs, "antialiasing", antialiasing, False
        )

        if self._disable_snapshots:
            if not self._warned_disabled:
                logger.warning(
                    "%s Visual snapshots disabled; skipping assertions.",
                    SNAPSHOT_MESSAGE_PREFIX,
                )
                self._warned_disabled = True
            return

        if not snapshot_name:
            if self._counter > 0:
                snapshot_name = f"{self._test_name}_{self._counter}.png"
            else:
                snapshot_name = f"{self._test_name}.png"
        else:
            _, ext = os.path.splitext(snapshot_name)
            if ext.lower() not in [".png", ".jpg", ".jpeg", ".webp"]:
                snapshot_name = f"{snapshot_name}.png"

        # Use global threshold if no local threshold provided
        if not threshold_value:
            threshold_value = self._global_snapshot_threshold

        # fail_fast stops after the first pixel, so a pixel or percentage budget would be wrong.
        compare_fail_fast = fail_fast_enabled
        if pixel_percentage_limit is not None or pixel_limit is not None:
            compare_fail_fast = False

        # If page reference is passed, use screenshot
        if isinstance(img_or_page, (Locator, SyncPage)):
            # Combine configured mask elements with any provided in the function call
            all_mask_selectors = list(self._mask_selectors)
            if mask_selectors:
                all_mask_selectors.extend(mask_selectors)

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
                **self._screenshot_kwargs,
            }

            if isinstance(img_or_page, SyncPage) and reset_scroll_enabled:
                img_or_page.evaluate("window.scrollTo(0, 0)")

            img = img_or_page.screenshot(**screenshot_kwargs)
        else:
            img = img_or_page

        # Use get_artifact_dir to automatically create a collision-free path for the current test
        # e.g., <snapshots_dir>/<sanitized-test-node-id>
        # Creation is deferred until here to avoid creating directories when snapshots are disabled
        snapshot_dir = get_artifact_dir(
            self._request.node, self._snapshots_base_dir, create=True
        )
        screenshot_file = snapshot_dir / snapshot_name

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

        failure_dir = get_artifact_dir(
            self._request.node, self._failures_base_dir, create=True
        )
        actual_path = failure_dir / f"actual_{snapshot_name}"
        actual_path.write_bytes(img)
        diff_path = failure_dir / f"diff_{snapshot_name}"

        result = self._matcher.compare(
            baseline_path=screenshot_file,
            actual_path=actual_path,
            diff_output_path=diff_path,
            threshold=threshold_value,
            fail_fast=compare_fail_fast,
            antialiasing=ignore_antialiasing,
        )

        if result.matched or diff_is_within_allowance(
            result,
            pixel_percentage_threshold=pixel_percentage_limit,
            pixel_threshold=pixel_limit,
        ):
            actual_path.unlink(missing_ok=True)
            diff_path.unlink(missing_ok=True)
            return

        if result.size_mismatch and not self._ignore_size_diff:
            msg = (
                f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots DO NOT match! {snapshot_name}"
                f" (Image sizes do not match: {result.actual_size} vs {result.baseline_size})"
            )
            self._failures.append(msg)
            if is_ci_environment():
                screenshot_file.write_bytes(img)
            if fail_fast_enabled:
                pytest.fail(msg)
            return

        if result.size_mismatch:
            logger.debug(
                "Image size mismatch detected, continuing with failure generation."
            )

        img_b = Image.open(screenshot_file)
        img_b.save(f"{failure_dir}/expected_{snapshot_name}")

        if is_ci_environment():
            screenshot_file.write_bytes(img)

        if fail_fast_enabled:
            pytest.fail(
                f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots DO NOT match! {snapshot_name}"
            )

        self._failures.append(
            f"{SNAPSHOT_MESSAGE_PREFIX} Snapshots DO NOT match! {snapshot_name}"
        )


@pytest.fixture(scope="session", autouse=True)
def require_odiff_binary(pytestconfig: Config) -> None:
    # Disabled snapshots never start odiff, so a missing binary is fine.
    snapshots_disabled = bool(
        get_pytest_option(
            NAMESPACE,
            pytestconfig,
            "playwright_visual_disable_snapshots",
            type_hint=bool,
        )
    )
    if snapshots_disabled:
        return

    matcher_name = (
        get_pytest_option(
            NAMESPACE,
            pytestconfig,
            "playwright_visual_matcher",
            type_hint=str,
        )
        or "pixelmatch"
    )
    if matcher_name != "odiff":
        return

    ODiffMatcher().require_binary()


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
