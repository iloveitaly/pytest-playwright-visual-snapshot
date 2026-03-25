def test_identical_filenames_in_different_directories(pytester):
    # Create two directories with the same filename inside
    dir1 = pytester.mkdir("dir1")
    dir2 = pytester.mkdir("dir2")

    test_content = """
import pytest

def test_snapshot(page, assert_snapshot):
    page.set_content("<h1>Hello from {name}</h1>")
    assert_snapshot(page)
"""

    dir1.joinpath("__init__.py").touch()
    dir2.joinpath("__init__.py").touch()

    dir1.joinpath("test_common.py").write_text(test_content.format(name="dir1"))
    dir2.joinpath("test_common.py").write_text(test_content.format(name="dir2"))

    # Run pytest
    result = pytester.runpytest("-v")

    # Check that both tests passed
    result.stdout.fnmatch_lines(
        [
            "*dir1/test_common.py::test_snapshot*PASSED*",
            "*dir2/test_common.py::test_snapshot*PASSED*",
        ]
    )

    # Check where snapshots were created
    snapshot_dir = pytester.path / "__snapshots__"

    assert snapshot_dir.exists()
    snapshot_dirs = list(snapshot_dir.iterdir())
    assert len(snapshot_dirs) == 2
