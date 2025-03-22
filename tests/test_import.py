"""Test pytest-playwright-visual-snapshot."""

import pytest_playwright_visual_snapshot


def test_import() -> None:
    """Test that the  can be imported."""
    assert isinstance(pytest_playwright_visual_snapshot.__name__, str)


# TODO for debuggging!
# def test_inspection(fixture_for_inspection):
#     pass
