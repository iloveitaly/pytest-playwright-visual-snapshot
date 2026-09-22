"""Diff allowance and odiff antialiasing configuration."""

from io import BytesIO

import pytest
from PIL import Image

from pytest_playwright_visual_snapshot.matchers.base import MatchResult
from pytest_playwright_visual_snapshot.matchers.odiff_matcher import ODiffMatcher
from pytest_playwright_visual_snapshot.matchers.pixelmatch_matcher import (
    PixelmatchMatcher,
)
from pytest_playwright_visual_snapshot.plugin import (
    AssertSnapshot,
    diff_percentage_is_allowed,
)


def _png_bytes(color=(255, 0, 0, 255), pixel=None) -> bytes:
    image = Image.new("RGBA", (10, 10), color)
    if pixel is not None:
        image.putpixel((0, 0), pixel)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _assertion(pytestconfig, request, tmp_path):
    failures: list[str] = []
    assertion = AssertSnapshot(pytestconfig, request, failures)
    assertion._snapshots_base_dir = tmp_path / "snapshots"
    assertion._failures_base_dir = tmp_path / "failures"
    assertion._test_name = "budget"
    assertion._counter = 0
    return assertion, failures


def test_diff_percentage_is_allowed():
    pixel_diff = MatchResult(matched=False, score=1, diff_percentage=0.005)

    assert diff_percentage_is_allowed(pixel_diff, 0.01) is True
    assert diff_percentage_is_allowed(pixel_diff, 0.005) is False
    assert diff_percentage_is_allowed(pixel_diff, None) is False
    assert (
        diff_percentage_is_allowed(
            MatchResult(matched=False, size_mismatch=True, diff_percentage=0.0),
            1,
        )
        is False
    )


def test_pixelmatch_reports_diff_percentage(tmp_path):
    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    base.write_bytes(_png_bytes())
    actual.write_bytes(_png_bytes(pixel=(0, 0, 255, 255)))

    result = PixelmatchMatcher().compare(base, actual, diff, threshold=0.1)

    assert result.matched is False
    assert result.score == 1
    assert result.diff_percentage == 1


def test_small_diff_within_allowance_passes(pytestconfig, request, tmp_path):
    assertion, failures = _assertion(pytestconfig, request, tmp_path)
    assertion._max_diff_percentage = 2

    assertion(_png_bytes())
    assert any("New snapshot" in failure for failure in failures)

    failures.clear()
    assertion._counter = 0
    assertion(_png_bytes(pixel=(0, 0, 255, 255)))

    assert failures == []
    assert list((tmp_path / "failures").rglob("diff_*.png")) == []
    assert list((tmp_path / "failures").rglob("actual_*.png")) == []


def test_diff_over_allowance_fails(pytestconfig, request, tmp_path):
    assertion, failures = _assertion(pytestconfig, request, tmp_path)
    assertion._max_diff_percentage = 0.5

    assertion(_png_bytes())
    failures.clear()
    assertion._counter = 0
    assertion(_png_bytes(pixel=(0, 0, 255, 255)))

    assert any("DO NOT match" in failure for failure in failures)
    assert list((tmp_path / "failures").rglob("diff_*.png"))


def test_per_call_allowance_overrides_global(pytestconfig, request, tmp_path):
    assertion, failures = _assertion(pytestconfig, request, tmp_path)
    assertion._max_diff_percentage = 0.5

    assertion(_png_bytes())
    failures.clear()
    assertion._counter = 0
    assertion(_png_bytes(pixel=(0, 0, 255, 255)), max_diff_percentage=2)

    assert failures == []


def test_allowance_disables_fail_fast(pytestconfig, request, tmp_path):
    assertion, _failures = _assertion(pytestconfig, request, tmp_path)
    seen: dict[str, object] = {}

    class _Matcher:
        name = "pixelmatch"

        def compare(self, baseline_path, actual_path, diff_output_path, **kwargs):
            seen.update(kwargs)
            return MatchResult(matched=True, score=0.0, diff_percentage=0.0)

    assertion._matcher = _Matcher()
    assertion(_png_bytes())

    seen.clear()
    assertion._counter = 0
    assertion(
        _png_bytes(pixel=(0, 0, 255, 255)),
        fail_fast=True,
        max_diff_percentage=1,
    )

    assert seen["fail_fast"] is False
    assert seen["antialiasing"] is False


def test_antialiasing_is_forwarded(pytestconfig, request, tmp_path):
    assertion, _failures = _assertion(pytestconfig, request, tmp_path)
    seen: dict[str, object] = {}

    class _Matcher:
        name = "odiff"

        def compare(self, baseline_path, actual_path, diff_output_path, **kwargs):
            seen.update(kwargs)
            return MatchResult(matched=True, score=0.0, diff_percentage=0.0)

    assertion._matcher = _Matcher()
    assertion._odiff_antialiasing = True
    assertion(_png_bytes())
    seen.clear()
    assertion._counter = 0
    assertion(_png_bytes(), antialiasing=False)

    assert seen["antialiasing"] is False

    seen.clear()
    assertion._counter = 0
    assertion(_png_bytes())

    assert seen["antialiasing"] is True


def test_options_from_pytest_config(pytestconfig, request, monkeypatch):
    monkeypatch.setattr(
        pytestconfig.option,
        "playwright_visual_max_diff_percentage",
        0.01,
        raising=False,
    )
    monkeypatch.setattr(
        pytestconfig.option,
        "playwright_visual_odiff_antialiasing",
        True,
        raising=False,
    )

    assertion = AssertSnapshot(pytestconfig, request, [])

    assert assertion._max_diff_percentage == 0.01
    assert assertion._odiff_antialiasing is True


def test_odiff_forwards_antialiasing_flag(tmp_path):
    captured: dict[str, object] = {}

    class _Server:
        def compare(self, base, compare, output, options):
            captured["options"] = options
            return {"match": True}

    matcher = ODiffMatcher()
    matcher._ensure_server = lambda: _Server()

    base = tmp_path / "base.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    base.write_bytes(_png_bytes())
    actual.write_bytes(_png_bytes())

    matcher.compare(base, actual, diff, threshold=0.1, antialiasing=True)

    assert captured["options"] == {
        "threshold": 0.1,
        "failOnLayoutDiff": True,
        "antialiasing": True,
    }


def test_ini_options(testdir: pytest.Testdir):
    testdir.makeini(
        """
        [pytest]
        playwright_visual_max_diff_percentage = 0.01
        playwright_visual_odiff_antialiasing = true
        """
    )
    testdir.makepyfile(
        """
        def test_read(pytestconfig, request):
            from pytest_playwright_visual_snapshot.plugin import AssertSnapshot

            assertion = AssertSnapshot(pytestconfig, request, [])
            assert assertion._max_diff_percentage == 0.01
            assert assertion._odiff_antialiasing is True
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)
