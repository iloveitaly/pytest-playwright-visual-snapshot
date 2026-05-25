from pathlib import Path

from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch

from .base import MatchResult


class PixelmatchMatcher:
    name = "pixelmatch"

    def compare(
        self,
        baseline_path: Path,
        actual_path: Path,
        diff_output_path: Path,
        *,
        threshold: float,
        fail_fast: bool = False,
    ) -> MatchResult:
        img_actual = Image.open(actual_path)
        img_baseline = Image.open(baseline_path)
        img_diff = Image.new("RGBA", img_actual.size)

        try:
            mismatch = pixelmatch(
                img_actual,
                img_baseline,
                img_diff,
                threshold=threshold,
                fail_fast=fail_fast,
            )
        except ValueError:
            return MatchResult(
                matched=False,
                size_mismatch=True,
                baseline_size=img_baseline.size,
                actual_size=img_actual.size,
            )

        if mismatch == 0:
            return MatchResult(matched=True, score=0.0)

        img_diff.save(diff_output_path)
        return MatchResult(matched=False, score=float(mismatch))
