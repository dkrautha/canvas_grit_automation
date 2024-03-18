from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from pathlib import Path


class CanvasConfig(BaseModel):
    api_url: str
    api_key: str
    course_id: int
    quizzes: dict[str, int]


class GritConfig(BaseModel):
    api_url: str
    api_key: str
    perform_upload: bool


class MiscConfig(BaseModel):
    backup_folder: Path
    log_folder: Path


class Config(BaseModel):
    canvas: CanvasConfig
    grit: GritConfig
    misc: MiscConfig
