from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class MatchResult:
    matched: bool
    "true when the images match"

    size_mismatch: bool = False
    "true when the dimensions differ and no pixel diff was produced"

    baseline_size: tuple[int, int] | None = None
    "baseline width and height. set for a size mismatch"

    actual_size: tuple[int, int] | None = None
    "actual width and height. set for a size mismatch"

    score: float | None = None
    "count of differing pixels"

    diff_percentage: float | None = None
    "percent of pixels that differ, from 0 to 100. unset for a size mismatch"


class ImageMatcher(Protocol):
    name: str

    def compare(
        self,
        baseline_path: Path,
        actual_path: Path,
        diff_output_path: Path,
        *,
        threshold: float,
        fail_fast: bool = False,
        antialiasing: bool = False,
    ) -> MatchResult: ...
