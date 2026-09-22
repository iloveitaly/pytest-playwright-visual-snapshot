"""Unit tests for ODiffMatcher.

Skipped when the odiff binary is unavailable. Install instructions are in the README.
"""

import shutil
import unittest.mock

import pytest
from PIL import Image

from pytest_playwright_visual_snapshot.matchers.odiff_matcher import (
    ODiffBinaryNotFoundError,
    ODiffMatcher,
)

pytestmark = pytest.mark.skipif(
    shutil.which("odiff") is None,
    reason="odiff binary not found — see the README install instructions",
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
    assert result.score == 100
    assert result.diff_percentage == 100
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
    assert result.diff_percentage is None
    assert result.baseline_size == (10, 10)
    assert result.actual_size == (20, 20)


def test_one_pixel_diff_percentage(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _write_png(base, size=(10, 10), color=(255, 0, 0, 255))
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    img.putpixel((0, 0), (0, 0, 255, 255))
    img.save(actual)

    matcher = ODiffMatcher()
    result = matcher.compare(base, actual, diff, threshold=0.1)
    matcher._server.stop()

    assert result.matched is False
    assert result.score == 1
    assert result.diff_percentage == 1


def test_antialiasing_ignores_edge_blend(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    size = (10, 10)

    baseline = Image.new("RGBA", size, (255, 255, 255, 255))
    shifted = Image.new("RGBA", size, (255, 255, 255, 255))
    for y in range(size[1]):
        for x in range(5):
            baseline.putpixel((x, y), (0, 0, 0, 255))
            shifted.putpixel((x, y), (0, 0, 0, 255))

    shifted.putpixel((4, 5), (128, 128, 128, 255))
    baseline.save(base)
    shifted.save(actual)

    matcher = ODiffMatcher()
    without_aa = matcher.compare(base, actual, diff, threshold=0.1, antialiasing=False)
    with_aa = matcher.compare(
        base, actual, tmp_path / "diff-aa.png", threshold=0.1, antialiasing=True
    )
    matcher._server.stop()

    assert without_aa.matched is False
    assert without_aa.score == 1
    assert with_aa.matched is True
    assert with_aa.diff_percentage == 0


def test_binary_not_found(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    _write_png(base)
    _write_png(actual)

    matcher = ODiffMatcher(binary_path=None)
    with (
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
