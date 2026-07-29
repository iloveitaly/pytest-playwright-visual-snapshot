import pytest

from tests.conftest import get_snapshots_dir

_TALL_PAGE = (
    "data:text/html,"
    "<html><body style='margin:0'>"
    "<div style='height:800px;background:red'></div>"
    "<div style='height:800px;background:blue'></div>"
    "</body></html>"
)


def test_reset_scroll_matches_top_of_page(testdir: pytest.Testdir) -> None:
    """Scrolled page with reset_scroll=True matches an unscrolled baseline."""
    testdir.makepyfile(
        f"""
        def test_snapshot(page, assert_snapshot):
            page.goto("{_TALL_PAGE}")
            page.evaluate("window.scrollTo(0, 800)")
            assert_snapshot(page, reset_scroll=True)
        """
    )

    result = testdir.runpytest("--browser", "chromium")
    result.assert_outcomes(passed=1, errors=1)
    assert "[playwright-visual-snapshot] New snapshot(s) created" in "".join(
        result.outlines
    )

    result = testdir.runpytest("--browser", "chromium")
    result.assert_outcomes(passed=1)


def test_without_reset_scroll_differs_from_top(testdir: pytest.Testdir) -> None:
    """Scrolled capture without reset_scroll differs from a top-of-page baseline."""
    testdir.makepyfile(
        f"""
        def test_snapshot(page, assert_snapshot):
            page.goto("{_TALL_PAGE}")
            assert_snapshot(page)
        """
    )

    result = testdir.runpytest("--browser", "chromium")
    result.assert_outcomes(passed=1, errors=1)
    assert get_snapshots_dir(testdir).exists()

    testdir.makepyfile(
        f"""
        def test_snapshot(page, assert_snapshot):
            page.goto("{_TALL_PAGE}")
            page.evaluate("window.scrollTo(0, 800)")
            assert_snapshot(page)
        """
    )

    result = testdir.runpytest("--browser", "chromium")
    result.assert_outcomes(passed=1, errors=1)
    assert "[playwright-visual-snapshot] Snapshots DO NOT match!" in "".join(
        result.outlines
    )
