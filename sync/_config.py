from __future__ import annotations

from pathlib import Path  # noqa: TCH003

from pydantic import BaseModel


class CanvasConfig(BaseModel):
    api_url: str
    api_key: str
    course_id: int
    grit_permission_quizzes: dict[str, int]
    group_tracking_quizzes: dict[str, int]
    quiz_id_to_group_id: dict[int, int]


class GritConfig(BaseModel):
    api_url: str
    api_key: str
    perform_upload: bool


class MiscConfig(BaseModel):
    backup_folder: Path
    logging_config_file: Path


class Config(BaseModel):
    canvas: CanvasConfig
    grit: GritConfig
    misc: MiscConfig
