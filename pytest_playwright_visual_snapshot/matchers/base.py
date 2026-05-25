from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class MatchResult:
    matched: bool
    size_mismatch: bool = False
    baseline_size: tuple[int, int] | None = None
    actual_size: tuple[int, int] | None = None
    score: float | None = None


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
    ) -> MatchResult: ...
