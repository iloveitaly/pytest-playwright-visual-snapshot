import logging
import os
import shutil
import sys
import typing as t
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Union

import pytest
from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch
from playwright.sync_api import Page as SyncPage
from pytest import Config, FixtureRequest, Parser

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
)

logger = logging.getLogger(__name__)


def _get_option(config: Config, key: str):
    try:
        val = config.getoption(key)
    except ValueError:
        val = None

    if val is None:
        val = config.getini(key)

    return val


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
        "playwright_visual_failure_directory",
        "Directory for storing visual failure images",
        type="string",
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


@pytest.fixture
def assert_snapshot(
    pytestconfig: Config, request: FixtureRequest, browser_name: str
) -> Callable:
    test_function_name = request.node.name
    test_name_without_params = test_name_without_parameters(test_function_name)
    test_name = f"{test_function_name}[{str(sys.platform)}]"

    current_test_file_path = Path(request.node.fspath)
    test_files_directory = current_test_file_path.parent.resolve()

    snapshots_path = Path(
        t.cast(str, _get_option(pytestconfig, "playwright_visual_snapshots_path"))
        or (test_files_directory / "__snapshots__")
    )
    snapshot_failures_path = Path(
        t.cast(
            str, _get_option(pytestconfig, "playwright_visual_snapshot_failures_path")
        )
        or (test_files_directory / "snapshot_failures")
    )

    global_snapshot_threshold = float(
        t.cast(str, _get_option(pytestconfig, "playwright_visual_snapshot_threshold"))
    )

    update_snapshot = _get_option(pytestconfig, "update_snapshots")

    # for automatically naming multiple assertions
    counter = 0

    def compare(
        img_or_page: Union[bytes, Any],
        *,
        threshold: float | None = None,
        name=None,
        fail_fast=False,
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
        if isinstance(img_or_page, SyncPage):
            img = img_or_page.screenshot(
                animations="disabled",
                type="jpeg",
                quality=100,
                # TODO replace with param
                mask=[img_or_page.locator('[data-clerk-component="UserButton"]')],
            )
        else:
            img = img_or_page

        # test file without the extension
        test_file_name_without_extension = current_test_file_path.stem

        # TODO this doesn't work with nested flders and custom paths
        # created a nested folder to store screenshots: snapshot/test_file_name/test_name/
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

        # Remove a single test's past run dir with actual, diff and expected images
        if failure_results_dir.exists():
            shutil.rmtree(failure_results_dir)

        # increment counter before any pytest.fail
        counter += 1

        if update_snapshot:
            screenshot_file.write_bytes(img)
            pytest.fail(
                f"[playwright-visual-snapshot] Snapshots updated. Please review images. {screenshot_file}"
            )

        if not screenshot_file.exists():
            screenshot_file.write_bytes(img)
            pytest.fail(
                f"[playwright-visual-snapshot] New snapshot(s) created. Please review images. {screenshot_file}"
            )

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
        # otherwise, it's hard to get linux-box screenshots without a linux box!
        if is_ci_environment():
            screenshot_file.write_bytes(img)

        pytest.fail("[playwright-visual-snapshot] Snapshots DO NOT match!")

    return compare
