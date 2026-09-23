from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class MatchResult:
    matched: bool
    '''True when the images match. Both matchers.'''

    size_mismatch: bool = False
    '''True when the dimensions differ and no pixel diff was produced.

    Both matchers. pixelmatch refuses unequal sizes. odiff sets this for a layout-diff.
    '''

    baseline_size: tuple[int, int] | None = None
    '''Baseline width and height. Both matchers set this for a size mismatch.'''

    actual_size: tuple[int, int] | None = None
    '''Actual width and height. Both matchers set this for a size mismatch.'''

    score: float | None = None
    '''Count of differing pixels. Both matchers.

    The pixelmatch mismatch count. With fail_fast, pixelmatch returns 1 at the first
    differing pixel. The odiff diffCount covers the whole image.
    '''

    diff_percentage: float | None = None
    '''Percent of pixels that differ, from 0 to 100. Both matchers.

    The odiff diffPercentage. pixelmatch derives the same scale from its mismatch count.
    Unset for a size mismatch.
    '''


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
