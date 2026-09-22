"""Diff allowance and odiff antialiasing configuration."""

from functools import partial
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
    diff_is_within_allowance,
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


def test_diff_is_within_allowance():
    pixel_diff = MatchResult(matched=False, score=1, diff_percentage=0.005)

    assert (
        diff_is_within_allowance(
            pixel_diff, max_diff_percentage=0.01, max_diff_pixels=None
        )
        is True
    )
    assert (
        diff_is_within_allowance(
            pixel_diff, max_diff_percentage=0.005, max_diff_pixels=None
        )
        is False
    )
    assert (
        diff_is_within_allowance(
            pixel_diff, max_diff_percentage=None, max_diff_pixels=None
        )
        is False
    )
    assert (
        diff_is_within_allowance(
            pixel_diff, max_diff_percentage=None, max_diff_pixels=1
        )
        is True
    )
    assert (
        diff_is_within_allowance(
            pixel_diff, max_diff_percentage=None, max_diff_pixels=0
        )
        is False
    )
    assert (
        diff_is_within_allowance(
            pixel_diff, max_diff_percentage=0.01, max_diff_pixels=0
        )
        is False
    )
    assert (
        diff_is_within_allowance(
            pixel_diff, max_diff_percentage=0.001, max_diff_pixels=5
        )
        is False
    )
    assert (
        diff_is_within_allowance(
            MatchResult(
                matched=False, size_mismatch=True, score=1, diff_percentage=0.0
            ),
            max_diff_percentage=1,
            max_diff_pixels=10,
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

    assertion(_png_bytes())
    assert any("New snapshot" in failure for failure in failures)

    failures.clear()
    assertion._counter = 0
    assertion(_png_bytes(pixel=(0, 0, 255, 255)), max_diff_percentage=2)

    assert failures == []
    assert list((tmp_path / "failures").rglob("diff_*.png")) == []
    assert list((tmp_path / "failures").rglob("actual_*.png")) == []


def test_max_diff_pixels_allows_that_many_pixels(pytestconfig, request, tmp_path):
    assertion, failures = _assertion(pytestconfig, request, tmp_path)

    assertion(_png_bytes())
    failures.clear()
    assertion._counter = 0
    assertion(_png_bytes(pixel=(0, 0, 255, 255)), max_diff_pixels=1)

    assert failures == []

    failures.clear()
    assertion._counter = 0
    assertion(_png_bytes(pixel=(0, 0, 255, 255)), max_diff_pixels=0)

    assert any("DO NOT match" in failure for failure in failures)


def test_diff_over_allowance_fails(pytestconfig, request, tmp_path):
    assertion, failures = _assertion(pytestconfig, request, tmp_path)

    assertion(_png_bytes())
    failures.clear()
    assertion._counter = 0
    assertion(_png_bytes(pixel=(0, 0, 255, 255)), max_diff_percentage=0.5)

    assert any("DO NOT match" in failure for failure in failures)
    assert list((tmp_path / "failures").rglob("diff_*.png"))


def test_call_overrides_partial_default(pytestconfig, request, tmp_path):
    assertion, failures = _assertion(pytestconfig, request, tmp_path)
    with_default = partial(assertion, max_diff_percentage=0.5)

    with_default(_png_bytes())
    failures.clear()
    assertion._counter = 0
    with_default(_png_bytes(pixel=(0, 0, 255, 255)), max_diff_percentage=2)

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

    seen.clear()
    assertion._counter = 0
    assertion(
        _png_bytes(pixel=(0, 0, 255, 255)),
        fail_fast=True,
        max_diff_pixels=1,
    )

    assert seen["fail_fast"] is False


def test_antialiasing_is_forwarded(pytestconfig, request, tmp_path):
    assertion, _failures = _assertion(pytestconfig, request, tmp_path)
    seen: dict[str, object] = {}

    class _Matcher:
        name = "odiff"

        def compare(self, baseline_path, actual_path, diff_output_path, **kwargs):
            seen.update(kwargs)
            return MatchResult(matched=True, score=0.0, diff_percentage=0.0)

    assertion._matcher = _Matcher()
    assertion(_png_bytes())
    seen.clear()
    assertion._counter = 0
    assertion(_png_bytes(), antialiasing=True)

    assert seen["antialiasing"] is True


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


def test_fixture_override_binds_default_kwargs(testdir: pytest.Testdir):
    testdir.makeconftest(
        """
        from functools import partial

        import pytest

        @pytest.fixture
        def assert_snapshot(assert_snapshot):
            return partial(assert_snapshot, max_diff_percentage=50, antialiasing=True)
        """
    )
    testdir.makepyfile(
        """
        from io import BytesIO

        from PIL import Image

        def _png(pixel=None):
            image = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
            if pixel is not None:
                image.putpixel((0, 0), pixel)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

        def test_budget(assert_snapshot):
            assert_snapshot(_png(), name="same.png")
            assert_snapshot(_png((0, 0, 255, 255)), name="one-pixel.png")
        """
    )

    created = testdir.runpytest()
    created.assert_outcomes(passed=1, errors=1)

    compared = testdir.runpytest()
    compared.assert_outcomes(passed=1)
