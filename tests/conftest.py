import os
import pathlib
import sys

pytest_plugins = "pytester"

# Set coverage process start for subprocesses
# This is required because tests use `pytester` which runs `pytest` in a subprocess.
# The `.venv` has `a1_coverage.pth` which starts coverage if `COVERAGE_PROCESS_START` is set.
# We also set `COVERAGE_FILE` to an absolute path to ensure all subprocesses write to the same
# base location (with suffixes if parallel=true) rather than the temporary directory pytester creates.
project_root = pathlib.Path(__file__).parent.parent
os.environ["COVERAGE_PROCESS_START"] = str(project_root / "pyproject.toml")
os.environ["COVERAGE_FILE"] = str(project_root / ".coverage")

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def read_fixture_text(name: str) -> str:
    """Return the text of a local fixture file (no network access)."""
    return (FIXTURES_DIR / name).read_text()


def read_fixture_bytes(name: str) -> bytes:
    """Return the bytes of a local fixture file (no network access)."""
    return (FIXTURES_DIR / name).read_bytes()


def copy_fixture_to_testdir(testdir, name: str) -> str:
    """Copy a fixture file into the testdir and return its file:// URI.

    Inner pytester tests run in an isolated tmpdir, so fixtures must live
    there to be reachable via page.goto().
    """
    dest = pathlib.Path(str(testdir.tmpdir)) / name
    dest.write_bytes(read_fixture_bytes(name))
    return dest.as_uri()


def get_snapshots_dir(testdir) -> pathlib.Path:
    """Return the snapshots directory for a given testdir."""
    return pathlib.Path(testdir.tmpdir) / "__snapshots__"


def get_failures_dir(testdir) -> pathlib.Path:
    """Return the failures directory for a given testdir."""
    return pathlib.Path(testdir.tmpdir) / "snapshot_failures"


def assert_single_snapshot_dir(snapshots_dir: pathlib.Path) -> pathlib.Path:
    """Assert that there is exactly one directory in the snapshots directory and return it."""
    assert snapshots_dir.exists()
    snapshot_dirs = [d for d in snapshots_dir.iterdir() if d.is_dir()]
    assert len(snapshot_dirs) == 1, (
        f"Expected 1 snapshot directory, found {len(snapshot_dirs)}: {snapshot_dirs}"
    )
    return snapshot_dirs[0]


def list_directory_contents(path: pathlib.Path) -> str:
    """List contents of a directory for debugging purposes."""
    if not path.exists():
        return f"Directory {path} does not exist"

    if not path.is_dir():
        return f"Path {path} is not a directory"

    files = list(path.iterdir())
    return f"Directory {path} contains: {[f.name for f in files]}"


def assert_file_exists_message(path: pathlib.Path) -> str:
    """Generate a descriptive message for file existence assertions."""
    return f"File does not exist: {path}\n{list_directory_contents(path.parent)}"


def get_expected_filename(test_name: str, browser_name: str) -> str:
    """Helper to construct the expected snapshot filename across platforms."""
    return f"{test_name}[{browser_name}][{sys.platform}].png"
