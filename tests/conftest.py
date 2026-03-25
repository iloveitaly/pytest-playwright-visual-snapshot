import sys
import os
import pathlib

pytest_plugins = "pytester"

# Set coverage process start for subprocesses
# This is required because tests use `pytester` which runs `pytest` in a subprocess.
# The `.venv` has `a1_coverage.pth` which starts coverage if `COVERAGE_PROCESS_START` is set.
# We also set `COVERAGE_FILE` to an absolute path to ensure all subprocesses write to the same
# base location (with suffixes if parallel=true) rather than the temporary directory pytester creates.
project_root = pathlib.Path(__file__).parent.parent
os.environ["COVERAGE_PROCESS_START"] = str(project_root / "pyproject.toml")
os.environ["COVERAGE_FILE"] = str(project_root / ".coverage")


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
