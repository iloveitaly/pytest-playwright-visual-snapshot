from pathlib import Path

import pytest

from tests.conftest import get_snapshots_dir


def test_disable_visual_snapshots(testdir: pytest.Testdir) -> None:
    testdir.makepyfile(
        """
        def test_snapshot(page, assert_snapshot):
            page.set_content("<div>Hello</div>")
            assert_snapshot(page)
        """
    )

    result = testdir.runpytest("--disable-visual-snapshots")
    result.assert_outcomes(passed=1)

    snapshots_dir = get_snapshots_dir(testdir)
    assert not snapshots_dir.exists()
