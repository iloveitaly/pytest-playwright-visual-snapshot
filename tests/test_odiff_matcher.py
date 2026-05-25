"""Unit tests for ODiffMatcher.

Skipped when the odiff binary is unavailable — install via
`brew install odiff` or `npm i -g odiff-bin`, or set ODIFF_BIN.
"""

import os
import shutil
import unittest.mock

import pytest
from PIL import Image

from pytest_playwright_visual_snapshot.matchers.odiff_matcher import (
    ODiffBinaryNotFoundError,
    ODiffMatcher,
)

# Skip all tests if odiff binary not present
ODIFF_BIN = os.environ.get("ODIFF_BIN") or shutil.which("odiff")
pytestmark = pytest.mark.skipif(
    ODIFF_BIN is None,
    reason="odiff binary not found — set ODIFF_BIN or install via brew/npm",
)


def _write_png(path, size=(10, 10), color=(255, 0, 0, 255)):
    img = Image.new("RGBA", size, color)
    img.save(path)


def test_match(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _write_png(base)
    _write_png(actual)

    matcher = ODiffMatcher()
    result = matcher.compare(base, actual, diff, threshold=0.1)
    matcher._server.stop()

    assert result.matched is True
    assert result.score == 0.0
    assert not diff.exists()


def test_pixel_diff(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _write_png(base, color=(255, 0, 0, 255))
    _write_png(actual, color=(0, 0, 255, 255))

    matcher = ODiffMatcher()
    result = matcher.compare(base, actual, diff, threshold=0.1)
    matcher._server.stop()

    assert result.matched is False
    assert result.size_mismatch is False
    assert result.score is not None and result.score > 0
    assert diff.exists()


def test_layout_diff(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _write_png(base, size=(10, 10))
    _write_png(actual, size=(20, 20))

    matcher = ODiffMatcher()
    result = matcher.compare(base, actual, diff, threshold=0.1)
    matcher._server.stop()

    assert result.matched is False
    assert result.size_mismatch is True
    assert result.baseline_size == (10, 10)
    assert result.actual_size == (20, 20)


def test_binary_not_found(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _write_png(base)
    _write_png(actual)

    matcher = ODiffMatcher(binary_path=None)
    with (
        unittest.mock.patch.dict(os.environ, {"ODIFF_BIN": "/nonexistent/odiff"}),
        unittest.mock.patch("shutil.which", return_value=None),
        pytest.raises(ODiffBinaryNotFoundError),
    ):
        matcher.compare(base, actual, diff, threshold=0.1)


def test_server_reused(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff1 = tmp_path / "diff1.png"
    diff2 = tmp_path / "diff2.png"
    _write_png(base)
    _write_png(actual)

    matcher = ODiffMatcher()
    matcher.compare(base, actual, diff1, threshold=0.1)
    server_after_first = matcher._server
    matcher.compare(base, actual, diff2, threshold=0.1)
    server_after_second = matcher._server

    matcher._server.stop()

    assert server_after_first is server_after_second
