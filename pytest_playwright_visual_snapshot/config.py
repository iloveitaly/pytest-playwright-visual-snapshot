from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class VisualSnapshotConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    playwright_rootdir: Path
    playwright_visual_snapshots_path: Path = Field(
        default_factory=lambda data: data["playwright_rootdir"] / "__snapshots__"
    )
    playwright_visual_snapshot_failures_path: Path = Field(
        default_factory=lambda data: data["playwright_rootdir"] / "snapshot_failures"
    )
    playwright_visual_snapshot_threshold: float = 0.1
    playwright_visual_snapshot_masks: List[str] = Field(default_factory=list)
    update_snapshots: bool = False
    playwright_visual_ignore_size_diff: bool = False
    playwright_visual_disable_snapshots: bool = False
