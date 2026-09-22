"""Test pytest-playwright-visual-snapshot."""

import pytest_playwright_visual_snapshot


def test_import() -> None:
    """Test that the  can be imported."""
    assert isinstance(pytest_playwright_visual_snapshot.__name__, str)


def test_version() -> None:
    """Test that the version is available."""
    assert isinstance(pytest_playwright_visual_snapshot.__version__, str)
